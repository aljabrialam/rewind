# Contract: Run Tree

The in-memory model of an agent run as a tree of checkpoints. Every operation is
a pure function over `Run` state — no runtime, network, or credentials
(NFR-001-01). Implemented as additive changes to `src/rewind/engine.py` (`Run`)
and `src/rewind/ports.py` (`Checkpoint`).

Traces: FR-001-01 … FR-001-09, NFR-001-01 … NFR-001-03.

---

## Tree invariants (hold after every operation)

| # | Invariant | Trace |
|---|---|---|
| I1 | Exactly one checkpoint has `parent_id is None` (the root), at `index 0`. | FR-001-01 |
| I2 | Exactly one `head`, and `head in checkpoints` (once the run has started). | FR-001-05, SC-004 |
| I3 | Every non-root `parent_id` resolves to a known checkpoint. | FR-001-06 |
| I4 | Parent/child links agree both ways; no `children` entry dangles. | FR-001-04 |
| I5 | Every checkpoint is reachable from the root by walking `children`; no cycles; no orphan. | NFR-001-02 |
| I6 | A `step_id`, once assigned, is never changed or reused. | FR-001-03, SC-001 |
| I7 | Identifier assignment does not depend on wall-clock resolution — two adds in one tick get distinct ids. | NFR-001-03, SC-009 |
| I8 | `restore_targets()` contains no `released` or `unreachable` checkpoint. | FR-001-08, SC-005 |

---

## Operations

### `add(cp) -> str`

| | |
|---|---|
| Pre | `cp.parent_id` is `None` (root) or an existing id |
| Effect | assigns `cp.step_id` if blank (short, random, not time-derived); sets `cp.created_at` if unset; appends to `order`; appends `cp.step_id` to the parent's `children`; sets `head = cp.step_id` |
| Post | I1–I7 hold; `order[-1] == cp.step_id` |

### `path_to(step_id) -> list[Checkpoint]`

| | |
|---|---|
| Pre | none (unknown id ⇒ `[]`) |
| Effect | pure read |
| Post | ordered root → `step_id`; each element's `parent_id` equals the previous element's `step_id`; caller performs no traversal (FR-001-01, US1 §2) |

### `as_tree() -> dict`

| | |
|---|---|
| Effect | pure read |
| Post | `{"head", "nodes"}`; `nodes` in `order`; each node carries `id, index, instruction, parent, children, sandbox, state, snapshot, created_at, exit_code, stdout, outcome, terminal, rationale`; drawable with no further queries (FR-001-07, SC-007) |

### `is_restorable(step_id) -> bool`  *(new)*

`True` iff `step_id in checkpoints` and `state == "live"` and `snapshot is not
None`. Pure. (FR-001-08)

### `restore_targets() -> list[str]`  *(new)*

`[id for id in order if is_restorable(id)]`. Never includes a `released` or
`unreachable` checkpoint (I8, SC-005).

### `set_head(step_id) -> None`  *(new)*

| | |
|---|---|
| Pre | `step_id in checkpoints` and `is_restorable(step_id)` |
| On violation | raise `ValueError` naming the reason (unknown / released / unreachable / no snapshot); `head` unchanged |
| Post | `head == step_id`; I2 holds |

Refuses the folded edge case "head moved to a checkpoint whose sandbox has been
released" (FR-001-08).

### `mark_terminal(step_id, outcome) -> None`  *(new)*

| | |
|---|---|
| Pre | `step_id in checkpoints`; `outcome in {"succeeded", "failed", "abandoned"}` |
| On violation | `ValueError` |
| Effect | `checkpoints[step_id].terminal = outcome` |

### `branch_outcome(step_id) -> str | None`  *(new)*

Returns `checkpoints[step_id].terminal` (or `None`). A still-advancing branch tip
has `None` (FR-001-09, SC-006). Pure.

### `check_integrity() -> list[str]`  *(new)*

Returns problem descriptions; empty ⇔ I1–I5 all hold. Used by the NFR-001-02 /
SC-010 tests after a sequence with a failure, an abandonment, and a shared-parent
branch. Pure.

---

## Who sets `state` and `terminal`

| Field/value | Set by | Spec |
|---|---|---|
| `state = "live"` | `add` (default) | 001 |
| `state = "released"` + `terminal = "abandoned"` | `Engine.promote` on losers | 005 (present) |
| `state = "unreachable"` | a checkpoint recorded with no `snapshot` (sandbox destroyed before write) | 001 edge case |
| `terminal = "failed"` | `Engine.step` on a non-zero exit (the failing checkpoint) | 002 |
| `terminal = "succeeded"` | caller via `mark_terminal(tip, "succeeded")` | 001 |

---

## Folded edge cases → contract behaviour

| Edge case | Behaviour |
|---|---|
| Two branches from one parent within the same second | both children get distinct `step_id` (I7); parent `children` holds both in creation order; equal `created_at` is allowed and merges/reorders/drops nothing |
| Head moved to a checkpoint whose sandbox was released | `set_head` raises `ValueError`; `head` unchanged; the released checkpoint is absent from `restore_targets()` |
| Step completes but sandbox destroyed before checkpoint write | checkpoint still `add`ed with `index`, `instruction`, completion state; `snapshot is None`; `state = "unreachable"`; not restorable; `order` still contains it |
| Single-step run that fails | tree = root + one checkpoint with `outcome == "failed"`; that tip `terminal == "failed"`; root still present and restorable if it has a snapshot |
