# Critic Evaluation and Promotion (spec 005)

**This closes the Constitution Article IX loop.** Propose (004) → execute (002) →
**judge on the branches' own evidence → promote the winner → release the rest**
→ fan out again. Full spec:
[`specs/005-critic-evaluation-and-promotion/`](../specs/005-critic-evaluation-and-promotion/).

## The operations (`src/rewind/engine.py`)

| Call | Does |
|---|---|
| `rank_by_evidence(branches) -> dict` | The deterministic fallback — a **pure, total** ranking by `(exit_code, elapsed, index, id)`. Works for any non-empty set, all-failed included. Each branch gets a numeric `score`. |
| `Engine._evidence_bundle(branches) -> str` | Evidence only — exit, elapsed, truncated output, id. **Never** a branch's rationale (FR-005-01). |
| `Engine.evaluate(branches, critic, context="") -> dict` | Bundle → critic (same `ReasoningPort` as the strategist) under `capabilities.CRITIC_WAIT` → `reasoning.validate_verdict` → on any timeout / unreachable / rejected verdict, the deterministic fallback, with `fallback_trigger` recorded. Empty set refused; single-branch promoted without a critic call; a still-running branch is excluded, never scored. |
| `Engine.promote(winner, losers, *, verdict=None, parent_id=None) -> dict` | Re-derive the winner from its own snapshot (**headless-safe** on failure — head unchanged, error reported); move the head; release every loser (**idempotent, continue-on-failure, classified**); `record_verdict` on the parent. Positional `promote(winner, losers)` still valid. |
| `Engine.judge_and_promote(branches, critic, ...) -> dict` | One turn of the loop: `evaluate` → build the write-once Verdict Record → `promote`. |
| `Run.record_verdict(parent_id, record)` / `get_verdict` | Write-once per parent (FR-005-06 / SC-007). |

## What lands on the parent checkpoint

`Checkpoint.verdict` = `{chosen, scores, reason, reason_unsupported, fallback_used,
fallback_trigger, excluded, recorded_at}`. `console_fixture` surfaces the most
recent recorded verdict on the head's lineage, so the console's Verdict block
shows it.

## Guarantees

- The critic sees **evidence, not self-description** (FR-005-01).
- A malformed verdict (unknown branch, missing score, bad structure, snapshot-less
  choice) → rejected → deterministic fallback; a winner is still promoted (FR-005-03/07).
- A hung reasoning endpoint → fallback within `CRITIC_WAIT`; the round never stalls (NFR-005-03).
- Losers are `released` + `abandoned`, kept in the tree; release never blocks on
  a failure or an already-absent sandbox (FR-005-05).
- The run is never left headless (FR-005-04).
- The promoted head is a valid fan-out origin; a loser is not — the loop turns again (FR-005-08).

## Running

```bash
pytest tests/unit/test_critic.py -q                     # 31 offline tests
pytest tests/contract/test_critic_contract.py -m live -q   # op parity + budget (needs DAYTONA_API_KEY + LLM_API_KEY)
FAKE=1 python demo.py                                   # full loop: steps → fail → fan-out → JUDGE + PROMOTE → restore
```
