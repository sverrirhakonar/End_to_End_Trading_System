import heapq
import uuid
from src.order import Order

class OrderBook:

    def __init__(self):
        """ Initializes the order book. """
        # (price, timestamp, order)
        self.asks = []  # Min-heap
        # (-price, timestamp, order)
        self.bids = []  # Max-heap (using negative prices)
        
        self.orders = {} # Fast lookup for cancellation
        print("OrderBook (Waiting Room): Initialized.")

    def add_order(self, order: Order):
        """ Adds a new, open order to the book. """
        # 1. Set order ID if not already set
        if order.order_id is None:
            order.order_id = str(uuid.uuid4())
        order.is_cancelled = False
        
        # 2. Store the order for fast lookup
        self.orders[order.order_id] = order
        
        # 3. Add the order to the correct heap
        if order.side == 'BUY':
            heap_item = (-order.price, order.timestamp, order)
            heapq.heappush(self.bids, heap_item)
        else:
            heap_item = (order.price, order.timestamp, order)
            heapq.heappush(self.asks, heap_item)
                
        return order.order_id

    def cancel_order(self, order_id):
        """ Marks an order for cancellation ("lazy cancellation"). """
        if order_id in self.orders:
            self.orders[order_id].is_cancelled = True
            print(f"OrderBook: Order {order_id} marked for cancellation.")
            return True
        else:
            print(f"OrderBook: Error - Cannot cancel. Order {order_id} not found.")
            return False

    def modify_order(self, order_id, new_details):
        """ Modifies an order by cancelling the old one and adding a new one. """
        if self.cancel_order(order_id):
            # Get old order and create a new one with modifications
            old_order = self.orders[order_id]
            new_order_dict = {
                'side': old_order.side,
                'quantity': new_details.get('quantity', old_order.quantity),
                'price': new_details.get('price', old_order.price),
                'order_type': old_order.order_type,
                'symbol': old_order.symbol,
                'timestamp': old_order.timestamp
            }
            new_order = Order(new_order_dict)
            return self.add_order(new_order)
        else:
            return None # Old order not found

    def get_best_bid_order(self):
        """Returns the full order at the highest bid (or None)."""
        while self.bids:
            price_neg, _, order = self.bids[0]
            if order.is_cancelled:
                heapq.heappop(self.bids) # Clean up cancelled orders
                continue
            return order
        return None

    def get_best_ask_order(self):
        """Returns the full order at the lowest ask (or None)."""
        while self.asks:
            price, _, order = self.asks[0]
            if order.is_cancelled:
                heapq.heappop(self.asks) # Clean up cancelled orders
                continue
            return order
        return None
        
    def pop_best_bid_order(self):
        """Removes and returns the best bid order."""
        while self.bids:
            price_neg, _, order = heapq.heappop(self.bids)
            if order.is_cancelled:
                continue
            del self.orders[order.order_id]
            return order
        return None
        
    def pop_best_ask_order(self):
        """Removes and returns the best ask order."""
        while self.asks:
            price, _, order = heapq.heappop(self.asks)
            if order.is_cancelled:
                continue
            del self.orders[order.order_id]
            return order
        return None