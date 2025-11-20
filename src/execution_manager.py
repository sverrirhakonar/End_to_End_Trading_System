import json
from uuid import uuid4
from typing import Dict, Any, Optional, List

from src.price_manager import PriceManager
from src.signals import SignalBundle, AggregatedSymbolSignal
from src.order import Order  # adjust path if needed
from src.position_manager import PositionManager  # adjust path if needed


class ExecutionManager:
    """
    ExecutionManager

    - Reads and updates cash and positions through PositionManager
    - Loads execution and risk settings from JSON or dict
    - Consumes SignalBundle and produces Order objects
    """

    def __init__(
        self,
        price_manager: PriceManager,
        position_manager: PositionManager,
        starting_cash: Optional[float] = None,
        settings_path: Optional[str] = None,
        settings_dict: Optional[Dict[str, Any]] = None,
    ):
        self.pm = price_manager
        self.pmgr = position_manager

        # Optional explicit starting cash override
        if starting_cash is not None:
            self.pmgr.cash = starting_cash

        config = self._load_settings(settings_path, settings_dict)
        self._apply_settings(config)

    # ---------------------- factory from json ----------------------

    @classmethod
    def from_json(
        cls,
        price_manager: PriceManager,
        position_manager: PositionManager,
        json_path: str,
        starting_cash: Optional[float] = None,
    ) -> "ExecutionManager":
        with open(json_path, "r") as f:
            cfg = json.load(f)
        return cls(
            price_manager=price_manager,
            position_manager=position_manager,
            starting_cash=starting_cash,
            settings_path=None,
            settings_dict=cfg,
        )

    # ------------------------- settings ----------------------------

    def _load_settings(
        self,
        settings_path: Optional[str],
        settings_dict: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if settings_dict is not None:
            return settings_dict

        if settings_path is not None:
            with open(settings_path, "r") as f:
                return json.load(f)

        return {
            "max_positions": 10,
            "max_symbol_weight": 0.2,
            "min_position_value": 1_000.0,
            "min_trade_value": 500.0,
            "base_weight_per_symbol": 0.03,
            "weight_per_strength_unit": 0.02,
            "max_strength_multiplier": 2.0,
            "default_order_type": "MARKET",
        }

    def _apply_settings(self, cfg: Dict[str, Any]) -> None:
        self.max_positions: int = cfg.get("max_positions", 10)
        self.max_symbol_weight: float = cfg.get("max_symbol_weight", 0.2)
        self.min_position_value: float = cfg.get("min_position_value", 0.0)
        self.min_trade_value: float = cfg.get("min_trade_value", 0.0)

        self.base_weight_per_symbol: float = cfg.get("base_weight_per_symbol", 0.01)
        self.weight_per_strength_unit: float = cfg.get("weight_per_strength_unit", 0.0)
        self.max_strength_multiplier: float = cfg.get("max_strength_multiplier", 1.0)

        self.default_order_type: str = cfg.get("default_order_type", "MARKET")

    # ------------------------ portfolio helpers -------------------------

    @property
    def cash(self) -> float:
        return self.pmgr.get_cash()

    @cash.setter
    def cash(self, value: float) -> None:
        self.pmgr.cash = value

    def get_position_qty(self, symbol: str) -> float:
        pos = self.pmgr.get_position(symbol)
        return 0.0 if pos is None else pos.quantity

    def get_portfolio_value(self) -> float:
        """
        Use PositionManager and latest prices.
        """
        last_prices: Dict[str, float] = {}
        for sym in self.pmgr.positions.keys():
            last_prices[sym] = self.pm.get_latest_price(sym)
        return self.pmgr.portfolio_value(last_prices)

    def get_symbol_value(self, symbol: str) -> float:
        price = self.pm.get_latest_price(symbol)
        if price is None:
            return 0.0
        return self.pmgr.position_value(symbol, price)

    def get_symbol_weight(self, symbol: str) -> float:
        pv = self.get_portfolio_value()
        if pv <= 0:
            return 0.0
        return self.get_symbol_value(symbol) / pv

    def open_symbols(self) -> List[str]:
        return [
            sym
            for sym, pos in self.pmgr.positions.items()
            if pos.quantity != 0
        ]

    # ---------------- main entry: bundle -> orders ---------------------

    def generate_orders_from_bundle(
        self,
        bundle: SignalBundle,
        timestamp,
    ) -> List[Order]:
        orders: List[Order] = []

        best_buy = bundle.strongest_buy_symbol()
        if best_buy is not None:
            buy_order = self._build_buy_order(best_buy, timestamp)
            if buy_order is not None:
                orders.append(buy_order)

        best_sell = bundle.strongest_sell_symbol()
        if best_sell is not None:
            sell_order = self._build_sell_order(best_sell, timestamp)
            if sell_order is not None:
                orders.append(sell_order)

        return orders

    # ---------------- internal order building logic --------------------

    def _build_buy_order(
        self,
        agg: AggregatedSymbolSignal,
        timestamp,
    ) -> Optional[Order]:
        symbol = agg.symbol
        price = self.pm.get_latest_price(symbol)
        if price is None or price <= 0:
            return None

        pv = self.get_portfolio_value()
        current_weight = self.get_symbol_weight(symbol)
        current_positions = self.open_symbols()

        # limit total symbols
        if symbol not in current_positions and len(current_positions) >= self.max_positions:
            return None

        # do not exceed max symbol weight
        if current_weight >= self.max_symbol_weight:
            return None

        # strength -> target weight
        raw_weight = (
            self.base_weight_per_symbol
            + agg.total_buy_strength * self.weight_per_strength_unit
        )

        max_weight_from_strength = self.max_symbol_weight * self.max_strength_multiplier
        target_weight = min(raw_weight, self.max_symbol_weight, max_weight_from_strength)

        target_value = target_weight * pv
        current_value = self.get_symbol_value(symbol)
        incremental_value = max(0.0, target_value - current_value)

        if incremental_value < self.min_trade_value:
            return None

        desired_shares = int(incremental_value // price)
        if desired_shares <= 0:
            return None

        max_affordable_shares = int(self.cash // price)
        shares_to_buy = min(desired_shares, max_affordable_shares)

        if shares_to_buy <= 0:
            return None

        future_value = current_value + shares_to_buy * price
        if future_value < self.min_position_value:
            return None

        order_dict = {
            "order_id": str(uuid4()),
            "timestamp": timestamp,
            "symbol": symbol,
            "quantity": shares_to_buy,
            "price": price,
            "side": "BUY",
            "order_type": self.default_order_type,
        }
        return Order(order_dict)

    def _build_sell_order(
        self,
        agg: AggregatedSymbolSignal,
        timestamp,
    ) -> Optional[Order]:
        symbol = agg.symbol
        current_shares = self.get_position_qty(symbol)
        if current_shares <= 0:
            return None

        price = self.pm.get_latest_price(symbol)
        if price is None or price <= 0:
            return None

        quantity = current_shares

        order_dict = {
            "order_id": str(uuid4()),
            "timestamp": timestamp,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "side": "SELL",
            "order_type": self.default_order_type,
        }
        return Order(order_dict)

    # ---------------- backtest style fills using PositionManager ----------------

    def apply_market_fills(self, orders: List[Order], fee_per_order: float = 0.0) -> None:
        """
        Simple fill:
        - Only fills MARKET orders
        - Sets filled_* fields on the order
        - Delegates cash and position updates to PositionManager.update_from_fill
        """
        for order in orders:
            if order.order_type != "MARKET":
                continue
            if order.quantity is None or order.quantity <= 0:
                continue
            if order.symbol is None or order.side is None:
                continue

            # In backtest we assume we fill at the order price
            order.filled_price = order.price
            order.filled_quantity = order.quantity
            order.filled_timestamp = order.timestamp

            # Let PositionManager handle cash and position updates
            self.pmgr.update_from_fill(order, fee=fee_per_order)

            order.status = "Filled"
