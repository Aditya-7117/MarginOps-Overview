# Extracted from the private MarginOps repository: live/marginops/engine/risk_guards.py at commit f1770cc (2 Oct 2026).
# Changes: dashes replaced in comments. Logic unchanged.
"""
Risk guards: the live safety failsafes that sit between the brain and the broker.
Pure decision functions (no I/O) so they are unit-tested and trustworthy.

Three guards, each answering a survival question:
  1. SL WATCHDOG:      did a protective stop fail to fire (e.g. gap-down jumped over a
                       GTT trigger)? If price is at/below the stop and we're still open,
                       force a MARKET exit ourselves. The loss gets booked, no leak.
  2. PRE-TRADE GATE:   would this order leave the wallet short? Reject before placing.
  3. SHORTFALL MONITOR: is the wallet in shortfall, and how long? De-risk FAST so it
                       never persists past the broker's lock window (~4-5 trading days).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# --- 1. SL watchdog -----------------------------------------------------------
def should_force_exit(ltp: float, stop_price: float, position_open: bool,
                      exit_in_progress: bool) -> bool:
    """True -> fire a MARKET sell ourselves NOW. Catches a broker GTT/Forever stop that
    failed to trigger on a gap-down (price opened *below* the stop). Booking the loss at
    the gap price is correct; sitting in the trade hoping for recovery is not."""
    if not position_open or exit_in_progress:
        return False
    return ltp <= stop_price


# --- 2. pre-trade margin gate -------------------------------------------------
def pre_trade_ok(total_margin: float, available_balance: float,
                 insufficient_balance: float) -> bool:
    """True -> safe to place. Values come straight from POST /margincalculator.
    Never place an order the wallet cannot cover (the #1 shortfall cause, eliminated)."""
    if insufficient_balance > 0:
        return False
    return total_margin <= available_balance + 1e-6


# --- 3. shortfall monitor -----------------------------------------------------
class ShortfallAction(Enum):
    OK = "ok"                       # no shortfall
    REDUCE = "reduce"               # shortfall present -> de-risk + alert (still early)
    URGENT_FLATTEN = "urgent"       # shortfall lingering -> force-flatten before broker lock


@dataclass(frozen=True)
class ShortfallVerdict:
    action: ShortfallAction
    alert: bool
    reason: str


def shortfall_monitor(insufficient_balance: float, days_in_shortfall: int,
                      broker_lock_days: int = 5) -> ShortfallVerdict:
    """Decide how hard to act on a wallet shortfall. The broker locks funds if a shortfall
    persists `broker_lock_days` (~4-5). We act FAR sooner: de-risk on day 1, force-flatten
    by day 2, so a shortfall never survives to the lock window."""
    if insufficient_balance <= 0:
        return ShortfallVerdict(ShortfallAction.OK, False, "no-shortfall")
    # day 0/1: reduce exposure to clear it; always alert the user to top up
    if days_in_shortfall < 2:
        return ShortfallVerdict(ShortfallAction.REDUCE, True,
                                f"shortfall Rs{insufficient_balance:.0f} day{days_in_shortfall} -> de-risk")
    # day 2+ and still short: force-flatten well before the broker lock (~day 4-5)
    return ShortfallVerdict(ShortfallAction.URGENT_FLATTEN, True,
                            f"shortfall {days_in_shortfall}d -> flatten before broker lock@{broker_lock_days}d")
