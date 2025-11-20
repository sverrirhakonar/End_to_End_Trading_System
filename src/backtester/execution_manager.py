import json
from uuid import uuid4
from typing import Dict, Any, Optional, List

from src.backtester.price_manager import PriceManager
from src.backtester.signals import SignalBundle, AggregatedSymbolSignal
from src.backtester.order import Order


class ExecutionManager:
    """
    ExecutionManager

    - Holds portfolio state (cash + positions)
    - Loads execution settings from JSON or dict
    - Consumes SignalBundle and produces Order objects
    """
    # Initialization
    def __init__(
        self,
        price_manager: PriceManager,
        starting_cash: float = 100_000.0,
        settings_path: Optional[str] = None,
        settings_dict: Optional[Dict[str, Any]] = None,
    ):
        self.pm = price_manager
        self.cash: float = starting_cash
        self.positions: Dict[str, int] = {}

        config = self._load_settings(settings_path, settings_dict)
        self._apply_settings(config)

    # Factory helper for JSON configs
    @classmethod
    def from_json(
        cls,
        price_manager: PriceManager,
        json_path: str,
        starting_cash: float = 100_000.0,
    ) -> "ExecutionManager":
        with open(json_path, "r") as f:
            cfg = json.load(f)
        return cls(
            price_manager=price_manager,
            starting_cash=starting_cash,
            settings_path=None,
            settings_dict=cfg,
        )

    # Settings helpers

    def _load_settings(
        self,
        settings_path: Optional[str],
        settings_dict: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Load settings from a dict or JSON path, or fall back to defaults.
        """
        if settings_dict is not None:
            return settings_dict

        if settings_path is not None:
            with open(settings_path, "r") as f:
                return json.load(f)

        # Default settings if nothing is provided
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
        """
        Store configuration values as attributes on this instance.
        """
        # risk and sizing
        self.max_positions: int = cfg.get("max_positions", 10)
        self.max_symbol_weight: float = cfg.get("max_symbol_weight", 0.2)
        self.min_position_value: float = cfg.get("min_position_value", 0.0)
        self.min_trade_value: float = cfg.get("min_trade_value", 0.0)

        self.base_weight_per_symbol: float = cfg.get("base_weight_per_symbol", 0.01)
        self.weight_per_strength_unit: float = cfg.get("weight_per_strength_unit", 0.0)
        self.max_strength_multiplier: float = cfg.get("max_strength_multiplier", 1.0)

        # execution style
        self.default_order_type: str = cfg.get("default_order_type", "MARKET")

    # Helpers

    def get_position(self, symbol: str) -> int:
        return self.positions.get(symbol, 0)

    def get_portfolio_value(self) -> float:
        """
        Current portfolio value = cash + sum(position * last_price).
        """
        value = self.cash
        for symbol, shares in self.positions.items():
            price = self.pm.get_latest_price(symbol)
            if price is not None:
                value += shares * price
        return value

    def get_symbol_value(self, symbol: str) -> float:
        shares = self.get_position(symbol)
        price = self.pm.get_latest_price(symbol)
        if price is None:
            return 0.0
        return shares * price

    def get_symbol_weight(self, symbol: str) -> float:
        """
        Fraction of total portfolio in a given symbol.
        """
        pv = self.get_portfolio_value()
        if pv <= 0:
            return 0.0
        return self.get_symbol_value(symbol) / pv

    def open_symbols(self) -> List[str]:
        """
        Symbols with a nonzero position.
        """
        return [s for s, qty in self.positions.items() if qty != 0]

    # Order generation

    def generate_orders_from_bundle(
        self,
        bundle: SignalBundle,
        timestamp,
    ) -> List[Order]:
        """
        Use aggregated signals plus settings to create Orders.
        In this basic version, we create at most one buy and one sell per step.
        """
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

    # Order logic to build orders from bundled signals

    def _build_buy_order(
        self,
        agg: AggregatedSymbolSignal,
        timestamp,
    ) -> Optional[Order]:
        """
        Decide whether to buy a symbol and how much, based on:
        - aggregated buy strength
        - current portfolio value and symbol weight
        - JSON driven constraints (max_positions, min_trade_value, etc)
        """
        symbol = agg.symbol
        price = self.pm.get_latest_price(symbol)
        if price is None or price <= 0:
            return None

        pv = self.get_portfolio_value()
        current_weight = self.get_symbol_weight(symbol)
        current_positions = self.open_symbols()

        # Do not open more distinct symbols than allowed
        if symbol not in current_positions and len(current_positions) >= self.max_positions:
            return None

        # Respect max weight per symbol
        if current_weight >= self.max_symbol_weight:
            return None

        # Determine target weight from strength
        raw_weight = (
            self.base_weight_per_symbol
            + agg.total_buy_strength * self.weight_per_strength_unit
        )

        max_weight_from_strength = self.max_symbol_weight * self.max_strength_multiplier
        target_weight = min(raw_weight, self.max_symbol_weight, max_weight_from_strength)

        # Compute how much additional value we want
        target_value = target_weight * pv
        current_value = self.get_symbol_value(symbol)
        incremental_value = max(0.0, target_value - current_value)

        # Enforce minimum trade size
        if incremental_value < self.min_trade_value:
            return None

        # Convert value to shares and check cash
        desired_shares = int(incremental_value // price)
        if desired_shares <= 0:
            return None

        max_affordable_shares = int(self.cash // price)
        shares_to_buy = min(desired_shares, max_affordable_shares)

        if shares_to_buy <= 0:
            return None

        # Check resulting position against min_position_value
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
        """
        Simple rule: if there is a strong sell aggregate, close the full position.
        Can be extended to partial exits based on agg.total_sell_strength.
        """
        symbol = agg.symbol
        current_shares = self.get_position(symbol)
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