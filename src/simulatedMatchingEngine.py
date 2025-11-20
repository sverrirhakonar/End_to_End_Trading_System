import random
from src.order_book import OrderBook
from src.logger_gateway import OrderLogger
from src.order import Order
import pandas as pd

class SimulatedMatchingEngine:

    def __init__(self, order_book: OrderBook, order_logger: OrderLogger):
        """ Initializes the engine. """
        self.order_book = order_book
        self.order_logger = order_logger
        
        # --- Configurable Randomness ---
        # 5% chance an order is just randomly rejected
        self.fill_reject_chance = 0.05 
        
        # 10% chance a fill will be partial
        self.partial_fill_chance = 0.10
        
        print("SimulatedMatchingEngine: Initialized.")

    def process_order(self, order: Order, current_tick: 'pd.Series'):
        """ Processes a *new* order from the strategy.
        This is called *after* the OrderManager validates it. """
        
        # 1. Simulate random rejection (Requirement 2.4)
        if random.random() < self.fill_reject_chance:
            print("MatchingEngine: Order randomly REJECTED.")
            self.order_logger.log_event('REJECTED', order, tick_timestamp=current_tick.name, reason="Random engine rejection")
            return [] # No fills

        # 2. Process based on order type
        if order.order_type == 'MARKET':
            return self._fill_market_order(order, current_tick)
            
        elif order.order_type == 'LIMIT':
            return self._process_limit_order(order, current_tick)
            
        return []
 
 
    def _fill_market_order(self, order: Order, current_tick: 'pd.Series'):
        """Handles filling a market order."""
        
        # We simulate the fill at the 'Close' price of the current bar.
        fill_price = current_tick['Close']
        fill_qty = order.quantity
        
        # 2. Simulate partial fill (Requirement 2.4)
        if random.random() < self.partial_fill_chance:
            # Fill a random 10% to 90% of the order
            fill_qty = int(order.quantity * random.uniform(0.1, 0.9))
            print(f"MatchingEngine: Order partially filled ({fill_qty} / {order.quantity})")
        
        # Log the fill
        self.order_logger.log_event(
            'FILLED', 
            order, 
            tick_timestamp=current_tick.name,
            fill_qty=fill_qty, 
            fill_price=fill_price
        )
        
        # Return a "fill event" for the portfolio to process
        return [{
            'side': order.side,
            'fill_qty': fill_qty,
            'fill_price': fill_price
        }]

    def _process_limit_order(self, order: Order, current_tick: 'pd.Series'):
        """Handles a new limit order."""
        
        can_fill_now = False
        fill_price = order.price # Limit orders fill at their price
        
        # Check if the order can be filled on this *same tick*
        if order.side == 'BUY':
            # We can buy if our limit price is >= the market's Low
            if order.price >= current_tick['Low']:
                can_fill_now = True
                
        elif order.side == 'SELL':
            # We can sell if our limit price is <= the market's High
            if order.price <= current_tick['High']:
                can_fill_now = True

        # --- Fill it now ---
        if can_fill_now:
            print(f"MatchingEngine: Limit order filled immediately.")
            # We can re-use the market order logic for filling
            return self._fill_market_order(order, current_tick)
            
        # --- Can't fill, so add to waiting room ---
        else:
            print(f"MatchingEngine: Limit order added to OrderBook to wait.")
            # Add the order to the book and get back the order ID
            order_id = self.order_book.add_order(order)
            
            # Log that it's been "placed" (but not filled)
            self.order_logger.log_event('PLACED', order, tick_timestamp=current_tick.name, reason="Placed in book to wait")
            return [] # No fills

    def check_open_orders(self, current_tick: 'pd.Series'):
        """ This runs *every tick* to check the waiting orders in the
        OrderBook against the new market data. """
        fills = []
        
        # --- 1. Check waiting BUY orders ---
        while True:
            best_bid_order = self.order_book.get_best_bid_order()
            
            if not best_bid_order:
                break # No waiting bids
                
            # Can we fill this buy order?
            # We can buy if our limit price is >= the market's Low
            if best_bid_order.price >= current_tick['Low']:
                print(f"MatchingEngine: Waiting BUY order {best_bid_order.order_id} FILLED.")
                
                # Pop it from the book
                popped_order = self.order_book.pop_best_bid_order()
                fill_price = popped_order.price
                fill_qty = popped_order.quantity # We fill 100% from the book
                
                self.order_logger.log_event('FILLED', popped_order, tick_timestamp=current_tick.name, fill_qty=fill_qty, fill_price=fill_price)
                fills.append({
                    'side': 'BUY',
                    'fill_qty': fill_qty,
                    'fill_price': fill_price
                })
            else:
                # The best buy order is still too low, so we stop checking
                break 

        # --- 2. Check waiting SELL orders ---
        while True:
            best_ask_order = self.order_book.get_best_ask_order()
            
            if not best_ask_order:
                break # No waiting asks
                
            # Can we fill this sell order?
            # We can sell if our limit price is <= the market's High
            if best_ask_order.price <= current_tick['High']:
                print(f"MatchingEngine: Waiting SELL order {best_ask_order.order_id} FILLED.")
                
                popped_order = self.order_book.pop_best_ask_order()
                fill_price = popped_order.price
                fill_qty = popped_order.quantity
                
                self.order_logger.log_event('FILLED', popped_order, tick_timestamp=current_tick.name, fill_qty=fill_qty, fill_price=fill_price)
                fills.append({
                    'side': 'SELL',
                    'fill_qty': fill_qty,
                    'fill_price': fill_price
                })
            else:
                # The best sell order is still too high, so we stop
                break
                
        return fills