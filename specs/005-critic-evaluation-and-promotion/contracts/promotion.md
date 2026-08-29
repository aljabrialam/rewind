# Contract: Promotion

`Engine.promote(winner_step_id, losers, *, verdict=None, parent_id=None) -> dict`
and `Engine.judge_and_promote(branches, critic, context="", parent_id=None) -> dict`.

Traces: FR-005-04, FR-005-05, FR-005-06, FR-005-08, NFR-005-04.

---

## Ordered port calls (NFR-005-04)

For a round over N branches, critic path, no failures:

| Operation | Count | Purpose |
|---|---|---|
| `branch` | 1 | re-derive the winner's sandbox from its own snapshot |
| `destroy` | N − 1 | release each loser (idempotent — a no-op if already gone) |

The critic call is a **reasoning-port** call — it does **not** appear in
`provider.calls`. The parity test asserts this provider op multiset on both
providers.

---

## `promote` obligations

| # | Obligation | Trace |
|---|---|---|
| C1 | Re-derive the winner from `checkpoints[winner].snapshot` via `provider.branch(snapshot, 1)`; install as `self.live[winner]`. | FR-005-04 |
| C2 | On re-derivation failure: return `{..., error: "<classified msg>"}`, **leave `self.run.head` unchanged** (never headless), still run C3. | FR-005-04 (headless safety) |
| C3 | On success: `self.run.head = winner` (Spec 001 head mechanism). | FR-005-04 |
| C4 | For each loser: pop its handle (if any), `provider.destroy` it inside try/except, set `checkpoint.state = "released"` and `checkpoint.terminal = "abandoned"`, append `{sid, released: bool, error: "<class>" | None}` to the result. | FR-005-05 |
| C5 | Release is **idempotent** — a loser with no live handle is `released: True`, not an error. | FR-005-05 |
| C6 | One loser's release raising MUST NOT stop the others or the promotion — the loop continues, the failure is reported with its classification. | FR-005-05, SC-009 |
| C7 | Loser checkpoints stay in the tree — id, instruction, evidence, snapshot untouched; only `state`/`terminal` change. `run.check_integrity()` still `[]`. | FR-005-05, SC-004 |
| C8 | If `verdict` and `parent_id` are given: `run.record_verdict(parent_id, verdict)` — **write-once** (a second call for the same parent is a no-op). | FR-005-06, SC-007 |
| C9 | The positional call `promote(winner, [losers])` (no keywords) keeps working for existing callers (`demo.py`). | back-compat |

Return: `{head, winner, losers: [{sid, released, error}], verdict_recorded: bool, error: str | None}`.

---

## `judge_and_promote` obligations

| # | Obligation | Trace |
|---|---|---|
| J1 | Resolve `parent_id` from the branches' common `parent_id` when not passed. | FR-005-06 |
| J2 | `evaluate(branches, critic, context)` → Verdict Result; build the Verdict Record `{chosen, scores, reason, reason_unsupported, fallback_used, fallback_trigger, recorded_at}`. | FR-005-02/07 |
| J3 | `chosen` from the result maps to a branch `step_id`; call `promote(chosen, <other branch ids>, verdict=record, parent_id=parent_id)`. | FR-005-04/05/06 |
| J4 | If `evaluate` returned `error` (empty set) → return it; head unchanged. | FR-005-10 |
| J5 | Return `{**promote_result, verdict: record, evaluate: <result>}`. | US3 |

---

## Loop repeats (FR-005-08, SC-008)

After `judge_and_promote`, the new head is `live` with a `snapshot`, so
`is_restorable(head)` is `True` and `Engine.fan_out(head, …)` proceeds. A
**loser** checkpoint (`state == "released"`) fails `is_restorable` and is refused
as a fan-out origin — same rule as restore (Spec 001/003). A test runs two full
rounds and asserts each round's verdict is recorded against its own parent and
the head is the second round's winner.

---

## Edge behaviours

| Edge case | Behaviour |
|---|---|
| every branch failed | fallback returns a total order; least-bad promoted (it has a snapshot); reason records "no branch exited 0" |
| two identical evidence | critic may pick either; fallback tie-breaks on `index` then `step_id`; reason notes the tie |
| critic names a destroyed / no-snapshot branch | `validate_verdict` rejects → fallback (which only ranks snapshot-bearing branches as head-eligible) |
| critic reason cites no evidence | `reason_unsupported = true`; promotion still proceeds; flag in the record |
| critic times out | `fallback_trigger = "critic-timeout"`; fallback within `CRITIC_WAIT`; winner promoted |
| a branch still running | waited ≤ `CRITIC_WAIT/4`, then excluded and recorded; not scored |
| winner's sandbox already released | expected — `promote` re-derives from snapshot (C1); re-derivation failure → C2 headless-safe |
| fan-out requested from a loser | refused (released checkpoint is not a valid origin) |
