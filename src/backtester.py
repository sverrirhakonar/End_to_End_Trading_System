from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import sys
import os
from contextlib import contextmanager

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
from src.logger_gateway import OrderLogger, SignalLogger
from model.models import MarketDataPoint


@contextmanager
def suppress_all_output():
    """
    Temporarily redirect stdout and stderr to os.devnull.
    Use this to silence all prints that happen inside the block.
    """
    devnull = open(os.devnull, "w")
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.stdout = devnull
        sys.stderr = devnull
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        devnull.close()


@dataclass
class WeightedStrategy:
    strategy: Strategy
    weight: float = 1.0


class Backtester:
    """
    Full backtest loop including:
      - multi symbol data via MultiHistoricalDataGateway
      - PriceManager indicators
      - multiple strategies per symbol with weights
      - signal aggregation
      - ExecutionManager sizing
      - OrderManager risk checks
      - per symbol OrderBook and SimulatedMatchingEngine
      - PositionManager updates on fill
      - equity curve, trade log, stats
      - prints settings and performance summary at the end

    If suppress_output is True, all prints during run() are muted.
    """

    def __init__(
        self,
        config_path: str,
        price_manager: PriceManager,
        position_manager: PositionManager,
        strategies_by_symbol: Dict[str, List[WeightedStrategy]],
        execution_manager: ExecutionManager,
        order_manager: OrderManager,
        order_logger: OrderLogger,
        signal_logger: SignalLogger,
        market_cfg,
        strat_cfg,
        exec_cfg,
        init_portfolio_cfg,
        order_mgr_params,
        suppress_output: bool = False,
    ):
        self.data_gateway = MultiHistoricalDataGateway(config_path)
        self.pm = price_manager
        self.pmgr = position_manager
        self.strategies_by_symbol = strategies_by_symbol
        self.exec_mgr = execution_manager
        self.order_mgr = order_manager

        self.order_logger = order_logger
        self.signal_logger = signal_logger

        # configs to show at the end
        self.market_cfg = market_cfg
        self.strat_cfg = strat_cfg
        self.exec_cfg = exec_cfg
        self.init_portfolio_cfg = init_portfolio_cfg
        self.order_mgr_params = order_mgr_params

        self.order_books: Dict[str, OrderBook] = {}
        self.matching_engines: Dict[str, SimulatedMatchingEngine] = {}

        # list of (timestamp, equity)
        self.equity_curve: List[Tuple[datetime, float]] = []

        # if True, suppress all prints during run()
        self.suppress_output = suppress_output

    # public entry point

    def run(self, max_steps: int | None = None):
        """
        Run the backtest.
        If self.suppress_output is True, printing to stdout and stderr from
        this call and anything it invokes will be muted.
        """
        if self.suppress_output:
            with suppress_all_output():
                self._run_internal(max_steps)
        else:
            self._run_internal(max_steps)

    def _run_internal(self, max_steps: int | None = None):
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
        # lazily create order book and matching engine per symbol
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

        # 1 check existing open limit orders against new tick
        for symbol, (timestamp, bar) in ticks.items():
            engine = self.matching_engines[symbol]
            engine.check_open_orders(bar)

        # 2 update price history
        for symbol, (timestamp, bar) in ticks.items():
            self.pm.update(symbol, bar)

        # 3 run strategies and collect signals
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
                    # log weighted signal
                    self.signal_logger.log_signal(timestamp=ts, signal=s)

        # 4 bundle signals and have ExecutionManager create orders
        if signals:
            bundle = SignalBundle.from_signals(signals)

            any_symbol = next(iter(ticks))
            bar_ts = ticks[any_symbol][0]

            raw_orders = self.exec_mgr.generate_orders_from_bundle(
                bundle=bundle,
                timestamp=bar_ts,
            )

            # 5 risk checks in OrderManager
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

            # 6 route accepted orders to symbol specific matching engines
            for order in accepted:
                _, bar = ticks[order.symbol]
                engine = self.matching_engines[order.symbol]
                engine.process_order(order, bar)

        # 7 record equity for this bar
        bar_timestamp = next(iter(ticks.values()))[0]
        equity = self.exec_mgr.get_portfolio_value()
        self.equity_curve.append((bar_timestamp.to_pydatetime(), equity))

    # helpers

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

    # settings printout

    def _print_run_settings(self):
        market_cfg = self.market_cfg
        strat_cfg = self.strat_cfg
        exec_cfg = self.exec_cfg
        init_portfolio_cfg = self.init_portfolio_cfg
        order_mgr_params = self.order_mgr_params

        print("=" * 70)
        print("BACKTEST CONFIGURATION")
        print("=" * 70)

        # market data sources
        print("\nMarket data sources:")
        print(f"{'Ticker':10s} {'CSV path':40s} {'Timeframe':10s} {'Bar':6s}")
        print("-" * 70)
        for entry in market_cfg:
            ticker = str(entry.get("ticker", ""))
            path = str(entry.get("csv_filepath", ""))[:38]
            timeframe = str(entry.get("timeframe", ""))
            bar = str(entry.get("bar", ""))
            print(f"{ticker:10s} {path:40s} {timeframe:10s} {bar:6s}")

        # initial portfolio
        print("\nInitial portfolio:")
        cash = init_portfolio_cfg.get("cash", 0.0)
        positions = init_portfolio_cfg.get("positions", {})
        print(f"{'Starting cash:':20s} {cash:12.2f}")
        if positions:
            print(f"{'Symbol':10s} {'Quantity':>10s} {'Avg price':>12s}")
            print("-" * 40)
            for sym, p in positions.items():
                qty = p.get("quantity", 0.0)
                avg = p.get("avg_price", 0.0)
                print(f"{sym:10s} {qty:10.2f} {avg:12.4f}")
        else:
            print("No starting positions.")

        # execution settings
        print("\nExecution settings (ExecutionManager):")
        print(f"{'max_positions:':25s} {exec_cfg.get('max_positions', 0)}")
        print(
            f"{'max_symbol_weight:':25s} "
            f"{exec_cfg.get('max_symbol_weight', 0.0):.2f}"
        )
        print(
            f"{'min_position_value:':25s} "
            f"{exec_cfg.get('min_position_value', 0.0):.2f}"
        )
        print(
            f"{'min_trade_value:':25s} "
            f"{exec_cfg.get('min_trade_value', 0.0):.2f}"
        )
        print(
            f"{'base_weight_per_symbol:':25s} "
            f"{exec_cfg.get('base_weight_per_symbol', 0.0):.3f}"
        )
        print(
            f"{'weight_per_strength_unit:':25s} "
            f"{exec_cfg.get('weight_per_strength_unit', 0.0):.3f}"
        )
        print(
            f"{'max_strength_multiplier:':25s} "
            f"{exec_cfg.get('max_strength_multiplier', 0.0):.2f}"
        )
        print(f"{'default_order_type:':25s} {exec_cfg.get('default_order_type', '')}")

        # order manager risk
        print("\nRisk settings (OrderManager):")
        print(
            f"{'max_orders_per_minute:':25s} "
            f"{order_mgr_params.get('max_orders_per_minute', 0)}"
        )
        print(
            f"{'max_position_size:':25s} "
            f"{order_mgr_params.get('max_position_size', 0)}"
        )

        # strategies
        print("\nStrategies per symbol:")
        print(f"{'Symbol':8s} {'Strategy':28s} {'Weight':>8s} {'Params'}")
        print("-" * 70)
        for symbol, strat_list in strat_cfg.items():
            for entry in strat_list:
                class_name = entry.get("class", "")
                weight = entry.get("weight", 1.0)
                params = entry.get("params", {})
                params_str = ", ".join(f"{k}={v}" for k, v in params.items())
                print(f"{symbol:8s} {class_name:28s} {weight:8.2f} {params_str}")
        print("=" * 70)

    # final stats
    def _final_report(self):
        # settings first
        self._print_run_settings()

        eq_df = self.get_equity_curve_dataframe()
        trade_df = self.get_trade_dataframe()

        print("\n" + "=" * 70)
        print("BACKTEST PERFORMANCE SUMMARY")
        print("=" * 70)

        if not eq_df.empty:
            eq_series = eq_df["equity"]

            start_val = eq_series.iloc[0]
            end_val = eq_series.iloc[-1]
            total_return = (end_val / start_val - 1.0) if start_val != 0 else 0.0

            running_max = eq_series.cummax()
            drawdown = (eq_series - running_max) / running_max
            max_dd = drawdown.min()

            rets = eq_series.pct_change().dropna()

            ann_vol = None
            ann_sharpe = None

            if not rets.empty:
                per_period_vol = rets.std()
                per_period_ret = rets.mean()

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
                        ann_sharpe = (
                            per_period_ret / per_period_vol
                        ) * (periods_per_year ** 0.5)

            print(f"{'Start equity:':25s} {start_val:12.2f}")
            print(f"{'End equity:':25s} {end_val:12.2f}")
            print(f"{'Total return:':25s} {total_return:11.2%}")
            print(f"{'Max drawdown:':25s} {max_dd:11.2%}")

            if ann_vol is not None:
                print(f"{'Volatility (annualized):':25s} {ann_vol:11.2%}")
            if ann_sharpe is not None:
                print(f"{'Sharpe ratio (rf=0):':25s} {ann_sharpe:11.2f}")
        else:
            print("No equity data recorded.")

        print("-" * 70)

        if not trade_df.empty:
            cum = trade_df["realized_pnl"].astype(float)

            if len(cum) > 1 and cum.abs().sum() > cum.abs().iloc[-1] * 2:
                per_trade = cum.diff().fillna(cum.iloc[0])
            else:
                per_trade = cum

            total_realized = per_trade.sum()
            avg_trade = per_trade.mean()
            wins = (per_trade > 0).sum()
            losses = (per_trade < 0).sum()
            num_trades = len(per_trade)
            win_rate = wins / num_trades if num_trades > 0 else 0.0

            print(f"{'Number of trades:':25s} {num_trades:12d}")
            print(f"{'Total realized PnL:':25s} {total_realized:12.2f}")
            print(f"{'Average trade PnL:':25s} {avg_trade:12.2f}")
            print(f"{'Win rate:':25s} {win_rate:11.2%}")
            print(f"{'Wins:':25s} {wins:12d}")
            print(f"{'Losses:':25s} {losses:12d}")
        else:
            print("No trades recorded.")

        print("-" * 70)
        print(f"{'Final cash:':25s} {self.pmgr.get_cash():12.2f}")
        print(f"{'Final positions:':25s} {self.pmgr.snapshot_positions()}")
        print("=" * 70)
