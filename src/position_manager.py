import json
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0


@dataclass
class TradeRecord:
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    realized_pnl: float
    position_after: float


@dataclass
class PositionManager:
    cash: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    trade_log: List[TradeRecord] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str) -> "PositionManager":
        with open(path, "r") as f:
            data = json.load(f)

        cash = data.get("cash", 0.0)
        raw_positions = data.get("positions", {})

        positions: Dict[str, Position] = {}

        for symbol, p in raw_positions.items():
            qty = p.get("quantity", 0.0)
            avg = p.get("avg_price", 0.0)
            positions[symbol] = Position(symbol, qty, avg)

        return cls(cash=cash, positions=positions)

    def get_cash(self) -> float:
        return self.cash

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def snapshot_positions(self) -> Dict[str, float]:
        return {sym: pos.quantity for sym, pos in self.positions.items()}

    def update_from_fill(self, order, fee: float = 0.0) -> None:
        qty = order.filled_quantity
        price = order.filled_price
        symbol = order.symbol
        side = order.side

        side_up = side.upper()
        signed_qty = qty if side_up == "BUY" else -qty

        pos = self.positions.get(symbol)
        if pos is None:
            pos = Position(symbol=symbol)
            self.positions[symbol] = pos

        old_qty = pos.quantity
        new_qty = old_qty + signed_qty

        trade_value = price * qty

        if signed_qty > 0:
            self.cash -= trade_value + fee
        else:
            self.cash += trade_value - fee

        # realized PnL calculation
        realized_pnl = 0.0
        if old_qty > 0 and signed_qty < 0:
            closing_qty = min(old_qty, -signed_qty)
            realized_pnl = closing_qty * (price - pos.avg_price)
        elif old_qty < 0 and signed_qty > 0:
            closing_qty = min(-old_qty, signed_qty)
            realized_pnl = closing_qty * (pos.avg_price - price)

        # Avg price handling
        if old_qty == 0 and new_qty != 0:
            pos.avg_price = price
        elif (
            old_qty != 0
            and new_qty != 0
            and ((old_qty > 0 and new_qty > 0) or (old_qty < 0 and new_qty < 0))
        ):
            total_old = abs(old_qty) * pos.avg_price
            total_new = abs(signed_qty) * price
            pos.avg_price = (total_old + total_new) / abs(new_qty)
        elif old_qty != 0 and new_qty != 0 and old_qty * new_qty < 0:
            pos.avg_price = price

        pos.quantity = new_qty

        if pos.quantity == 0:
            pos.avg_price = 0.0

        # trade log record
        ts = getattr(order, "filled_timestamp", None)
        if ts is None:
            ts = getattr(order, "timestamp", None)
        if isinstance(ts, datetime):
            trade_ts = ts
        else:
            trade_ts = datetime.fromisoformat(str(ts)) if ts is not None else datetime.utcnow()

        self.trade_log.append(
            TradeRecord(
                timestamp=trade_ts,
                symbol=symbol,
                side=side_up,
                quantity=qty,
                price=price,
                realized_pnl=realized_pnl,
                position_after=pos.quantity,
            )
        )

    def position_value(self, symbol: str, last_price: float) -> float:
        pos = self.positions.get(symbol)
        if pos is None:
            return 0.0
        return pos.quantity * last_price

    def portfolio_value(self, last_prices: Dict[str, float]) -> float:
        value = self.cash
        for sym, pos in self.positions.items():
            price = last_prices.get(sym)
            if price is not None:
                value += pos.quantity * price
        return value

    def is_flat(self, symbol: str) -> bool:
        pos = self.positions.get(symbol)
        return pos is None or pos.quantity == 0

    def is_long(self, symbol: str) -> bool:
        pos = self.positions.get(symbol)
        return pos is not None and pos.quantity > 0

    def is_short(self, symbol: str) -> bool:
        pos = self.positions.get(symbol)
        return pos is not None and pos.quantity < 0
