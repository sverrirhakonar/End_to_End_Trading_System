# src/backtester.py

from typing import Dict, List, Tuple
import json
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.gateways.multi_historical_data_gateway import MultiHistoricalDataGateway
from src.price_manager import PriceManager
from src.strategies import Strategy
from src.signals import Signal, SignalBundle
from src.execution_manager import ExecutionManager
from src.order_manager import OrderManager
from src.position_manager import PositionManager, TradeRecord
from src.order_book import OrderBook
from src.simulatedMatchingEngine import SimulatedMatchingEngine
from src.logger_gateway import OrderLogger
from model.models import MarketDataPoint


@dataclass
class WeightedStrategy:
    strategy: Strategy
    weight: float = 1.0


class Backtester:
    def __init__(
        self,
        config_path: str,
        price_manager: PriceManager,
        position_manager: PositionManager,
        strategies_by_symbol: Dict[str, List[WeightedStrategy]],
        execution_manager: ExecutionManager,
        order_manager: OrderManager,
    ):
        self.data_gateway = MultiHistoricalDataGateway(config_path)
        self.pm = price_manager
        self.pmgr = position_manager
        self.strategies_by_symbol = strategies_by_symbol
        self.exec_mgr = execution_manager
        self.order_mgr = order_manager

        self.order_logger = OrderLogger()

        self.order_books: Dict[str, OrderBook] = {}
        self.matching_engines: Dict[str, SimulatedMatchingEngine] = {}

        self.equity_curve: List[Tuple[datetime, float]] = []

    def run(self, max_steps: int | None = None):
        step = 0

        while True:
            if max_steps is not None and step >= max_steps:
                print("Backtester: max steps reached.")
                break

            ticks = self.data_gateway.get_next_tick()
            if ticks is None:
                print("Backtester: end of data.")
                break

            self._process_step(ticks)
            step += 1

        self._final_report()

    def _process_step(self, ticks: Dict[str, tuple]):
        for symbol, (_, _) in ticks.items():
            if symbol not in self.order_books:
                ob = OrderBook()
                me = SimulatedMatchingEngine(
                    order_book=ob,
                    order_logger=self.order_logger,
                    position_manager=self.pmgr,
                )
                self.order_books[symbol] = ob
                self.matching_engines[symbol] = me

        for symbol, (timestamp, bar) in ticks.items():
            engine = self.matching_engines[symbol]
            engine.check_open_orders(bar)

        for symbol, (timestamp, bar) in ticks.items():
            self.pm.update(symbol, bar)

        signals: List[Signal] = []

        for symbol, (ts, bar) in ticks.items():
            weighted_strats = self.strategies_by_symbol.get(symbol, [])
            if not weighted_strats:
                continue

            mdp = self._build_market_data_point(symbol, ts, bar)

            for ws in weighted_strats:
                out = ws.strategy.generate_signals(mdp)
                if not out:
                    continue
                for s in out:
                    s.strength *= ws.weight
                    signals.append(s)

        if signals:
            bundle = SignalBundle.from_signals(signals)

            any_symbol = next(iter(ticks))
            bar_ts = ticks[any_symbol][0]

            raw_orders = self.exec_mgr.generate_orders_from_bundle(
                bundle=bundle,
                timestamp=bar_ts,
            )

            accepted = []
            for o in raw_orders:
                cap = self.exec_mgr.cash
                pos_size = self.exec_mgr.get_position_qty(o.symbol)
                if self.order_mgr.validate_order(
                    order=o,
                    current_capital=cap,
                    current_position_size=pos_size,
                ):
                    accepted.append(o)

            for order in accepted:
                _, bar = ticks[order.symbol]
                engine = self.matching_engines[order.symbol]
                engine.process_order(order, bar)

        bar_timestamp = next(iter(ticks.values()))[0]
        equity = self.exec_mgr.get_portfolio_value()
        self.equity_curve.append((bar_timestamp.to_pydatetime(), equity))

    def _build_market_data_point(self, sym, ts, bar) -> MarketDataPoint:
        vol = bar.get("Volume", 0)
        q = int(vol if not pd.isna(vol) else 0)
        return MarketDataPoint(
            timestamp=ts.to_pydatetime(),
            symbol=sym,
            price=float(bar["Close"]),
            quantity=q,
        )

    def get_equity_curve_dataframe(self) -> pd.DataFrame:
        if not self.equity_curve:
            return pd.DataFrame(columns=["timestamp", "equity"])
        ts, vals = zip(*self.equity_curve)
        return pd.DataFrame({"timestamp": ts, "equity": vals}).set_index("timestamp")

    def get_trade_dataframe(self) -> pd.DataFrame:
        records: List[TradeRecord] = self.pmgr.trade_log
        if not records:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "symbol",
                    "side",
                    "quantity",
                    "price",
                    "realized_pnl",
                    "position_after",
                ]
            )
        data = [
            {
                "timestamp": tr.timestamp,
                "symbol": tr.symbol,
                "side": tr.side,
                "quantity": tr.quantity,
                "price": tr.price,
                "realized_pnl": tr.realized_pnl,
                "position_after": tr.position_after,
            }
            for tr in records
        ]
        df = pd.DataFrame(data).set_index("timestamp")
        return df.sort_index()

    def _final_report(self):
        eq_df = self.get_equity_curve_dataframe()
        trade_df = self.get_trade_dataframe()

        print("Backtester: end of data.")

        if not eq_df.empty:
            eq_series = eq_df["equity"]

            # total return
            start_val = eq_series.iloc[0]
            end_val = eq_series.iloc[-1]
            total_return = (end_val / start_val - 1.0) if start_val != 0 else 0.0

            # max drawdown
            running_max = eq_series.cummax()
            drawdown = (eq_series - running_max) / running_max
            max_dd = drawdown.min()

            # per period returns
            rets = eq_series.pct_change().dropna()

            ann_vol = None
            ann_sharpe = None

            if not rets.empty:
                per_period_vol = rets.std()
                per_period_ret = rets.mean()

                # infer bar frequency from timestamps
                diffs = eq_df.index.to_series().diff().dropna()
                if not diffs.empty:
                    dt_sec = diffs.dt.total_seconds().median()
                    seconds_per_year = 365.0 * 24.0 * 60.0 * 60.0
                    periods_per_year = seconds_per_year / dt_sec if dt_sec > 0 else 0.0
                else:
                    periods_per_year = 0.0

                if periods_per_year > 0.0:
                    ann_vol = per_period_vol * (periods_per_year ** 0.5)
                    if per_period_vol > 0.0:
                        ann_sharpe = (per_period_ret / per_period_vol) * (periods_per_year ** 0.5)

            print(f"Total return: {total_return:.2%}")
            print(f"Max drawdown: {max_dd:.2%}")

            if ann_vol is not None:
                print(f"Volatility (annualized): {ann_vol:.2%}")
            if ann_sharpe is not None:
                print(f"Sharpe ratio (rf=0): {ann_sharpe:.2f}")

        if not trade_df.empty:
            total_realized = trade_df["realized_pnl"].sum()
            avg_trade = trade_df["realized_pnl"].mean()
            wins = (trade_df["realized_pnl"] > 0).sum()
            losses = (trade_df["realized_pnl"] < 0).sum()
            num_trades = len(trade_df)
            win_rate = wins / num_trades if num_trades > 0 else 0.0

            print(f"Number of trades: {num_trades}")
            print(f"Total realized PnL: {total_realized:.2f}")
            print(f"Average trade PnL: {avg_trade:.2f}")
            print(f"Win rate: {win_rate:.2%}")
            print(f"Wins: {wins}, Losses: {losses}")

        print("Final cash:", self.pmgr.get_cash())
        print("Final positions:", self.pmgr.snapshot_positions())