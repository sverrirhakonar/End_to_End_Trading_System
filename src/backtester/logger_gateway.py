import csv
import os
import datetime

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

    def log_event(self, event_type: str, order: dict, reason: str = "", fill_qty: int = 0, fill_price: float = 0.0):
        """ Writes a single event to the CSV log file.
        This is the main function called by the backtester. """
        try:
            # 1. Get the current time for the log entry
            log_time = datetime.datetime.now()
            
            # 2. Build the row to write
            log_row = {
                'timestamp': log_time,
                'event_type': event_type,
                'order_id': order.get('id', 'N/A'), # Use .get() for safety
                'side': order.get('side'),
                'type': order.get('type'),
                'qty': order.get('qty'),
                'price': order.get('price'),
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