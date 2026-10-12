# Extracted from the private MarginOps repository: live/tests/test_reconcile.py at commit f1770cc (2 Oct 2026).
# Changes: import paths (the sys.path shim and the __main__ runner removed); instrument names replaced by placeholders; a dash replaced.
"""Reconciliation tests: manual square-off detection (the 2022 'I closed some myself' case)."""
from marginops_extract.reconcile import reconcile, ReconKind
from marginops_extract.snapshot import PositionSnapshot


def snap(sec, sym, cid):
    return PositionSnapshot(security_id=sec, symbol=sym, product="MTF", qty=10,
                            avg_price=100, ltp=102, correlation_id=cid)


def sys_pos(sec, sym, cid):
    return {"security_id": sec, "symbol": sym, "correlation_id": cid}


def test_manual_close_detected():
    # we hold STOCK_A; broker no longer shows it -> user squared it off manually
    events = reconcile([sys_pos("1", "STOCK_A", "A-STOCK_A")], broker_positions=[])
    assert len(events) == 1
    assert events[0].kind is ReconKind.MANUAL_CLOSE and events[0].symbol == "STOCK_A"


def test_matched_position():
    s = sys_pos("1", "STOCK_A", "A-STOCK_A")
    b = snap("1", "STOCK_A", "A-STOCK_A")
    events = reconcile([s], [b])
    assert len(events) == 1 and events[0].kind is ReconKind.MATCHED


def test_manual_open_flagged():
    # broker shows a position we never placed -> manual buy
    events = reconcile(system_open=[], broker_positions=[snap("9", "STOCK_C", None)])
    assert any(e.kind is ReconKind.MANUAL_OPEN and e.symbol == "STOCK_C" for e in events)


def test_partial_manual_close_in_mixed_book():
    # two open; user closes one (STOCK_A) in the app, keeps the other (STOCK_B)
    sysp = [sys_pos("1", "STOCK_A", "A-STOCK_A"), sys_pos("2", "STOCK_B", "A-STOCK_B")]
    broker = [snap("2", "STOCK_B", "A-STOCK_B")]
    events = reconcile(sysp, broker)
    kinds = {e.symbol: e.kind for e in events}
    assert kinds["STOCK_A"] is ReconKind.MANUAL_CLOSE
    assert kinds["STOCK_B"] is ReconKind.MATCHED


def test_match_by_security_id_when_cid_missing():
    s = sys_pos("5", "STOCK_D", "A-STOCK_D")
    b = snap("5", "STOCK_D", None)               # broker lost our cid but same scrip
    events = reconcile([s], [b])
    assert events[0].kind is ReconKind.MATCHED

