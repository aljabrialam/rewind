# Phase 1 Data Model: Branch Fan-Out

Concrete shapes for `spec.md` → Key Entities. New members in
`src/rewind/engine.py`. `Run` / `Checkpoint` (Spec 001), the port (Spec 000),
and `Instruction` / `validate` (Spec 002) are reused.

---

## 1. Fan-Out Request  *(inputs to `fan_out`)*

| Field | Type | Rule |
|---|---|---|
| `step_id` | string | The common parent checkpoint. Must be restorable (`state == "live"`, has `snapshot`) — else refused, same as Spec 003. |
| `reasoner` | ReasoningPort | The strategist (Spec 002). |
| `n` | int ≥ 1 | Requested strategy count. Capped at `capabilities.MAX_BRANCHES` (3) and at the number of distinct strategies received. |
| `context` | string | Passed to `reasoner.next_instruction`. Optional. |
| `observer` | callable \| None | Called with the progress list on every branch state transition. Optional. |

`branch_from(step_id, strategies: list[str], *, rationales=None, observer=None)` is
the lower-level primitive — same parent precondition, strategies already resolved.

---

## 2. Strategy

Reuses `reasoning.Instruction` — `{instruction: str, rationale: str}`. The
strategist is asked `n` times; responses that fail `validate()` raise
`SchemaError` (nothing is created). Distinct by `instruction` text; duplicates
collapsed.

---

## 3. Derivation

| Value | Meaning | Available when |
|---|---|---|
| `"fork"` | live-VM fork of the parent sandbox (fastest) | a `fork` op is in `capabilities.VERIFIED_OPS` (not today) |
| `"branch"` | create a sandbox from the parent checkpoint's snapshot | `branch` is in `VERIFIED_OPS` (yes — the current default) |

Selected fastest-first from `("fork", "branch")`; the first available wins.
Recorded on `FanOutResult.derivation` and `Engine._last_derivation`.

---

## 4. Branch Progress  *(FR-004-07, NFR-004-04)*

One per branch, updated live under a lock.

| Field | Type | Rule |
|---|---|---|
| `checkpoint_id` | string | The child checkpoint's id. |
| `sandbox_id` | string \| None | The runtime's own sandbox id, byte-for-byte (NFR-004-02). `None` only if creation failed. |
| `state` | `"creating"` \| `"running"` \| `"done"` \| `"failed"` | Advances `creating → running → done`/`failed`. |

The `observer`, if given, is called with `[progress.__dict__ for progress in list]`
after each transition. `FanOutResult.progress` holds the final list.

---

## 5. Branch (child Checkpoint additions)

Reuses `ports.Checkpoint`. For a fan-out child:

| Field | Value |
|---|---|
| `parent_id` | the common parent `step_id` (FR-004-05) |
| `instruction` | the strategy's instruction |
| `rationale` | the strategy's rationale (Spec 002) |
| `sandbox_id` | the branch sandbox's runtime id |
| `snapshot` | **the branch's own** captured snapshot (taken before its sandbox is destroyed) — so Spec 005 can promote by re-derivation |
| `evidence` | this branch's independent `ExecResult` (FR-004-06) |
| `outcome` / `terminal` | `terminal = "failed"` on a non-zero exit or an exception; otherwise unset until Spec 005 |
| `state` | `"live"` while running; the child persists after its sandbox is destroyed |

---

## 6. Fan-Out Result  *(return of `fan_out`; `branch_from` returns `list[Checkpoint]` for back-compat)*

| Field | Type | Rule |
|---|---|---|
| `children` | list[Checkpoint] | One per branch that ran, in strategy order. |
| `ran` | int | How many branches actually ran (≤ `n`, ≤ distinct strategies, ≤ `MAX_BRANCHES`). |
| `requested` | int | The original `n` (so a cap is visible). |
| `derivation` | string | `"fork"` \| `"branch"` — which was used. |
| `elapsed_seconds` | float ≥ 0 | Wall-clock around the whole fan-out. |
| `progress` | list[dict] | The final `BranchProgress` entries. |
| `error` | string \| None | Set only when the fan-out was refused before any sandbox (bad parent, strategist unreachable, schema failure) — mirrors Spec 003's refusal style. |

`as_dict()` — plain-dict form for the console / a fixture.

---

## 7. Branch lifecycle (one branch)

| State | Entry | Exit |
|---|---|---|
| `creating` | sandbox creation issued (part of `provider.branch(snapshot, N)`) | → `running` when the strategy starts; → `failed` if the sandbox never came up |
| `running` | strategy executing via `provider.run` | → `done` on exit 0; → `failed` on non-zero exit or an exception |
| `done` / `failed` | terminal for the branch | its own `snapshot` is taken (if `done`), then its sandbox is destroyed (FR-004-10); the child checkpoint remains in the tree |

**Invariant**: at no point does the count of live branch sandboxes push the total
over `capabilities.CEILING` (FR-004-09, deferred to Spec 000's `BoundedSemaphore`).
After the fan-out returns, the live sandbox count equals its pre-fan-out value
(SC-006).

---

## Type glossary

| Name | Definition |
|---|---|
| `BranchProgress` | dataclass `{checkpoint_id, sandbox_id, state}` |
| `FanOutResult` | dataclass `{children, ran, requested, derivation, elapsed_seconds, progress, error}` + `as_dict()` |
| `Derivation` | `"fork"` \| `"branch"` |
| restorable parent | `Run.is_restorable(step_id)` from Spec 001 |
