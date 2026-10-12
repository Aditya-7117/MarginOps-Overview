# Extracted from the private MarginOps repository: live/tests/test_stop_manager.py at commit f1770cc (2 Oct 2026).
# Changes: import paths (the sys.path shim removed); instrument name and security id replaced by placeholders; dashes in the docstring replaced.
"""Unit tests for the 25-modify SL handshake + order-level intervention reconciliation.
Pure logic, no network, so this validates the live behaviour before Static-IP go-live."""
from marginops_extract.stop_manager import (
    StopOrderManager, StopState, StopAction, MAX_MODIFIES, SAFETY,
)
from marginops_extract.reconcile import reconcile_orders, ReconKind


def _mgr(**kw):
    base = dict(security_id="1001", symbol="STOCK_C", qty=10,
                sl_order_id="SL-1", trigger_price=100.0)
    base.update(kw)
    return StopOrderManager(StopState(**base))


def test_noop_when_stop_not_raised():
    m = _mgr()
    d = m.plan(99.0)               # lower -> never loosen
    assert d.action is StopAction.NOOP
    d = m.plan(100.0)             # equal -> noop
    assert d.action is StopAction.NOOP


def test_modify_raises_stop_and_counts():
    m = _mgr()
    d = m.plan(105.0)
    assert d.action is StopAction.MODIFY and d.new_trigger == 105.0
    m.on_modified(105.0)
    assert m.state.trigger_price == 105.0 and m.state.modify_count == 1


def test_replace_when_budget_nearly_exhausted():
    # drive the counter to one short of the safety threshold
    m = _mgr(modify_count=MAX_MODIFIES - SAFETY - 1)   # 22
    d = m.plan(110.0)
    assert d.action is StopAction.REPLACE             # the 23rd would hit the wall -> replace
    m.on_replaced("SL-2", 110.0)
    assert m.state.sl_order_id == "SL-2"
    assert m.state.modify_count == 0                  # counter reset
    assert m.state.replaced_count == 1


def test_full_sequence_never_exceeds_limit():
    m = _mgr(modify_count=0)
    trig = 100.0
    replaces = 0
    for i in range(1, 80):                            # trail up 79 times over the trade's life
        trig += 1.0
        d = m.plan(trig)
        assert m.state.modify_count < MAX_MODIFIES    # never reach the hard wall
        if d.action is StopAction.MODIFY:
            m.on_modified(trig)
        elif d.action is StopAction.REPLACE:
            m.on_replaced(f"SL-{i}", trig); replaces += 1
    assert replaces >= 3                              # handshake fired several times
    assert m.state.trigger_price == trig             # stop tracked all the way up


def test_no_live_stop_plans_replace():
    m = _mgr(sl_order_id=None)
    d = m.plan(100.0)
    assert d.action is StopAction.REPLACE


def test_external_change_adopts_broker_truth():
    m = _mgr()
    m.on_external_change(broker_trigger=108.0, broker_order_id="SL-1")
    assert m.state.trigger_price == 108.0 and m.state.modify_count == 0
    m.on_external_change(broker_trigger=None, broker_order_id=None)
    assert m.state.sl_order_id is None                # vanished -> re-arm next cycle


# ---- order-level reconciliation (user intervention) ----
def test_reconcile_detects_manual_sl_modify():
    stops = [{"sl_order_id": "SL-1", "symbol": "STOCK_C", "trigger_price": 100.0, "kind": "stop"}]
    book = [{"orderId": "SL-1", "orderStatus": "PENDING", "triggerPrice": 95.0}]
    ev = reconcile_orders(stops, book)
    assert len(ev) == 1 and ev[0].kind is ReconKind.MANUAL_SL_MODIFY


def test_reconcile_detects_manual_sl_cancel():
    stops = [{"sl_order_id": "SL-1", "symbol": "STOCK_C", "trigger_price": 100.0, "kind": "stop"}]
    book = [{"orderId": "SL-1", "orderStatus": "CANCELLED", "triggerPrice": 100.0}]
    ev = reconcile_orders(stops, book)
    assert ev[0].kind is ReconKind.MANUAL_SL_CANCEL
    # also when the order is simply absent
    assert reconcile_orders(stops, [])[0].kind is ReconKind.MANUAL_SL_CANCEL


def test_reconcile_detects_manual_entry_cancel():
    stops = [{"sl_order_id": "EN-1", "symbol": "STOCK_C", "kind": "entry"}]
    ev = reconcile_orders(stops, [])
    assert ev[0].kind is ReconKind.MANUAL_ENTRY_CANCEL


def test_reconcile_matched_stop_no_event():
    stops = [{"sl_order_id": "SL-1", "symbol": "STOCK_C", "trigger_price": 100.0, "kind": "stop"}]
    book = [{"orderId": "SL-1", "orderStatus": "PENDING", "triggerPrice": 100.0}]
    assert reconcile_orders(stops, book) == []
