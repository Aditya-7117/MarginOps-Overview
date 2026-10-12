# Extracted from the private MarginOps repository: live/marginops/utils/idempotency.py at commit f1770cc (2 Oct 2026).
# Changes: docstring example uses a placeholder symbol; dashes in comments replaced. Logic unchanged.
"""
Correlation-id derivation: the idempotency key every order carries.

The key MUST be deterministic: re-deriving it from the same trade intent after a crash, a
restart or a retry has to produce the same string, so a replayed placement is recognised,
by the broker and by our own reconciler, as the SAME order rather than a new one. A random
id (uuid4) cannot do this: regenerating it after a crash mid-placement yields a different
key, the broker sees an unrelated order, and the position is opened twice.

Identity of a trade intent = (sleeve, instrument, trading day):
  • same instrument, same sleeve, same day   -> the same intent, must collapse to one key
  • same instrument, same sleeve, a later day -> a genuinely different intent
so the day is part of the key. Omitting it (as one call site previously did) makes a
re-entry weeks later collide with the original order's id.

Brokers cap correlation-id length (Dhan: 30 chars). When the natural key would overflow,
the instrument segment is truncated and a short digest of the FULL key is appended, so
uniqueness survives truncation and the result stays reproducible.
"""
from __future__ import annotations

import hashlib

MAX_LEN = 30
_DIGEST_LEN = 4


def correlation_id(sleeve: str, instrument: str, day, *, max_len: int = MAX_LEN) -> str:
    """Deterministic idempotency key for one trade intent. Same inputs -> same key, always.

    >>> correlation_id("A", "STOCK_E", "2026-07-30")
    'A-STOCK_E-2026-07-30'
    """
    d = str(day)[:10]
    key = f"{sleeve}-{instrument}-{d}"
    if len(key) <= max_len:
        return key
    # truncation is lossy, so bind the full key in with a deterministic digest
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:_DIGEST_LEN]
    keep = max_len - len(sleeve) - len(d) - _DIGEST_LEN - 3      # 3 separators
    return f"{sleeve}-{instrument[:max(keep, 1)]}-{d}-{digest}"[:max_len]
