# src/logger_gateway.py

import csv
import os
import datetime

from src.order import Order
from src.signals import Signal   # <- THIS IMPORT IS IMPORTANT


class OrderLogger:
    """ Logging Gateway for Backtester """

    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = log_dir

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filepath = os.path.join(self.log_dir, f"order_log_{timestamp}.csv")

        self.fieldnames = [
            'timestamp',
            'event_type',
            'order_id',
            'side',
            'type',
            'qty',
            'price',
            'fill_qty',
            'fill_price',
            'reason'
        ]

        self._initialize_log_file()
        print(f"OrderLogger: Logging events to {self.log_filepath}")

    def _initialize_log_file(self):
        try:
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir)

            with open(self.log_filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

        except Exception as e:
            print(f"OrderLogger: FATAL Error initializing log file: {e}")
            raise

    def log_event(
        self,
        event_type: str,
        order: Order,
        tick_timestamp,
        reason: str = "",
        fill_qty: int = 0,
        fill_price: float = 0.0
    ):
        try:
            log_time = tick_timestamp

            log_row = {
                'timestamp': log_time,
                'event_type': event_type,
                'order_id': order.order_id,
                'side': getattr(order, 'side', 'N/A'),
                'type': getattr(order, 'order_type', 'N/A'),
                'qty': getattr(order, 'quantity', None),
                'price': getattr(order, 'price', None),
                'fill_qty': fill_qty,
                'fill_price': fill_price,
                'reason': reason
            }

            with open(self.log_filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(log_row)

        except Exception as e:
            print(f"OrderLogger: Error writing to log: {e}")


class SignalLogger:
    """Logs raw strategy signals to a separate CSV."""

    def __init__(self, log_dir: str = 'logs'):
        self.log_dir = log_dir

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filepath = os.path.join(self.log_dir, f"signal_log_{timestamp}.csv")

        self.fieldnames = [
            'timestamp',
            'symbol',
            'side',
            'strength',
            'source',
        ]

        self._initialize_log_file()
        print(f"SignalLogger: Logging signals to {self.log_filepath}")

    def _initialize_log_file(self):
        try:
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir)

            with open(self.log_filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

        except Exception as e:
            print(f"SignalLogger: FATAL Error initializing log file: {e}")
            raise

    def log_signal(self, timestamp, signal: Signal):
        try:
            row = {
                'timestamp': timestamp,
                'symbol': signal.symbol,
                'side': signal.side,
                'strength': signal.strength,
                'source': signal.source,
            }

            with open(self.log_filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(row)

        except Exception as e:
            print(f"SignalLogger: Error writing signal to log: {e}")
