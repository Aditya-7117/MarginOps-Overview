# Extracted from the private MarginOps repository: live/tests/test_risk_guards.py at commit f1770cc (2 Oct 2026).
# Changes: import path; dashes in docstrings replaced.
"""Unit tests for the live risk guards: the failsafes that book losses + kill shortfalls."""
from marginops_extract.risk_guards import (
    should_force_exit, pre_trade_ok, shortfall_monitor, ShortfallAction,
)


# ---- SL watchdog (the gap-down catch) ---------------------------------------
def test_gap_below_stop_forces_exit():
    # SL at 80, gap-opens at 70 -> broker GTT may not have fired -> WE force the exit
    assert should_force_exit(ltp=70, stop_price=80, position_open=True, exit_in_progress=False)


def test_exactly_at_stop_forces_exit():
    assert should_force_exit(ltp=80, stop_price=80, position_open=True, exit_in_progress=False)


def test_above_stop_does_not_exit():
    assert not should_force_exit(ltp=85, stop_price=80, position_open=True, exit_in_progress=False)


def test_no_double_fire_when_exit_pending():
    assert not should_force_exit(ltp=70, stop_price=80, position_open=True, exit_in_progress=True)


def test_closed_position_no_exit():
    assert not should_force_exit(ltp=70, stop_price=80, position_open=False, exit_in_progress=False)


# ---- pre-trade margin gate ---------------------------------------------------
def test_pre_trade_blocks_insufficient():
    assert not pre_trade_ok(total_margin=5000, available_balance=4000, insufficient_balance=1000)


def test_pre_trade_blocks_when_margin_exceeds_balance():
    assert not pre_trade_ok(total_margin=5000, available_balance=4999, insufficient_balance=0)


def test_pre_trade_allows_when_covered():
    assert pre_trade_ok(total_margin=3000, available_balance=10000, insufficient_balance=0)


# ---- shortfall monitor (the 4-5 day rule) -----------------------------------
def test_no_shortfall_ok():
    v = shortfall_monitor(insufficient_balance=0, days_in_shortfall=0)
    assert v.action is ShortfallAction.OK and not v.alert


def test_fresh_shortfall_reduces_and_alerts():
    v = shortfall_monitor(insufficient_balance=5000, days_in_shortfall=0)
    assert v.action is ShortfallAction.REDUCE and v.alert


def test_lingering_shortfall_flattens_before_lock():
    # day 2 still short -> flatten now, well before the ~5-day broker lock
    v = shortfall_monitor(insufficient_balance=5000, days_in_shortfall=2, broker_lock_days=5)
    assert v.action is ShortfallAction.URGENT_FLATTEN and v.alert

