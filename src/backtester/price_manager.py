from collections import deque
import pandas as pd

class PriceManager:
    def __init__(self, max_history: int = 100):
        self.prices = {}  # {symbol: deque(maxlen=max_history)}
        self.max_history = max_history
    
    def update(self, symbol: str, tick_data: pd.Series):
        """Add new price bar to history."""
        if symbol not in self.prices:
            self.prices[symbol] = deque(maxlen=self.max_history)
        self.prices[symbol].append(tick_data)
    
    def get_latest_price(self, symbol: str) -> float:
        """Get most recent close price."""
        if symbol not in self.prices or len(self.prices[symbol]) == 0:
            return None
        return self.prices[symbol][-1]['Close']
    
    def get_sma(self, symbol: str, period: int) -> float:
        """Calculate simple moving average."""
        if not self._has_sufficient_data(symbol, period):
            return None
        prices = [bar['Close'] for bar in list(self.prices[symbol])[-period:]]
        return sum(prices) / period
    
    def get_std(self, symbol: str, period: int) -> float:
        """Calculate standard deviation."""
        if not self._has_sufficient_data(symbol, period):
            return None
        prices = [bar['Close'] for bar in list(self.prices[symbol])[-period:]]
        mean = sum(prices) / period
        variance = sum((p - mean) ** 2 for p in prices) / period
        return variance ** 0.5
    
    def get_bollinger_bands(self, symbol: str, period: int, num_std: float = 2.0):
        """Calculate Bollinger Bands (middle, upper, lower)."""
        sma = self.get_sma(symbol, period)
        std = self.get_std(symbol, period)
        if sma is None or std is None:
            return None, None, None
        upper = sma + (num_std * std)
        lower = sma - (num_std * std)
        return sma, upper, lower
    
    def _has_sufficient_data(self, symbol: str, period: int) -> bool:
        """Check if enough data exists for calculation."""
        return symbol in self.prices and len(self.prices[symbol]) >= period