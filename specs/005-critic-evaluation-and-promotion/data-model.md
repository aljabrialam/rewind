# Phase 1 Data Model: Critic Evaluation and Promotion

New members in `engine.py` / `reasoning.py` / `ports.py`. `Run` / `Checkpoint`
(Spec 001), the port (Spec 000), the reasoning port (Spec 002), and the fan-out
children (Spec 004) are reused.

---

## 1. Evidence Bundle  (input to the critic, FR-005-01)

Built by `Engine._evidence_bundle(branches) -> str`. One section per branch:

```
branch <step_id> | exit <exit_code> | elapsed <elapsed>s
output:
<stdout, truncated>
---
```

Reads only `Checkpoint.step_id` and `Checkpoint.evidence` (exit_code, stdout,
elapsed). **Never** `Checkpoint.rationale` or any agent narration. This string is
the critic's `context`.

---

## 2. Verdict  (`reasoning.Verdict`, the critic's structured response)

| Field | Type | Rule (`validate_verdict`, else `VerdictSchemaError` → fallback) |
|---|---|---|
| `chosen` | str | present; a string; ∈ the submitted `branch_ids`; the chosen branch has a non-null `snapshot` |
| `scores` | dict[str, float] | present; covers **every** id in `branch_ids`; each value coercible to `float`. A `list[{branch, score}]` form is normalised to this. |
| `reason` | str | present; non-empty |

`validate_verdict(payload, branch_ids)` also computes `reason_unsupported` — a
**soft** check: `True` when `reason` contains none of {an exit code digit next to
"exit", a branch id substring, the words "output"/"stdout"/"elapsed"}. Not a
rejection (Edge Cases).

---

## 3. Verdict Record  (`Checkpoint.verdict`, write-once — FR-005-06)

Stored on the **parent** checkpoint via `Run.record_verdict(parent_id, record)`
(sets only if currently `None`).

| Field | Type | Source |
|---|---|---|
| `chosen` | str | the promoted branch's `step_id` |
| `scores` | dict[str, float] | critic's, or the fallback's per-branch `score` |
| `reason` | str | critic's `reason`, or the fallback's generated reason |
| `reason_unsupported` | bool | soft check (critic path only; `False` on fallback) |
| `fallback_used` | bool | `True` when the deterministic ranking decided it |
| `fallback_trigger` | str \| None | `"critic-timeout"` \| `"critic-unreachable: …"` \| `"verdict-rejected: …"` \| `"single-branch"` \| `None` |
| `recorded_at` | ISO-8601 str | when written |

Immutable for that parent once written (SC-007).

---

## 4. Deterministic Ranking  (`rank_by_evidence`, pure + total — NFR-005-02)

| Aspect | Rule |
|---|---|
| sort key | `(exit_code or 99, elapsed or 1e9, index, step_id)` — strict total order for any non-empty set, all-failed included |
| `winner` | index of the first branch after sorting (return shape unchanged) |
| `scores[i]` | gains `score = -(exit_code * 1e6) - elapsed` (higher = better) alongside `branch` / `exit_code` |
| `reason` | notes a tie when the top two share `(exit_code, elapsed)`; notes "no branch exited 0" for an all-failed set |
| `provider` | `"deterministic-fallback"` |

Pure: no `self`, no I/O. Total: returns for any `len(branches) >= 1`.

---

## 5. Verdict Result  (return of `Engine.evaluate`)

| Field | Type | Meaning |
|---|---|---|
| `chosen` | str \| None | chosen branch `step_id`; `None` only on `error` |
| `scores` | dict[str, float] | per-branch score |
| `reason` | str | the reason (critic's or generated) |
| `reason_unsupported` | bool | soft-check flag |
| `fallback_used` | bool | — |
| `fallback_trigger` | str \| None | — |
| `excluded` | list[str] | branch ids excluded for not finishing (FR-005-09) |
| `error` | str \| None | `"no branches"` / `"no snapshot on any branch"` etc. |

---

## 6. Promotion state machine  (`Engine.promote` / `judge_and_promote`)

| State | Entry | Exit |
|---|---|---|
| `evaluating` | `judge_and_promote(branches, critic)` | empty set → `refused("no branches")`; single-with-snapshot → straight to `promoting`; else build bundle → critic (bounded) → `validate_verdict` → verdict result (critic or fallback) |
| `promoting` | a verdict result with a `chosen` that has a snapshot | re-derive winner sandbox from its snapshot; on failure → `headless-safe` (head unchanged, `error` set, losers still released); else move head |
| `releasing` | winner installed (or re-derivation failed) | for each loser: pop handle, `destroy` in try/except, mark `released` + `terminal="abandoned"`, record `{sid, released, error}`; idempotent; one failure never breaks the loop |
| `recording` | releases done | `run.record_verdict(parent_id, record)` (write-once) |
| `done` | — | return `{head, winner, losers:[…], verdict_recorded, error}` |
| `refused` | empty set / no eligible branch | head unchanged; `error` names why |

**Invariant**: the run is never left headless — on any promotion failure the head
stays where it was and the failure is reported (FR-005-04).

---

## 7. Critic

The reasoning agent in the judging role. **Same** `ReasoningPort` as the
strategist (`next_instruction(context) -> Mapping`). Live implementation +
`ReplayReasoner` for `fixtures/reasoning/critic-*.json`. `capabilities.CRITIC_WAIT`
bounds the call.

---

## Type glossary

| Name | Definition |
|---|---|
| `Verdict` | frozen dataclass `{chosen: str, scores: dict[str,float], reason: str}` |
| `VerdictSchemaError` | `SchemaError` subclass raised by `validate_verdict` |
| `Checkpoint.verdict` | `dict | None` — the write-once Verdict Record on a parent |
| `CRITIC_WAIT` | `capabilities` constant — bounded critic wall-clock (default 8s) |
| branch-eligible | a branch with a non-null `snapshot` (can become head) |
