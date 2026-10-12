# MarginOps extract

Four infrastructure modules copied from the private MarginOps repository, with the tests that guard
them. They run on their own: no network, no broker, no third-party packages.

| Module | What it decides | Private source |
|---|---|---|
| `idempotency.py` | One deterministic order key per trade intent, so a retry after a crash is recognised as the same order | `live/marginops/utils/idempotency.py` |
| `reconcile.py` | A typed event for every difference between the system's book and the broker's: manual close, manual open, moved stop, cancelled stop, cancelled entry | `live/marginops/engine/reconcile.py` |
| `stop_manager.py` | How to keep raising a protective stop under the exchange's 25-modification cap: modify in place, and once the budget is nearly spent, cancel and place a fresh stop, which resets the counter | `live/marginops/engine/stop_manager.py` |
| `risk_guards.py` | When to force an exit through a missed stop, when to refuse an order the wallet cannot cover, and how fast to de-risk a margin shortfall | `live/marginops/engine/risk_guards.py` |
| `snapshot.py` | The broker position type the reconciler compares against | `live/marginops/broker/base.py` (one type only) |

Every file comes from commit `f1770cc` (2 October 2026), the latest pushed to the private repository. The
logic is unchanged. The edits are import paths, placeholder instrument names and security ids in the tests
(`STOCK_A` and so on), and comment punctuation. The first two lines of each file say exactly what
changed.

## Run it

```bash
python -m pip install -e ".[test]"
python -m pytest
```

32 tests, standard library only, Python 3.10 or later. GitHub Actions runs them on every push.

## What is not here

No signal logic, thresholds, tuned parameters, instrument lists, configuration or broker transport.
The line is drawn in [DISCLOSURE.md](../DISCLOSURE.md).
