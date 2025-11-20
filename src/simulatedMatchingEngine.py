# src/simulatedMatchingEngine.py

import random
import pandas as pd

from src.order_book import OrderBook
from src.logger_gateway import OrderLogger
from src.order import Order
from src.position_manager import PositionManager


class SimulatedMatchingEngine:
    def __init__(
        self,
        order_book: OrderBook,
        order_logger: OrderLogger,
        position_manager: PositionManager,
        fee_per_order: float = 0.0,
    ):
        """Initializes the engine."""
        self.order_book = order_book
        self.order_logger = order_logger
        self.position_manager = position_manager
        self.fee_per_order = fee_per_order

        # Configurable randomness
        self.fill_reject_chance = 0.05
        self.partial_fill_chance = 0.10

        print("SimulatedMatchingEngine: Initialized.")

    # ------------------------------------------------------------------
    # Public entrypoints
    # ------------------------------------------------------------------
    def process_order(self, order: Order, current_tick: "pd.Series"):
        """Process a new validated order."""
        fills = []

        # 1. Random rejection
        if random.random() < self.fill_reject_chance:
            print("MatchingEngine: Order randomly REJECTED.")
            self.order_logger.log_event(
                event_type="REJECTED",
                order=order,
                tick_timestamp=current_tick.name,
                reason="Random engine rejection",
            )
            order.status = "Rejected"
            return fills

        # 2. Type dependent handling
        if order.order_type == "MARKET":
            filled = self._fill_market_order(order, current_tick)
            if filled is not None:
                fills.append(filled)

        elif order.order_type == "LIMIT":
            fills.extend(self._process_limit_order(order, current_tick))

        return fills

    def check_open_orders(self, current_tick: "pd.Series"):
        """Check waiting limit orders in the book vs new tick."""
        fills = []

        # 1. Waiting BUY orders
        while True:
            best_bid_order = self.order_book.get_best_bid_order()
            if not best_bid_order:
                break

            if best_bid_order.price >= current_tick["Low"]:
                print(
                    f"MatchingEngine: Waiting BUY order {best_bid_order.order_id} FILLED."
                )
                popped_order = self.order_book.pop_best_bid_order()
                fill_price = popped_order.price
                fill_qty = popped_order.quantity

                filled = self._apply_fill(
                    order=popped_order,
                    current_tick=current_tick,
                    fill_qty=fill_qty,
                    fill_price=fill_price,
                    event_type="FILLED",
                )
                fills.append(filled)
            else:
                break

        # 2. Waiting SELL orders
        while True:
            best_ask_order = self.order_book.get_best_ask_order()
            if not best_ask_order:
                break

            if best_ask_order.price <= current_tick["High"]:
                print(
                    f"MatchingEngine: Waiting SELL order {best_ask_order.order_id} FILLED."
                )
                popped_order = self.order_book.pop_best_ask_order()
                fill_price = popped_order.price
                fill_qty = popped_order.quantity

                filled = self._apply_fill(
                    order=popped_order,
                    current_tick=current_tick,
                    fill_qty=fill_qty,
                    fill_price=fill_price,
                    event_type="FILLED",
                )
                fills.append(filled)
            else:
                break

        return fills

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fill_market_order(self, order: Order, current_tick: "pd.Series") -> Order | None:
        """Fill a market order at Close, possibly partially."""
        fill_price = current_tick["Close"]
        fill_qty = order.quantity

        if random.random() < self.partial_fill_chance:
            fill_qty = int(order.quantity * random.uniform(0.1, 0.9))
            fill_qty = max(1, fill_qty)
            print(
                f"MatchingEngine: Order partially filled ({fill_qty} / {order.quantity})"
            )

        return self._apply_fill(
            order=order,
            current_tick=current_tick,
            fill_qty=fill_qty,
            fill_price=fill_price,
            event_type="FILLED",
        )

    def _process_limit_order(self, order: Order, current_tick: "pd.Series"):
        """Handle a new limit order."""
        fills: list[Order] = []
        can_fill_now = False

        if order.side == "BUY":
            if order.price >= current_tick["Low"]:
                can_fill_now = True
        elif order.side == "SELL":
            if order.price <= current_tick["High"]:
                can_fill_now = True

        if can_fill_now:
            print("MatchingEngine: Limit order filled immediately.")
            filled = self._fill_market_order(order, current_tick)
            if filled is not None:
                fills.append(filled)
        else:
            print("MatchingEngine: Limit order added to OrderBook to wait.")
            order_id = self.order_book.add_order(order)
            order.order_id = order_id
            order.status = "Placed"

            self.order_logger.log_event(
                event_type="PLACED",
                order=order,
                tick_timestamp=current_tick.name,
                reason="Placed in book to wait",
            )

        return fills

    def _apply_fill(
        self,
        order: Order,
        current_tick: "pd.Series",
        fill_qty: int,
        fill_price: float,
        event_type: str,
    ) -> Order:
        """Common fill logic: log and update positions."""
        order.filled_quantity = fill_qty
        order.filled_price = fill_price
        order.filled_timestamp = current_tick.name
        order.status = "Filled"

        self.order_logger.log_event(
            event_type=event_type,
            order=order,
            tick_timestamp=current_tick.name,
            fill_qty=fill_qty,
            fill_price=fill_price,
        )

        # Update portfolio through PositionManager
        self.position_manager.update_from_fill(order, fee=self.fee_per_order)

        return order
