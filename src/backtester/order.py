
class Order:
    def __init__(self, order_dict: dict):
        self.order_id = order_dict.get("order_id")
        self.timestamp = order_dict.get("timestamp")
        self.symbol = order_dict.get("symbol")
        self.quantity = order_dict.get("quantity")
        self.price = order_dict.get("price")
        self.order_type = order_dict.get("order_type")  
        self.status = "Pending"  
        self.filled_price = None  
        self.filled_quantity = None  
        self.filled_timestamp =  None  
        self.is_cancelled = False

    