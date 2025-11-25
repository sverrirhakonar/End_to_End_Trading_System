# order_manager.py

from collections import deque
import pandas as pd
from src.order import Order
from src.logger_gateway import OrderLogger


class OrderManager:
    """
    Validates and records orders *before* execution.
    It checks:
    1. Capital Sufficiency
    2. Risk Limits (Orders per minute)
    3. Position Limits (Total shares held)
    """

    def __init__(
        self,
        initial_capital: float,
        max_orders_per_minute: int,
        max_position_size: int,
        order_logger: OrderLogger | None = None,
    ):
        self.capital = initial_capital
        self.max_orders_per_minute = max_orders_per_minute
        self.max_position_size = max_position_size
        self.order_timestamps = deque()

        self.order_logger = order_logger

    def _log_risk_event(self, event_type: str, order: Order, reason: str):
        if self.order_logger is None:
            return
        # use the order timestamp as "tick_timestamp" for risk events
        self.order_logger.log_event(
            event_type=event_type,
            order=order,
            tick_timestamp=order.timestamp,
            reason=reason,
        )

    def validate_order(self, order: Order, current_capital: float, current_position_size: int):
        new_time = order.timestamp

        one_minute_ago = new_time - pd.Timedelta('1 minute')
        while self.order_timestamps and self.order_timestamps[0] < one_minute_ago:
            self.order_timestamps.popleft()

        if len(self.order_timestamps) >= self.max_orders_per_minute:
            reason = f"Too many orders per minute. (Limit: {self.max_orders_per_minute})"
            #print(f"Risk Check FAILED: {reason}")
            self._log_risk_event("RISK_FAIL", order, reason)
            return False

        required_capital = order.quantity * order.price

        if required_capital > current_capital and order.side == 'BUY':
            reason = (
                f"Not enough capital. "
                f"(Need: ${required_capital:.2f}, Have: ${current_capital:.2f})"
            )
            #print(f"Risk Check FAILED: {reason}")
            self._log_risk_event("RISK_FAIL", order, reason)
            return False

        if order.side == 'BUY':
            new_position = current_position_size + order.quantity
            if new_position > self.max_position_size:
                reason = f"Order would exceed max position size. (Limit: {self.max_position_size})"
                #print(f"Risk Check FAILED: {reason}")
                self._log_risk_event("RISK_FAIL", order, reason)
                return False
        else:
            new_position = current_position_size - order.quantity
            if new_position < 0:
                reason = (
                    f"Cannot sell more shares than you own. "
                    f"(Have: {current_position_size}, Sell: {order.quantity})"
                )
                #print(f"Risk Check FAILED: {reason}")
                self._log_risk_event("RISK_FAIL", order, reason)
                return False

        # passed all checks
        #print(f"Risk Check PASSED: Order {order.side} {order.quantity} @ {order.price:.2f}")
        self.order_timestamps.append(new_time)
        self._log_risk_event("RISK_PASS", order, "All risk checks passed")
        return True
