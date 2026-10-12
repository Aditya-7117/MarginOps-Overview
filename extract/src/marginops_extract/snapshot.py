# Extracted from the private MarginOps repository: live/marginops/broker/base.py at commit f1770cc (2 Oct 2026).
# Changes: only the PositionSnapshot type is kept; the broker interface, orders and margin types are omitted.
"""The broker position snapshot the reconciler compares against."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PositionSnapshot:
    security_id: str
    symbol: str
    product: str
    qty: int
    avg_price: float               # position cost basis, not an order-fill acknowledgement
    ltp: float                     # 0 may mean unavailable; never infer NAV from that sentinel
    correlation_id: Optional[str]  # ours if we placed it; None => possibly manual/broker
    exchange_segment: str = "NSE_EQ"
