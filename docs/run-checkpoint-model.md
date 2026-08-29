# Run and Checkpoint Model (spec 001)

An agent run is a **tree of checkpoints**, not a transcript. Any earlier moment
stays addressable after the run moves past it. Full spec:
[`specs/001-run-and-checkpoint-model/`](../specs/001-run-and-checkpoint-model/).

## The pieces

| File | Role |
|---|---|
| `src/rewind/ports.py` → `Checkpoint` | A tree node: `step_id` (stable, not time-derived), `index`, `instruction`, `parent_id`, `children`, `sandbox_id`, `snapshot`, `created_at`, `state` (`live`/`released`/`unreachable`), `evidence`/`outcome`/`rationale` (spec 002), `terminal` (`succeeded`/`failed`/`abandoned`). |
| `src/rewind/engine.py` → `Run` | The tree + pure operations: `add`, `get`, `path_to`, `as_tree`, `is_restorable`, `restore_targets`, `set_head`, `mark_terminal`, `branch_outcome`, `check_integrity`. Every one is a pure function over in-memory state — no runtime, network, or credentials. |

## Guarantees

- **Stable identifiers** — a `step_id` is assigned once and never changes or is reused; assignment does not depend on wall-clock resolution (two adds in one tick get distinct ids). (FR-001-03, NFR-001-03)
- **A tree, not a list** — a checkpoint may hold many children; creating a child only appends to the parent's `children`. Exactly one `head` at all times. (FR-001-04/05)
- **Released is never restorable** — `is_restorable` = `live` ∧ has a `snapshot`; `restore_targets()` excludes every released/unreachable node; `set_head` refuses a non-restorable target. (FR-001-08)
- **Every stopped branch has one terminal outcome** — `failed` (set by `Engine.step` on a non-zero exit), `abandoned` (set by `Engine.promote` on losers), `succeeded` (set by a caller), or `None` while advancing. (FR-001-09)
- **One renderable form** — `as_tree()` carries all 14 node fields; a viewer draws the tree with no second pass. `demo.py` writes it to `fixtures/tree.json`; `ui/console.html` reads it. (FR-001-07)
- **Structurally sound under stress** — `check_integrity()` returns `[]` after a run with a failed step, an abandoned branch, and two branches from one parent. (NFR-001-02, SC-010)

## Running

```bash
pytest tests/unit/test_run_tree.py -q     # 33 pure-logic tests, sub-second, offline
FAKE=1 python demo.py                     # writes fixtures/tree.json from Run.as_tree()
```
