# Extracted from the private MarginOps repository: live/tests/test_idempotency.py at commit f1770cc (2 Oct 2026).
# Changes: import path; instrument names replaced by placeholders.
"""
Idempotency-key derivation tests.

The key must be DERIVED, never random: a retry after a crash mid-placement has to reproduce
the same string, or the broker sees an unrelated order and the position opens twice.
"""
from marginops_extract.idempotency import MAX_LEN, correlation_id


def test_same_intent_reproduces_the_same_key():
    a = correlation_id("A", "STOCK_E", "2026-07-30")
    b = correlation_id("A", "STOCK_E", "2026-07-30")
    assert a == b == "A-STOCK_E-2026-07-30"


def test_day_is_part_of_the_key():
    """Regression: omitting the day made a re-entry weeks later collide with the original."""
    assert correlation_id("A", "STOCK_E", "2026-07-30") != \
           correlation_id("A", "STOCK_E", "2026-08-14")


def test_sleeve_is_part_of_the_key():
    assert correlation_id("A", "STOCK_E", "2026-07-30") != \
           correlation_id("C", "STOCK_E", "2026-07-30")


def test_accepts_a_timestamp_and_normalises_to_the_date():
    assert correlation_id("A", "STOCK_E", "2026-07-30T15:40:00") == \
           correlation_id("A", "STOCK_E", "2026-07-30")


def test_never_exceeds_the_broker_cap():
    for sym in ["X", "STOCK_E", "STOCK_LONGNAME", "A" * 40]:
        for sleeve in ["A", "LONGSLEEVENAME"]:
            key = correlation_id(sleeve, sym, "2026-07-30")
            assert len(key) <= MAX_LEN, (sleeve, sym, key, len(key))


def test_truncation_stays_unique_and_deterministic():
    """Two long symbols sharing a prefix must not collapse to the same key."""
    a = correlation_id("A", "VERYLONGSYMBOLNAME" + "AAAA", "2026-07-30")
    b = correlation_id("A", "VERYLONGSYMBOLNAME" + "BBBB", "2026-07-30")
    assert a != b
    assert a == correlation_id("A", "VERYLONGSYMBOLNAME" + "AAAA", "2026-07-30")

