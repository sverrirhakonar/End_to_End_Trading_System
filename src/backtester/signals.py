# src/backtester/signals.py

from dataclasses import dataclass, field
from typing import Dict, List, Iterable, Optional


@dataclass
class Signal:
    symbol: str
    side: str           # "BUY" or "SELL"
    strength: float = 1.0
    source: Optional[str] = None


@dataclass
class AggregatedSymbolSignal:
    symbol: str
    buy_count: int = 0
    sell_count: int = 0
    total_buy_strength: float = 0.0
    total_sell_strength: float = 0.0
    sources: List[str] = field(default_factory=list)

    @property
    def net_strength(self) -> float:
        return self.total_buy_strength - self.total_sell_strength

    @property
    def has_buy(self) -> bool:
        return self.buy_count > 0

    @property
    def has_sell(self) -> bool:
        return self.sell_count > 0


@dataclass
class SignalBundle:
    by_symbol: Dict[str, AggregatedSymbolSignal]

    @classmethod
    def from_signals(cls, signals: Iterable[Signal]) -> "SignalBundle":
        agg: Dict[str, AggregatedSymbolSignal] = {}

        for s in signals:
            sym = s.symbol
            if sym not in agg:
                agg[sym] = AggregatedSymbolSignal(symbol=sym)

            entry = agg[sym]

            if s.side == "BUY":
                entry.buy_count += 1
                entry.total_buy_strength += s.strength
            elif s.side == "SELL":
                entry.sell_count += 1
                entry.total_sell_strength += s.strength

            if s.source is not None:
                entry.sources.append(s.source)

        return cls(by_symbol=agg)

    def strongest_buy_symbol(self) -> Optional[AggregatedSymbolSignal]:
        candidates = [
            v for v in self.by_symbol.values()
            if v.total_buy_strength > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.total_buy_strength)

    def strongest_sell_symbol(self) -> Optional[AggregatedSymbolSignal]:
        candidates = [
            v for v in self.by_symbol.values()
            if v.total_sell_strength > 0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x.total_sell_strength)

    def strongest_net_symbol(self) -> Optional[AggregatedSymbolSignal]:
        if not self.by_symbol:
            return None
        return max(self.by_symbol.values(), key=lambda x: abs(x.net_strength))
