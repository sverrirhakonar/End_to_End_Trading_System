
from abc import ABC, abstractmethod
from model.models import MarketDataPoint

class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, tick: MarketDataPoint) -> list:
        pass

class MovingAverageStrategy(Strategy):
    def __init__(self):
        self.prices = []
        self._running_sum = 0.0

from collections import deque

class MovingAverageStrategy(Strategy):
    def __init__(self, window=20):
        self.window = window
        self.prices = deque()
        self._running_sum = 0.0

    def generate_signals(self, tick):
        price = tick.price

        self.prices.append(price)
        self._running_sum += price

        if len(self.prices) > self.window:
            oldest = self.prices.popleft()
            self._running_sum -= oldest

        if len(self.prices) < self.window:
            return []
        mean = self._running_sum / self.window

        if price < mean:
            return ['BUY']
        if price > mean:
            return ['SELL']
        return []
