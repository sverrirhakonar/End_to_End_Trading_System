import pandas as pd
from collections import deque
from typing import Optional, List, Tuple


class PriceManager:
    def __init__(self, max_history: int = 100):
        self.prices = {}  # {symbol: deque(maxlen=max_history)}
        self.max_history = max_history
    
    def update(self, symbol: str, tick_data: pd.Series):
        """Add new price bar to history."""
        if symbol not in self.prices:
            self.prices[symbol] = deque(maxlen=self.max_history)
        self.prices[symbol].append(tick_data)
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get most recent close price."""
        if symbol not in self.prices or len(self.prices[symbol]) == 0:
            return None
        return self.prices[symbol][-1]['Close']
    
    def _get_closes(self, symbol: str, period: Optional[int] = None) -> Optional[List[float]]:
        if symbol not in self.prices or len(self.prices[symbol]) == 0:
            return None
        data = list(self.prices[symbol])
        if period is not None and len(data) < period:
            return None
        if period is not None:
            data = data[-period:]
        return [bar['Close'] for bar in data]
    
    def _get_highs(self, symbol: str, period: int) -> Optional[List[float]]:
        if not self._has_sufficient_data(symbol, period):
            return None
        data = list(self.prices[symbol])[-period:]
        return [bar['High'] for bar in data]
    
    def _get_lows(self, symbol: str, period: int) -> Optional[List[float]]:
        if not self._has_sufficient_data(symbol, period):
            return None
        data = list(self.prices[symbol])[-period:]
        return [bar['Low'] for bar in data]

    def get_sma(self, symbol: str, period: int) -> Optional[float]:
        """Calculate simple moving average."""
        closes = self._get_closes(symbol, period)
        if closes is None:
            return None
        return sum(closes) / period
    
    def get_std(self, symbol: str, period: int) -> Optional[float]:
        """Calculate standard deviation."""
        closes = self._get_closes(symbol, period)
        if closes is None:
            return None
        mean = sum(closes) / period
        variance = sum((p - mean) ** 2 for p in closes) / period
        return variance ** 0.5
    
    def get_bollinger_bands(self, symbol: str, period: int, num_std: float = 2.0
                            ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate Bollinger Bands (middle, upper, lower)."""
        sma = self.get_sma(symbol, period)
        std = self.get_std(symbol, period)
        if sma is None or std is None:
            return None, None, None
        upper = sma + (num_std * std)
        lower = sma - (num_std * std)
        return sma, upper, lower
    
    def get_rate_of_change(self, symbol: str, period: int) -> Optional[float]:
        """Percentage change over period bars."""
        needed = period + 1
        closes = self._get_closes(symbol, needed)
        if closes is None or len(closes) < needed:
            return None
        old_price = closes[0]
        new_price = closes[-1]
        if old_price == 0:
            return None
        return (new_price - old_price) / old_price

    def _ema(self, values: List[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        k = 2.0 / (period + 1.0)
        ema = values[0]
        for v in values[1:]:
            ema = v * k + ema * (1.0 - k)
        return ema
    
    def get_ema(self, symbol: str, period: int) -> Optional[float]:
        closes = self._get_closes(symbol)
        if closes is None:
            return None
        return self._ema(closes, period)
    
    def get_rsi(self, symbol: str, period: int = 14) -> Optional[float]:
        closes = self._get_closes(symbol, period + 1)
        if closes is None or len(closes) < period + 1:
            return None
        
        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(-diff)
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi
    
    def get_macd(self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9
                ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        closes = self._get_closes(symbol)
        if closes is None:
            return None, None, None
        if len(closes) < slow:
            return None, None, None
        
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        if ema_fast is None or ema_slow is None:
            return None, None, None
        
        macd_line = ema_fast - ema_slow
        
        macd_series = []
        for i in range(len(closes)):
            sub = closes[: i + 1]
            if len(sub) >= slow:
                ef = self._ema(sub, fast)
                es = self._ema(sub, slow)
                if ef is not None and es is not None:
                    macd_series.append(ef - es)
        
        if len(macd_series) < signal:
            return macd_line, None, None
        
        signal_line = self._ema(macd_series, signal)
        if signal_line is None:
            return macd_line, None, None
        
        hist = macd_line - signal_line
        return macd_line, signal_line, hist
    
    def get_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        if not self._has_sufficient_data(symbol, period + 1):
            return None
        
        data = list(self.prices[symbol])[-(period + 1):]
        trs = []
        for i in range(1, len(data)):
            high = data[i]['High']
            low = data[i]['Low']
            prev_close = data[i - 1]['Close']
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            trs.append(tr)
        
        if len(trs) < period:
            return None
        return sum(trs) / period
    
    def get_high_low_range(self, symbol: str, period: int
                          ) -> Tuple[Optional[float], Optional[float]]:
        highs = self._get_highs(symbol, period)
        lows = self._get_lows(symbol, period)
        if highs is None or lows is None:
            return None, None
        return max(highs), min(lows)
    
    def get_volatility(self, symbol: str, period: int) -> Optional[float]:
        closes = self._get_closes(symbol, period + 1)
        if closes is None or len(closes) < period + 1:
            return None
        
        rets = []
        for i in range(1, len(closes)):
            if closes[i - 1] == 0:
                return None
            rets.append((closes[i] - closes[i - 1]) / closes[i - 1])
        
        if len(rets) == 0:
            return None
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        return var ** 0.5
    
    def get_price_deviation_from_sma(self, symbol: str, period: int) -> Optional[float]:
        price = self.get_latest_price(symbol)
        sma = self.get_sma(symbol, period)
        if price is None or sma is None or sma == 0:
            return None
        return (price - sma) / sma
    
    def _has_sufficient_data(self, symbol: str, period: int) -> bool:
        return symbol in self.prices and len(self.prices[symbol]) >= period
