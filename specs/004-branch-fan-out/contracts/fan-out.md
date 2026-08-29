# Contract: Branch Fan-Out

`Engine.fan_out(step_id, reasoner, n, context="", observer=None) -> FanOutResult`
and the lower-level `Engine.branch_from(step_id, strategies, *, rationales=None,
observer=None) -> list[Checkpoint]`.

Traces: FR-004-01 … FR-004-10, NFR-004-01 … NFR-004-04.

---

## Preconditions (FR-004-05, spec 003 parity)

| Condition | Result |
|---|---|
| parent `step_id` unknown | refused — `FanOutResult.error = "unknown"`, no sandbox, head unchanged |
| parent `state != "live"` | refused — `error = "released"` / `"unreachable"` |
| parent `snapshot is None` | refused — `error = "unreachable"` |
| strategist unreachable / returns nothing | refused — `error` names it, run tree unchanged |
| a strategy response fails `validate()` | `SchemaError` propagates — nothing created |

---

## Strategy acquisition (FR-004-01)

- `fan_out` calls `reasoner.next_instruction(context)` `n` times; each response
  through `validate()` (Spec 002 schema).
- Distinct by `instruction` text; duplicates collapsed.
- Count run = `min(n, MAX_BRANCHES, len(distinct strategies))`; `FanOutResult.ran`
  and `.requested` both reported so a cap or a short strategist is visible.
- `branch_from` skips this step — it takes resolved strategy strings.

---

## Derivation selection (FR-004-03, SC-009)

```
PREFERENCE = ("fork", "branch")      # fastest first
derivation = first d in PREFERENCE whose backing op is in capabilities.VERIFIED_OPS
```

Today → `"branch"` (snapshot-based). Recorded on `FanOutResult.derivation` and
`Engine._last_derivation`. If `fork` is added to the map later, the fan-out
prefers it with no other change (FR-004-03 fallback is the reverse: a missing
preferred op drops to the next).

---

## Ordered port calls (NFR-004-03)

For N branches, no failures. Executions are **concurrent**, so the parity test
asserts **counts per operation**, not sequence:

| Operation | Count | Purpose |
|---|---|---|
| `branch` | N | create N sandboxes from the parent snapshot |
| `run` | N | execute each strategy (concurrent) |
| `checkpoint` | N | each branch's own snapshot (only for branches that exited 0) |
| `destroy` | N | cleanup — every branch sandbox, on every path |

A branch that exits non-zero contributes `run×1`, `destroy×1`, no `checkpoint`.

---

## Guarantees

| # | Obligation | Trace |
|---|---|---|
| C1 | Ask the strategist for exactly `n` structured strategies; reject a non-conforming response. | FR-004-01 |
| C2 | Create one isolated sandbox per (capped) strategy, all from the same parent snapshot, via the selected derivation. | FR-004-02, FR-004-03 |
| C3 | Run the branches concurrently — total wall-clock ≈ the slowest single branch, ≤ 1.5× one branch for N equal branches. | FR-004-04, NFR-004-01, SC-003 |
| C4 | Record each branch as a child checkpoint of the common parent; the parent's own fields and `run.head` are unchanged. | FR-004-05, SC-002 |
| C5 | Capture `ExecResult` independently per branch; no branch's evidence derived from another's. | FR-004-06, SC-004 |
| C6 | Maintain a live per-branch progress list `{checkpoint_id, sandbox_id, state}`; call `observer` on each transition; return it on `FanOutResult.progress`. Sandbox ids are the runtime's own, unmodified. | FR-004-07, NFR-004-02, NFR-004-04, SC-007, SC-008 |
| C7 | A branch failure (non-zero exit, exception, or failed creation) sets that child's `evidence` + `terminal = "failed"` + progress `failed`, and does **not** abort the fan-out; the other children are returned. | FR-004-08, SC-005 |
| C8 | The live sandbox count never exceeds `capabilities.CEILING` during the fan-out (deferred to Spec 000's `BoundedSemaphore`), and returns to its pre-fan-out value afterwards. | FR-004-09, SC-006 |
| C9 | Every branch sandbox created is destroyed in a `finally` — success, branch-failure, and operation-raised paths — without touching any child checkpoint's `snapshot`. | FR-004-10, SC-006 |
| C10 | `FanOutResult.as_dict()` / `branch_from`'s children are renderable with no further computation. | NFR-004-04 |
| C11 | The offline path (`FakeProvider` + `ReplayReasoner`) completes effectively instantly with no network and no credentials. | NFR-004-01, NFR-004-03, SC-010 |

---

## Provisional change to `Engine.promote` (Spec 005 territory)

Because branch sandboxes are now destroyed (C9), `promote(winner, losers)` can no
longer keep the winner's live handle. It is updated to re-derive the winner from
`winner_cp.snapshot` (`provider.branch(snapshot, 1)[0]`) and register that as the
head handle; losers are marked `released` / `abandoned` with no handle to
destroy. Flagged provisional — Spec 005 formalises promotion.

---

## Edge behaviours

| Edge case | Behaviour |
|---|---|
| `n` > `MAX_BRANCHES` | capped at `MAX_BRANCHES`; `ran` < `requested` |
| strategist returns fewer distinct strategies than `n` | run what was received; `ran` reflects it; no fabricated strategies |
| ceiling has no room for the full set | branches that fit run; surplus gets a bounded wait then a `capacity` outcome for that branch (Spec 000); started branches intact |
| two branches finish at the same instant | both children recorded; shared time does not merge/reorder/drop |
| a branch never terminates | the port's bounded execution applies; that branch `failed`, its sandbox destroyed with the rest |
| child inspected after the fan-out | keeps id, instruction, evidence, and its own `snapshot`; its live sandbox is gone; Spec 005 can still act on it |
