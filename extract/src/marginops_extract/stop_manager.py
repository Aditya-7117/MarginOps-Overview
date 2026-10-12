# Extracted from the private MarginOps repository: live/marginops/engine/stop_manager.py at commit f1770cc (2 Oct 2026).
# Changes: dashes in docstrings replaced. Logic unchanged.
"""
StopOrderManager: the smart-handshake brain for a position's protective stop.

The broker caps the number of MODIFICATIONS on a single stop order (Dhan/exchange hard
limit = 25). Our per-setup trailing only re-prices the stop ~1-2x/day, but a swing held
for weeks on a persistent (Forever/GTT) stop accumulates modifies and WILL approach 25.

This class is PURE DECISION LOGIC (no network): given the current stop and a desired new
stop, it returns the ACTION the executor must take:

    NOOP     desired stop is not higher than the live stop (we never loosen a stop)
    MODIFY   re-price the existing stop order (consumes one of the 25 modifies)
    REPLACE  the modify budget is nearly exhausted -> CANCEL the stop order and PLACE a
             fresh one at the new trigger; the broker's modify counter resets to 0

The executor (DhanBroker live / PaperBroker mirror) performs the action and calls back
`on_modified` / `on_replaced` so the counter stays in lockstep with reality. Trailing is
monotonic up; a gap-down still books because the underlying order is a MARKET stop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StopAction(Enum):
    NOOP = "noop"
    MODIFY = "modify"
    REPLACE = "replace"        # cancel + place fresh (resets the broker modify counter)


# Dhan/exchange hard limit on modifications to one order. We act a few short of it.
MAX_MODIFIES = 25
SAFETY = 2                     # trigger REPLACE at (MAX_MODIFIES - SAFETY) to never hit the wall


@dataclass
class StopState:
    """Per-position protective-stop bookkeeping (persisted with the position)."""
    security_id: str
    symbol: str
    qty: int
    sl_order_id: str | None = None      # broker id of the live stop order
    trigger_price: float = 0.0
    modify_count: int = 0               # modifies since this order was (re)placed
    replaced_count: int = 0             # how many times we did the cancel/replace handshake
    max_modifies: int = MAX_MODIFIES
    safety: int = SAFETY


@dataclass(frozen=True)
class StopDecision:
    action: StopAction
    new_trigger: float
    reason: str


@dataclass
class StopOrderManager:
    state: StopState

    def plan(self, desired_trigger: float, *, tick: float = 0.05) -> StopDecision:
        """Decide what to do to move the stop to `desired_trigger`. Never lowers the stop."""
        st = self.state
        if st.sl_order_id is None:
            return StopDecision(StopAction.REPLACE, desired_trigger, "no live stop -> place one")
        if desired_trigger <= st.trigger_price + tick / 2:
            return StopDecision(StopAction.NOOP, st.trigger_price, "stop not raised")
        # would this modify exhaust the budget? then cancel+replace (counter resets to 0)
        if st.modify_count + 1 >= st.max_modifies - st.safety:
            return StopDecision(StopAction.REPLACE, desired_trigger,
                                f"modify budget near limit ({st.modify_count}/{st.max_modifies}) -> cancel+replace")
        return StopDecision(StopAction.MODIFY, desired_trigger,
                            f"modify {st.modify_count + 1}/{st.max_modifies}")

    # ---- executor callbacks (keep the counter truthful) ----
    def on_modified(self, new_trigger: float) -> None:
        self.state.trigger_price = new_trigger
        self.state.modify_count += 1

    def on_replaced(self, new_sl_order_id: str, new_trigger: float) -> None:
        self.state.sl_order_id = new_sl_order_id
        self.state.trigger_price = new_trigger
        self.state.modify_count = 0                 # fresh order -> counter resets
        self.state.replaced_count += 1

    def on_external_change(self, broker_trigger: float | None, broker_order_id: str | None) -> None:
        """The user/broker changed the stop out-of-band (manual modify, or the order is gone).
        ADOPT the broker truth; never fight it. If the order vanished, mark it absent so the
        next cycle re-arms a fresh protective stop."""
        if broker_order_id is None:
            self.state.sl_order_id = None
            return
        self.state.sl_order_id = broker_order_id
        if broker_trigger is not None and broker_trigger > 0:
            self.state.trigger_price = broker_trigger
        self.state.modify_count = 0                 # unknown how many the user used; reset to be safe
