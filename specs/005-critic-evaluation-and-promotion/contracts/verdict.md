# Contract: Critic Verdict

`reasoning.validate_verdict(payload: Mapping, branch_ids: Sequence[str]) -> Verdict`
and `Engine.evaluate(branches, critic, context="") -> dict` (Verdict Result).

Traces: FR-005-01, FR-005-02, FR-005-03, FR-005-07, FR-005-09, FR-005-10,
NFR-005-01, NFR-005-02, NFR-005-03.

---

## The evidence bundle (FR-005-01, SC-001)

`Engine._evidence_bundle(branches)` — plain text, one section per branch, from
`Checkpoint.step_id` + `Checkpoint.evidence` only:

```
branch <id> | exit <exit_code> | elapsed <elapsed>s
output:
<stdout, truncated ~800 chars>
---
```

MUST NOT contain any branch's `rationale` or any other agent narration. This
string is passed to `critic.next_instruction(...)` as the context.

---

## Verdict schema (FR-005-02) — `validate_verdict`

| Field | Accept | Reject → `VerdictSchemaError` (caught → fallback) |
|---|---|---|
| `chosen` | a string in `branch_ids` whose branch has a non-null `snapshot` | missing; not a string; not in `branch_ids`; names a branch with no `snapshot` |
| `scores` | a mapping with a `float`-coercible value for **every** id in `branch_ids` (a `list[{branch, score}]` is normalised) | missing; not a mapping/list; omits any id; a non-numeric value |
| `reason` | a non-empty string | missing; empty |

**`reason_unsupported`** (soft — computed, never a rejection): `True` when
`reason` cites no evidence — none of an exit-code reference, a branch id
substring, or the words `output` / `stdout` / `elapsed`. Recorded on the result,
promotion still proceeds (Edge Cases).

---

## `Engine.evaluate` — bounded call + fallback (FR-005-07, NFR-005-03)

1. **empty** branch set → `{error: "no branches"}`, no critic call.
2. **single** branch with a snapshot → `{chosen: <id>, fallback_used: true,
   fallback_trigger: "single-branch", …}`, no critic call.
3. any branch **not terminal** (`evidence is None`, or `progress.state` /
   `terminal` not in a finished state) → wait up to `CRITIC_WAIT / 4`, then
   `excluded += [id]`, record it, judge the rest (FR-005-09 — never scored).
4. build the bundle; run `critic.next_instruction(bundle)` in a thread with
   `future.result(timeout=CRITIC_WAIT)`:
   - `FuturesTimeoutError` → fallback, `fallback_trigger = "critic-timeout"`
   - any other exception → fallback, `"critic-unreachable: <msg>"`
   - result → `validate_verdict(result, ids)`:
     - `VerdictSchemaError` → fallback, `"verdict-rejected: <why>"`
     - ok → critic verdict; `fallback_used = false`
5. **fallback** = `rank_by_evidence` over the branch-eligible set; `chosen` =
   the top branch's `step_id`; `scores` from the ranking; `reason` generated.

Every path returns a Verdict Result with a `chosen` (unless `error`), `scores`
covering the judged branches, `fallback_used`, `fallback_trigger`, `excluded`.

---

## Determinism (NFR-005-01, SC-011)

The same recorded critic response (via `ReplayReasoner` over
`fixtures/reasoning/critic-*.json`) over the same branch set MUST yield an
identical Verdict Result and, after promotion, an identical Verdict Record. The
fallback's tie-break (`index`, then `step_id`) makes the fallback path equally
reproducible.

---

## Totality of the fallback (NFR-005-02, SC-006)

`rank_by_evidence` is a pure function and returns a strict total ordering for any
`len(branches) >= 1`, including a set where **every** branch has a non-zero exit
— ordered by `(exit_code, elapsed, index, step_id)`. No reasoning agent, no
network, no credentials.
