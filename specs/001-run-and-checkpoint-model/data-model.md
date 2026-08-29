# Phase 1 Data Model: Run and Checkpoint Model

Concrete shapes for `spec.md` → Key Entities. Existing types in
`src/rewind/` reused and extended where noted.

---

## 1. Checkpoint (`ports.Checkpoint`, extended)

| Field | Type | Rule |
|---|---|---|
| `step_id` | string | Stable identifier, unique within the run, opaque, not time-derived. `"root"` for the root; otherwise short random. Never reassigned (FR-001-03, NFR-001-03). |
| `index` | int | Ordinal position; root is `0` (FR-001-01). |
| `instruction` | string | The step's instruction; `"(start)"` for the root (FR-001-01). |
| `parent_id` | string \| None | `None` only for the root (FR-001-06). |
| `children` | list[string] | Child identifiers, in creation order. May hold more than one (FR-001-04). |
| `sandbox_id` | string \| None | The sandbox associated with this checkpoint (FR-001-06). |
| `snapshot` | string \| None | Reference to the captured runtime state, when one exists (FR-001-02). Absence ⇒ not restorable. |
| `created_at` | string (ISO-8601 UTC) | **NEW** — set when the checkpoint is added; display + tie-break only (FR-001-06). |
| `state` | `"live"` \| `"released"` \| `"unreachable"` | Whether the runtime state can be returned to (FR-001-08). |
| `evidence` | ExecResult \| None | From Spec 002. `None` for the root. |
| `outcome` | `"ok"` \| `"failed"` (derived) | From Spec 002 — computed from `evidence` only. |
| `rationale` | string | From Spec 002 — distinct from evidence. |
| `halt_reason` | `"step-failed"` \| `"step-bound"` \| None | From Spec 002 — the fine cause a branch stopped. |
| `terminal` | `"succeeded"` \| `"failed"` \| `"abandoned"` \| None | **NEW** — the branch's terminal outcome, set on the tip checkpoint (FR-001-09). |

---

## 2. Run (`engine.Run`, extended)

| Field | Type | Rule |
|---|---|---|
| `checkpoints` | dict[str, Checkpoint] | All nodes, keyed by `step_id`. |
| `order` | list[str] | Insertion order of every checkpoint. Source of truth for "ordered sequence of steps" (FR-001-01). |
| `head` | string \| None | Exactly one head once the run has started (FR-001-05). |

### Operations (all pure over in-memory state — NFR-001-01)

| Operation | Intent | Post-condition / invariant |
|---|---|---|
| `add(cp) -> str` | Append a checkpoint; link it to its parent; make it the head | `step_id` assigned if blank; `order` grows by one; parent's `children` grows by one; `head == cp.step_id` |
| `path_to(step_id) -> list[Checkpoint]` | Root-to-node lineage | Ordered root → node; caller does no traversal (FR-001-01/US1) |
| `as_tree() -> dict` | The one renderable form | `{"head": ..., "nodes": [...]}`; every checkpoint once; each node carries every FR-001-07 field |
| `is_restorable(step_id) -> bool` | **NEW** | `True` iff known ∧ `state == "live"` ∧ `snapshot is not None` (FR-001-08) |
| `restore_targets() -> list[str]` | **NEW** | ids in `order` for which `is_restorable` is `True`; contains no released/unreachable node (FR-001-08, SC-005) |
| `set_head(step_id) -> None` | **NEW** | Refuses (`ValueError`) an unknown or non-restorable target; otherwise sets `head` (FR-001-08 + folded edge case) |
| `mark_terminal(step_id, outcome) -> None` | **NEW** | `outcome ∈ {succeeded, failed, abandoned}` else `ValueError`; sets `checkpoints[step_id].terminal` |
| `branch_outcome(step_id) -> str \| None` | **NEW** | Returns that checkpoint's `terminal`; `None` while advancing (FR-001-09) |
| `check_integrity() -> list[str]` | **NEW** | Empty list ⇔ sound tree (R4 rules); used by NFR-001-02 / SC-010 tests |

---

## 3. Checkpoint state machine (`state` field)

| State | Meaning | Entered by | Restorable? |
|---|---|---|---|
| `live` | present and usable | `add` (default) | only if it also has a `snapshot` |
| `released` | runtime state deliberately freed | `Engine.promote` on losers (Spec 005) | never |
| `unreachable` | runtime state lost or never existed | a step completing after its sandbox was destroyed (folded edge case); a checkpoint recorded with no `snapshot` | never |

`terminal` is orthogonal to `state`: a `released` checkpoint typically also has
`terminal == "abandoned"`; a `live` checkpoint at the end of a good run has
`terminal == "succeeded"`.

---

## 4. Branch Terminal Outcome

String on the tip checkpoint: `"succeeded"` | `"failed"` | `"abandoned"` | `None`.

| Value | Set when |
|---|---|
| `succeeded` | a caller finishes a branch cleanly — `mark_terminal(tip, "succeeded")` |
| `failed` | `Engine.step` records a non-zero exit — set on the failing checkpoint |
| `abandoned` | `Engine.promote` sets it on each loser checkpoint |
| `None` | the branch is still advancing |

---

## 5. Renderable Tree (`as_tree()` output)

```
{
  "head": "<step_id>",
  "nodes": [
    {
      "id", "index", "instruction", "parent", "children",   # structure
      "sandbox", "state", "snapshot", "created_at",          # FR-001-06/08
      "exit_code", "stdout",                                 # evidence (Spec 002)
      "outcome", "terminal",                                 # derived + branch fact
      "rationale"                                            # distinct from evidence
    }
  ]
}
```

`nodes` is in `order`. `stdout` is truncated to 400 chars for the render only;
the full value stays on `Checkpoint.evidence`. A consumer draws the tree from
this alone (FR-001-07, SC-007).

---

## Type glossary

| Name | Definition |
|---|---|
| `Checkpoint` | `ports.Checkpoint` + `created_at: str`, `terminal: str | None` |
| `Run` | `engine.Run` + the six new pure operations above |
| restorable | `state == "live" and snapshot is not None` |
| branch tip | the last checkpoint on a forward path of children |
