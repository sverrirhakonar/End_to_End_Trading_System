from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class MarketDataPoint:
    timestamp: datetime
    symbol: str
    price: float
    quantity: int
