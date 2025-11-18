import heapq
import time
import uuid

class OrderBook:

    def __init__(self):
        """
        Initializes the order book.
        - self.bids: A max-heap for buy orders. (Stores (-price, timestamp, order))
        - self.asks: A min-heap for sell orders. (Stores (price, timestamp, order))
        - self.orders: A dictionary for fast lookup and cancellation.
        """
        # (price, timestamp, order)
        self.asks = []  # Min-heap
        # (-price, timestamp, order)
        self.bids = []  # Max-heap (using negative prices)
        
        self.orders = {} # Fast lookup for cancellation
        print("OrderBook (Waiting Room): Initialized.")

    def add_order(self, order_details):
        """
        Adds a new, open order to the book.
        This is called by the MatchingEngine when a limit order
        is not immediately filled.
        
        Args:
            order_details (dict): Contains order info, e.g.:
                {'side': 'buy', 'qty': 100, 'price': 150.50, 'type': 'limit'}
        """
        # 1. Create a full order object
        order = order_details.copy()
        order['id'] = str(uuid.uuid4()) # Assign a unique ID
        order['timestamp'] = time.time() #################### Maybe use the time of the tick???????
        order['is_cancelled'] = False
        
        # 2. Store the order for fast lookup
        self.orders[order['id']] = order
        
        # 3. Add the order to the correct heap
        if order['side'] == 'buy':
            heap_item = (-order['price'], order['timestamp'], order)
            heapq.heappush(self.bids, heap_item)
        else:
            heap_item = (order['price'], order['timestamp'], order)
            heapq.heappush(self.asks, heap_item)
                
        return order['id']

    def cancel_order(self, order_id):
        """
        Marks an order for cancellation ("lazy cancellation").
        """
        if order_id in self.orders:
            self.orders[order_id]['is_cancelled'] = True
            print(f"OrderBook: Order {order_id} marked for cancellation.")
            return True
        else:
            print(f"OrderBook: Error - Cannot cancel. Order {order_id} not found.")
            return False

    def modify_order(self, order_id, new_details):
        """
        Modifies an order by cancelling the old one and adding a new one.
        """
        if self.cancel_order(order_id):
            # Get old order details and create a new one
            old_order = self.orders[order_id]
            new_order = {
                'side': old_order['side'],
                'qty': new_details.get('qty', old_order['qty']),
                'price': new_details.get('price', old_order['price']),
                'type': old_order['type']
            }
            return self.add_order(new_order)
        else:
            return None # Old order not found

    def get_best_bid_order(self):
        """Returns the full order at the highest bid (or None)."""
        while self.bids:
            price_neg, _, order = self.bids[0]
            if order['is_cancelled']:
                heapq.heappop(self.bids) # Clean up cancelled orders
                continue
            return order
        return None

    def get_best_ask_order(self):
        """Returns the full order at the lowest ask (or None)."""
        while self.asks:
            price, _, order = self.asks[0]
            if order['is_cancelled']:
                heapq.heappop(self.asks) # Clean up cancelled orders
                continue
            return order
        return None
        
    def pop_best_bid_order(self):
        """Removes and returns the best bid order."""
        while self.bids:
            price_neg, _, order = heapq.heappop(self.bids)
            if order['is_cancelled']:
                continue
            del self.orders[order['id']]
            return order
        return None
        
    def pop_best_ask_order(self):
        """Removes and returns the best ask order."""
        while self.asks:
            price, _, order = heapq.heappop(self.asks)
            if order['is_cancelled']:
                continue
            del self.orders[order['id']]
            return order
        return None