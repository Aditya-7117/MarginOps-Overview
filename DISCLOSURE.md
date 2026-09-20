# Disclosure

This repository is an architecture overview of a private system. The strategy logic is
deliberately excluded.

MarginOps is a private systematic trading platform. What is published here is the execution
half: the order lifecycle, reconciliation against broker truth, the risk mechanisms, durability,
and the test infrastructure. The code excerpts in the README are quoted from the private
repository with file paths and line numbers, so the engineering claims can be checked rather
than taken on trust.

## Published here

- Architecture and sequence diagrams
- The order lifecycle, including how the system responds to a human intervening by hand
- The reconciliation algorithm and its typed discrepancy events
- Margin-aware position sizing: the reserved buffer, the notional cap, the drawdown circuit
  breaker, the graduated shortfall ladder, and machine-readable rejection reasons
- Durability and idempotent order handling
- The test tree, with the commands and their output
- An honest post-mortem of a real incident
- Code excerpts quoted verbatim, with paths and line numbers

## Never published, here or anywhere

- Signal generation logic, feature definitions and regime thresholds
- Entry and exit trigger conditions
- Tuned parameter values, model weights and instrument selection rules
- Configuration files
- Broker credentials, API keys, account identifiers and capital amounts
- Any performance figure: returns, Sharpe, profit factor or drawdown
- Real positions or trade history
- **Backtest results of any kind.** See the note below

## On backtest results

The repository contains a backtesting and research layer, and this overview makes no claim about
its results. The engine's own causality check flagged a look-ahead leak in the pipeline feeding
it. Until that is fixed and the suite re-run end to end, every figure the backtester has produced
is treated as void and none of it is published here, on my CV, or anywhere else.

That is the whole position, and it is stated rather than quietly omitted.

## The line I drew

If a reader could reproduce the trading results from an artefact, it is strategy and it stays
private. If it only shows that the system is correct, recoverable and auditable, it is
engineering and it is published.
