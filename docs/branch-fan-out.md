# Branch Fan-Out (spec 004)

Explore several continuations from one checkpoint at once, each in its own
isolated machine — settle a choice by running it, not predicting it. Full spec:
[`specs/004-branch-fan-out/`](../specs/004-branch-fan-out/).

## The operations

| Call | Purpose |
|---|---|
| `Engine.fan_out(step_id, reasoner, n, context="", observer=None) -> FanOutResult` | Ask the strategist for `n` structured strategies (Spec 002 schema), then run the fan-out. Business refusals (bad parent, unreachable strategist) come back as `FanOutResult.error`. |
| `Engine.branch_from(step_id, strategies, *, rationales=None, observer=None) -> list[Checkpoint]` | The primitive: strategy strings already resolved. |
| `Engine._select_derivation() -> str` | The fastest branch derivation the capability map declares — `("fork", "branch")`, first one in `capabilities.VERIFIED_OPS` wins. Today: `"branch"` (snapshot-based). |

## What it guarantees

- **N isolated sandboxes from one parent**, one per (capped, deduped) strategy — capped at `MAX_BRANCHES` = 3 (FR-004-02).
- **Concurrent execution** — total wall-clock ≈ the slowest branch, not the sum (FR-004-04 / SC-003).
- **A child checkpoint per branch**, each with its **own** snapshot and independent evidence; the run head stays at the parent (FR-004-05/06).
- **Live per-branch progress** — `{checkpoint_id, sandbox_id, state}` where `state` advances `creating → running → done`/`failed`; the `observer` is called on every transition; sandbox ids are the runtime's own, unmodified (FR-004-07 / NFR-004-02/04).
- **A failing branch is a result, not an abort** — its child gets `terminal="failed"`; the others still come back (FR-004-08 / SC-005).
- **Every branch sandbox destroyed** — `try/finally`, on the success, branch-failure, and operation-raised paths; the child checkpoints and their snapshots survive (FR-004-10 / SC-006).
- **Ceiling held** — deferred to Spec 000's `BoundedSemaphore`; branches that don't fit are reported as capacity failures, the rest run.

`FanOutResult`: `{children, ran, requested, derivation, elapsed_seconds, progress, error}` + `as_dict()`.

## Provisional

`Engine.promote(winner, losers)` now re-derives the winner from its snapshot
(branch sandboxes are destroyed by the fan-out). Spec 005 will formalise
promotion.

## Running

```bash
pytest tests/unit/test_fan_out.py -q                        # 25 offline tests
pytest tests/contract/test_fan_out_contract.py -m live -q   # op-count parity + budget (needs DAYTONA_API_KEY)
FAKE=1 python demo.py                                       # the fan-out beat: derivation, 3 live ids, states
```
