
from abc import ABC, abstractmethod
from model.models import MarketDataPoint
from src.backtester.price_manager import PriceManager


class Strategy(ABC):
    @abstractmethod
    def generate_signals(self, tick: MarketDataPoint) -> list:
        pass

class MomentumStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, period: int = 20, threshold: float = 0.02):
        self.pm = price_manager
        self.symbol = symbol
        self.period = period
        self.threshold = threshold

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        roc = self.pm.get_rate_of_change(self.symbol, self.period)
        if roc is None:
            return []
        if roc > self.threshold:
            return ["BUY"]
        if roc < -self.threshold:
            return ["SELL"]
        return []

class MovingAverageCrossoverStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, fast: int = 10, slow: int = 50):
        self.pm = price_manager
        self.symbol = symbol
        self.fast = fast
        self.slow = slow

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        fast_sma = self.pm.get_sma(self.symbol, self.fast)
        slow_sma = self.pm.get_sma(self.symbol, self.slow)
        if fast_sma is None or slow_sma is None:
            return []
        if fast_sma > slow_sma:
            return ["BUY"]
        if fast_sma < slow_sma:
            return ["SELL"]
        return []

class MeanReversionStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, period: int = 20, band: float = 0.02):
        self.pm = price_manager
        self.symbol = symbol
        self.period = period
        self.band = band

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        dev = self.pm.get_price_deviation_from_sma(self.symbol, self.period)
        if dev is None:
            return []
        if dev < -self.band:
            return ["BUY"]   # price below SMA
        if dev > self.band:
            return ["SELL"]  # price above SMA
        return []

class BollingerReversionStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, period: int = 20, num_std: float = 2.0):
        self.pm = price_manager
        self.symbol = symbol
        self.period = period
        self.num_std = num_std

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        mid, upper, lower = self.pm.get_bollinger_bands(self.symbol, self.period, self.num_std)
        price = self.pm.get_latest_price(self.symbol)
        if mid is None or upper is None or lower is None or price is None:
            return []
        if price < lower:
            return ["BUY"]
        if price > upper:
            return ["SELL"]
        return []

class DonchianBreakoutStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, lookback: int = 20):
        self.pm = price_manager
        self.symbol = symbol
        self.lookback = lookback

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        highest, lowest = self.pm.get_high_low_range(self.symbol, self.lookback)
        price = self.pm.get_latest_price(self.symbol)
        if highest is None or lowest is None or price is None:
            return []
        if price > highest:
            return ["BUY"]
        if price < lowest:
            return ["SELL"]
        return []

class AtrBreakoutStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, atr_period: int = 14, k: float = 1.5):
        self.pm = price_manager
        self.symbol = symbol
        self.atr_period = atr_period
        self.k = k

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        atr = self.pm.get_atr(self.symbol, self.atr_period)
        price = self.pm.get_latest_price(self.symbol)
        sma = self.pm.get_sma(self.symbol, self.atr_period)
        if atr is None or price is None or sma is None:
            return []
        
        upper_break = sma + self.k * atr
        lower_break = sma - self.k * atr
        
        if price > upper_break:
            return ["BUY"]
        if price < lower_break:
            return ["SELL"]
        return []

class RsiReversionStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str,
                 period: int = 14, overbought: float = 70.0, oversold: float = 30.0):
        self.pm = price_manager
        self.symbol = symbol
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        rsi = self.pm.get_rsi(self.symbol, self.period)
        if rsi is None:
            return []
        if rsi < self.oversold:
            return ["BUY"]
        if rsi > self.overbought:
            return ["SELL"]
        return []

class TrendRsiConfirmationStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str, sma_period: int = 50):
        self.pm = price_manager
        self.symbol = symbol
        self.sma_period = sma_period

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        price = self.pm.get_latest_price(self.symbol)
        sma = self.pm.get_sma(self.symbol, self.sma_period)
        rsi = self.pm.get_rsi(self.symbol, period=14)
        if price is None or sma is None or rsi is None:
            return []
        
        if price > sma and rsi > 55:
            return ["BUY"]
        if price < sma and rsi < 45:
            return ["SELL"]
        return []

class MacdTrendStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str,
                 fast: int = 12, slow: int = 26, signal_period: int = 9):
        self.pm = price_manager
        self.symbol = symbol
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        macd_line, signal_line, hist = self.pm.get_macd(
            self.symbol,
            self.fast,
            self.slow,
            self.signal_period
        )
        if macd_line is None or signal_line is None or hist is None:
            return []
        if hist > 0 and macd_line > signal_line:
            return ["BUY"]
        if hist < 0 and macd_line < signal_line:
            return ["SELL"]
        return []

class RegimeSwitchingStrategy(Strategy):
    def __init__(self, price_manager: PriceManager, symbol: str,
                 vola_period: int = 20, vola_threshold: float = 0.01, sma_period: int = 20):
        self.pm = price_manager
        self.symbol = symbol
        self.vola_period = vola_period
        self.vola_threshold = vola_threshold
        self.sma_period = sma_period

    def generate_signals(self, tick: MarketDataPoint) -> list[str]:
        vola = self.pm.get_volatility(self.symbol, self.vola_period)
        price = self.pm.get_latest_price(self.symbol)
        sma = self.pm.get_sma(self.symbol, self.sma_period)
        if vola is None or price is None or sma is None:
            return []
        
        deviation = self.pm.get_price_deviation_from_sma(self.symbol, self.sma_period)
        if deviation is None:
            return []
        
        # Low volatility regime: mean reversion
        if vola < self.vola_threshold:
            if deviation < -0.01:
                return ["BUY"]
            if deviation > 0.01:
                return ["SELL"]
            return []
        
        # High volatility regime: trend following
        if price > sma:
            return ["BUY"]
        if price < sma:
            return ["SELL"]
        return []
