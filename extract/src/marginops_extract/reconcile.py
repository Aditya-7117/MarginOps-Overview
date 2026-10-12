# Extracted from the private MarginOps repository: live/marginops/engine/reconcile.py at commit f1770cc (2 Oct 2026).
# Changes: dashes in docstrings replaced. Logic unchanged.
"""
Reconciliation + manual-override: the broker is the source of truth; the system adapts.

Every cycle we compare what WE think is open against what the BROKER reports:
  • a position we hold but the broker no longer shows -> the user SQUARED IT OFF manually
    in the Dhan app. We book it as "manual", free the slot, no panic, no re-entry.
  • a broker position with no matching system order -> a manual BUY (or a stale fill);
    flagged for review, never auto-managed as ours.
  • matched positions -> refresh LTP/qty from the broker.

Pure logic over the two lists (keyed by correlation id, then security id). Unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReconKind(Enum):
    MANUAL_CLOSE = "manual_close"        # we held it, broker doesn't -> user closed it
    MANUAL_OPEN = "manual_open"          # broker has it, we didn't place it -> user opened it
    MATCHED = "matched"                  # both agree -> refresh
    MANUAL_SL_MODIFY = "manual_sl_modify"  # user moved our stop's trigger -> adopt broker truth
    MANUAL_SL_CANCEL = "manual_sl_cancel"  # our stop order is gone at broker -> re-arm a fresh one
    MANUAL_ENTRY_CANCEL = "manual_entry_cancel"  # user cancelled our pending buy -> drop, free slot


@dataclass(frozen=True)
class ReconEvent:
    kind: ReconKind
    key: str                          # correlation id or security id
    symbol: str
    detail: str


def reconcile(system_open: list, broker_positions: list) -> list[ReconEvent]:
    """`system_open`  : our open positions  (objects/dicts with .correlation_id|order_id,
                        .security_id, .symbol)
       `broker_positions`: PositionSnapshot list from the broker.
    Returns the events the loop must act on (book manual closes, flag manual opens)."""
    def cid(p):
        return _get(p, "correlation_id") or _get(p, "order_id")

    broker_by_cid = {p.correlation_id: p for p in broker_positions if p.correlation_id}
    broker_by_sec = {p.security_id: p for p in broker_positions}
    events: list[ReconEvent] = []
    seen_secs: set = set()

    # our positions vs broker
    for s in system_open:
        c = cid(s)
        sec = _get(s, "security_id")
        sym = _get(s, "symbol") or _get(s, "stock") or str(sec)
        seen_secs.add(sec)
        match = (broker_by_cid.get(c) if c else None) or broker_by_sec.get(sec)
        if match is None:
            events.append(ReconEvent(ReconKind.MANUAL_CLOSE, str(c or sec), sym,
                                     "held by system, absent at broker -> user squared off"))
        else:
            events.append(ReconEvent(ReconKind.MATCHED, str(c or sec), sym, "ok"))

    # broker positions we never placed
    for p in broker_positions:
        if p.security_id in seen_secs:
            continue
        if p.correlation_id and any(cid(s) == p.correlation_id for s in system_open):
            continue
        events.append(ReconEvent(ReconKind.MANUAL_OPEN, p.correlation_id or p.security_id,
                                 p.symbol, "broker position with no system order -> manual buy"))
    return events


def reconcile_orders(system_stops: list, broker_orders: list, *, tick: float = 0.05) -> list[ReconEvent]:
    """Order-level reconciliation for user intervention on our PROTECTIVE STOPS / pending entries.
    The broker is the source of truth; we adapt and never fight.

    `system_stops`  : our tracked stops (objects/dicts with .sl_order_id, .trigger_price, .symbol,
                      and optional .kind in {"stop","entry"}; default "stop").
    `broker_orders` : the live order book, dicts with orderId, orderStatus, triggerPrice.

      • our stop's trigger differs from the broker's      -> MANUAL_SL_MODIFY (adopt broker)
      • our stop order id absent / CANCELLED at broker     -> MANUAL_SL_CANCEL (re-arm next cycle)
      • our pending entry absent / CANCELLED at broker     -> MANUAL_ENTRY_CANCEL (free the slot)
    Orders the broker shows as TRADED/EXPIRED are normal lifecycle, not intervention.
    """
    by_id = {str(_get(o, "orderId")): o for o in broker_orders if _get(o, "orderId") is not None}
    gone = {"CANCELLED", "REJECTED", "EXPIRED"}
    events: list[ReconEvent] = []
    for s in system_stops:
        oid = _get(s, "sl_order_id") or _get(s, "order_id")
        sym = _get(s, "symbol") or _get(s, "stock") or str(oid)
        kind = (_get(s, "kind") or "stop")
        bo = by_id.get(str(oid)) if oid is not None else None
        status = str(_get(bo, "orderStatus") or "").upper() if bo else ""
        if oid is None or bo is None or status in gone:
            if kind == "entry":
                events.append(ReconEvent(ReconKind.MANUAL_ENTRY_CANCEL, str(oid), sym,
                                         "pending entry gone at broker -> user cancelled, free slot"))
            else:
                events.append(ReconEvent(ReconKind.MANUAL_SL_CANCEL, str(oid), sym,
                                         "protective stop gone at broker -> re-arm a fresh stop"))
            continue
        if kind == "stop":
            our_trig = float(_get(s, "trigger_price") or 0)
            brk_trig = float(_get(bo, "triggerPrice") or 0)
            if brk_trig > 0 and abs(brk_trig - our_trig) > tick:
                events.append(ReconEvent(ReconKind.MANUAL_SL_MODIFY, str(oid), sym,
                                         f"user moved stop {our_trig}->{brk_trig}; adopt broker truth"))
    return events


def _get(obj, attr):
    if isinstance(obj, dict):
        return obj.get(attr)
    return getattr(obj, attr, None)
