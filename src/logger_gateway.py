import csv
import os
import datetime
from src.order import Order

class OrderLogger:
    """ Logging Gateway for Backtester """

    def __init__(self, log_dir: str = 'logs'):
        """ Initializes the logger and the log file. """
        self.log_dir = log_dir
        
        # Create a unique filename for this backtest run
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filepath = os.path.join(self.log_dir, f"order_log_{timestamp}.csv")
        
        # These are the columns for our CSV log book
        self.fieldnames = [
            'timestamp',    # When did the event happen
            'event_type',   # e.g., 'SENT', 'FILLED', 'REJECTED', 'CANCELLED'
            'order_id',     # The unique ID of the order
            'side',         # 'BUY' or 'SELL'
            'type',         # 'MARKET' or 'LIMIT'
            'qty',          # Order quantity
            'price',        # Order price (or 'None' for market)
            'fill_qty',     # How much was filled (for 'FILLED' events)
            'fill_price',   # At what price (for 'FILLED' events)
            'reason'        # e.g., "Risk check failed"
        ]
        
        self._initialize_log_file()
        print(f"OrderLogger: Logging events to {self.log_filepath}")

    def _initialize_log_file(self):
        """ Creates the log directory and writes the CSV header
        if the file doesn't exist. """
        try:
            # Create the 'logs' directory if it's not there
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir)
                
            # Open the file in 'write' mode (w) to create it
            # and write the header.
            with open(self.log_filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
                
        except Exception as e:
            print(f"OrderLogger: FATAL Error initializing log file: {e}")
            raise

    def log_event(self, event_type: str, order: Order, tick_timestamp, reason: str = "", fill_qty: int = 0, fill_price: float = 0.0):
        """ Writes a single event to the CSV log file.
        This is the main function called by the backtester. 
        
        Args:
            event_type: e.g., 'SENT', 'FILLED', 'REJECTED', 'CANCELLED'
            order: Order object containing order details
            tick_timestamp: Timestamp of the market tick that triggered this event
            reason: Optional reason string (for rejections, cancellations)
            fill_qty: Quantity filled (for FILLED events)
            fill_price: Price filled at (for FILLED events)
        """
        try:
            # 1. Use the tick timestamp that triggered the event
            log_time = tick_timestamp
            
            # 2. Build the row to write using Order object attributes
            log_row = {
                'timestamp': log_time,
                'event_type': event_type,
                'order_id': order.order_id,
                'side': order.side if hasattr(order, 'side') else 'N/A',
                'type': order.order_type,
                'qty': order.quantity,
                'price': order.price,
                'fill_qty': fill_qty,
                'fill_price': fill_price,
                'reason': reason
            }
            
            # 3. Open the file in "append" mode (a) and write the row
            with open(self.log_filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(log_row)
                
        except Exception as e:
            print(f"OrderLogger: Error writing to log: {e}")