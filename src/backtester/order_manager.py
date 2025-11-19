from collections import deque
import pandas as pd

class OrderManager:
    """
    Validates and records orders *before* execution.
    It checks:
    1. Capital Sufficiency
    2. Risk Limits (Orders per minute)
    3. Position Limits (Total shares held)
    """

    def __init__(self, initial_capital: float, max_orders_per_minute: int, max_position_size: int):

        self.capital = initial_capital
        self.max_orders_per_minute = max_orders_per_minute
        self.max_position_size = max_position_size
        self.order_timestamps = deque()
        

    def validate_order(self, order: dict, current_capital: float, current_position_size: int):
        
        # --- 1. Check for Orders Per Minute ---
        new_time = order['timestamp']
        
        # more than 1 minute older than the new order.
        one_minute_ago = new_time - pd.Timedelta('1 minute')
        while self.order_timestamps and self.order_timestamps[0] < one_minute_ago:
            self.order_timestamps.popleft()
            
        # Now, check if we're still over the limit
        if len(self.order_timestamps) >= self.max_orders_per_minute:
            print(f"Risk Check FAILED: Too many orders per minute. (Limit: {self.max_orders_per_minute})")
            return False
            
        # --- 2. Check for Capital Sufficiency ---
        required_capital = order['qty'] * order['price']
        
        if required_capital > current_capital and order['side'] == 'BUY':
            print(f"Risk Check FAILED: Not enough capital. (Need: ${required_capital:.2f}, Have: ${current_capital:.2f})")
            return False
            
        # --- 3. Check for Position Limits ---
        if order['side'] == 'BUY':
            new_position = current_position_size + order['qty']
            if new_position > self.max_position_size:
                print(f"Risk Check FAILED: Order would exceed max position size. (Limit: {self.max_position_size})")
                return False
        else: # 'SELL'
            new_position = current_position_size - order['qty']
            # We assume we can't go "short" (negative shares)
            if new_position < 0:
                print(f"Risk Check FAILED: Cannot sell more shares than you own. (Have: {current_position_size}, Sell: {order['qty']})")
                return False

        # --- If all checks pass ---
        print(f"Risk Check PASSED: Order {order['side']} {order['qty']} @ {order['price']:.2f}")

        self.order_timestamps.append(new_time)
        return True