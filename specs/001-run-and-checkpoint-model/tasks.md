---
description: "Task list for Run and Checkpoint Model implementation"
---

# Tasks: Run and Checkpoint Model

**Feature**: `001-run-and-checkpoint-model`

**Input**: Design documents from `specs/001-run-and-checkpoint-model/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/run-tree.md](contracts/run-tree.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED (Constitution Article VI — this is the canonical base-layer feature). Test names are the source of truth in [quickstart.md](quickstart.md).

**Nature**: governs an existing implementation (`src/rewind/engine.py` `Run`/`Checkpoint`). All edits are **additive**. No external dependency — every test runs offline.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US5, on user-story tasks only

## Path Conventions

Single project. `src/rewind/ports.py` (Checkpoint fields), `src/rewind/engine.py` (Run ops), `tests/unit/test_run_tree.py` (new).

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_run_tree.py` (module docstring + imports: `from rewind.engine import Run, Engine`; `from rewind.ports import Checkpoint`)

**Checkpoint**: `pytest -q` still green (67 from specs 000/002).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the two new `Checkpoint` fields. Blocks Phases 3–7.

- [X] T002 In `src/rewind/ports.py` add to `Checkpoint`: `created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())` and `terminal: str | None = None`. (`datetime`/`timezone` already imported.) Keep field order so existing positional construction in `engine.py` still works — add both at the end of the dataclass.
- [X] T003 In `src/rewind/engine.py` `Run.add`: set `cp.created_at` only if falsy (respect a caller-supplied value); leave id assignment as-is (`uuid.uuid4().hex[:8]` — already time-independent).

**Checkpoint**: `Checkpoint(...)` gets a `created_at`; `import rewind.engine` clean; `pytest -q` still 67.

---

## Phase 3: User Story 1 — An earlier moment stays addressable (Priority: P1) 🎯 MVP

**Goal**: stable identifiers, ordered steps, root-to-node lineage with no caller traversal.

**Independent Test**: record an early checkpoint's id, advance the run, confirm it still resolves; `path_to` returns the ordered lineage.

### Tests for User Story 1

- [X] T004 [P] [US1] `tests/unit/test_run_tree.py`: `test_run_is_ordered_steps`, `test_step_carries_index_instruction_state`, `test_identifier_stable_after_run_advances` (SC-001), `test_path_to_is_ordered_root_to_node` (SC-002)
- [X] T005 [P] [US1] `tests/unit/test_run_tree.py`: `test_lookup_unknown_id_returns_nothing`, `test_checkpoint_records_snapshot_reference` (FR-001-02)

### Implementation for User Story 1

- [X] T006 [US1] Verify `Run.path_to` returns `list[Checkpoint]` root→node and handles an unknown id as `[]`; adjust only if a test fails. Add a `Run.get(step_id) -> Checkpoint | None` helper if the tests need a non-raising lookup.

**Checkpoint**: MVP — any earlier checkpoint stays addressable by a stable id.

---

## Phase 4: User Story 2 — The run is a tree, not a list (Priority: P1)

**Goal**: a parent holds multiple children; exactly one head; each child names parent + sandbox + created_at.

### Tests for User Story 2

- [X] T007 [P] [US2] `tests/unit/test_run_tree.py`: `test_parent_can_have_two_children` (FR-001-04), `test_child_creation_does_not_mutate_parent` (SC-003), `test_exactly_one_head` (SC-004)
- [X] T008 [P] [US2] `tests/unit/test_run_tree.py`: `test_checkpoint_has_parent_sandbox_and_created_at` (FR-001-06), `test_two_checkpoints_same_second_distinct_ids` (NFR-001-03, SC-009)

### Implementation for User Story 2

- [X] T009 [US2] Confirm `Run.add` appends to the parent's `children` and never rewrites the parent's `index`/`instruction`/`state`; add an assertion helper `Run.check_integrity()` stub returning `[]` (filled in Phase 8) so shared-parent tests can call it.

**Checkpoint**: the model is a tree; branching (004) has a parent that holds many children.

---

## Phase 5: User Story 3 — A released checkpoint is never restorable (Priority: P2)

**Goal**: `is_restorable`, `restore_targets`, `set_head` refusal.

### Tests for User Story 3

- [X] T010 [P] [US3] `tests/unit/test_run_tree.py`: `test_released_not_restorable`, `test_unreachable_not_restorable`, `test_live_with_snapshot_is_restorable`, `test_live_without_snapshot_not_restorable`
- [X] T011 [P] [US3] `tests/unit/test_run_tree.py`: `test_restore_targets_excludes_released` (SC-005), `test_set_head_refuses_released` (folded edge case), `test_set_head_accepts_restorable`

### Implementation for User Story 3

- [X] T012 [US3] In `src/rewind/engine.py` add `Run.is_restorable(step_id) -> bool` = known ∧ `state == "live"` ∧ `snapshot is not None` (per [contracts/run-tree.md](contracts/run-tree.md))
- [X] T013 [US3] Add `Run.restore_targets() -> list[str]` = `[id for id in self.order if self.is_restorable(id)]`
- [X] T014 [US3] Add `Run.set_head(step_id) -> None` — raise `ValueError` (naming the reason: unknown / not live / no snapshot) if not restorable; else `self.head = step_id`

**Checkpoint**: a released or unreachable checkpoint can never be a restore target or head.

---

## Phase 6: User Story 4 — Every branch has a terminal outcome (Priority: P2)

**Goal**: `succeeded` / `failed` / `abandoned` / `None`, read as a property of the branch tip.

### Tests for User Story 4

- [X] T015 [P] [US4] `tests/unit/test_run_tree.py`: `test_branch_outcome_none_while_advancing` (FR-001-09 §4), `test_branch_outcome_succeeded` (via `mark_terminal`), `test_mark_terminal_rejects_bad_value`
- [X] T016 [P] [US4] `tests/unit/test_run_tree.py`: `test_branch_outcome_failed` (Engine.step on a failing step sets tip `terminal="failed"`), `test_branch_outcome_abandoned` (Engine.promote sets losers `terminal="abandoned"`), `test_single_step_run_that_fails` (folded edge case: root + one `terminal="failed"` checkpoint, root intact)

### Implementation for User Story 4

- [X] T017 [US4] In `src/rewind/engine.py` add `Run.mark_terminal(step_id, outcome)` (validate `outcome in {"succeeded","failed","abandoned"}` else `ValueError`; set `checkpoints[step_id].terminal`) and `Run.branch_outcome(step_id) -> str | None` (return `checkpoints[step_id].terminal`)
- [X] T018 [US4] In `src/rewind/engine.py` `Engine.step`: on `not result.ok`, also set `cp.terminal = "failed"` (next to the existing `cp.halt_reason = "step-failed"`)
- [X] T019 [US4] In `src/rewind/engine.py` `Engine.promote`: for each loser, also set `self.run.checkpoints[sid].terminal = "abandoned"` (next to `state = "released"`)

**Checkpoint**: any stopped branch reports exactly one terminal outcome.

---

## Phase 7: User Story 5 — The whole tree renders without extra work (Priority: P3)

**Goal**: `as_tree()` carries every FR-001-07 field; a viewer draws it with no second pass.

### Tests for User Story 5

- [X] T020 [P] [US5] `tests/unit/test_run_tree.py`: `test_as_tree_has_all_fields` (id, index, instruction, parent, children, sandbox, state, snapshot, created_at, exit_code, stdout, outcome, terminal, rationale — SC-007), `test_as_tree_root_only` (single node, empty children, head == root)
- [X] T021 [P] [US5] `tests/unit/test_run_tree.py`: `test_as_tree_nodes_in_order`, `test_as_tree_children_referenced_by_id`

### Implementation for User Story 5

- [X] T022 [US5] In `src/rewind/engine.py` `Run.as_tree`: add `"snapshot": c.snapshot`, `"created_at": c.created_at`, `"outcome": c.outcome`, `"terminal": c.terminal` to each node dict; keep the existing keys and the 400-char `stdout` truncation

**Checkpoint**: one renderable form, all fields, no recomputation.

---

## Phase 8: Cross-cutting — structural integrity (NFR-001-02)

- [X] T023 In `src/rewind/engine.py` implement `Run.check_integrity() -> list[str]` per R4 rules (one root at index 0; one head that exists; parent links resolve; child links resolve and agree both ways; all reachable from root; no cycles)
- [X] T024 [P] `tests/unit/test_run_tree.py`: `test_integrity_of_fresh_run`, `test_integrity_after_failure_abandon_and_shared_parent` (SC-010 — build a run with a failed step, an abandoned branch, and two children of one parent; assert `check_integrity() == []`)
- [X] T025 [P] `tests/unit/test_run_tree.py`: `test_no_runtime_import` (the module under test pulls in no provider/network — assert `test_run_tree` and `engine` import graph excludes `providers`, `daytona`, sockets) covering NFR-001-01 / SC-008

---

## Phase 9: Polish

- [X] T026 [P] Add `docs/run-checkpoint-model.md` linking [contracts/run-tree.md](contracts/run-tree.md) and the FR→test matrix
- [X] T027 Verify the FR/NFR/SC → named-test matrix in [quickstart.md](quickstart.md): every row resolves to a passing test (Article VI gate)
- [X] T028 `FAKE=1 python demo.py` still runs; `fixtures/tree.json` now carries the new keys; restore `fixtures/tree.json` after
- [X] T029 `pytest -q` full offline suite green (000 + 001 + 002); note count in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2, T002–T003)** blocks everything.
- **US1 (P3)**, **US2 (P4)**: after Foundational; both mostly tests over existing behaviour — parallel-safe.
- **US3 (P5)**: after Foundational; adds 3 `Run` methods — independent file region.
- **US4 (P6)**: after Foundational; adds 2 `Run` methods + 2 one-line edits in `Engine.step`/`promote`.
- **US5 (P7)**: after Foundational; one `as_tree` edit — do after US4 so `terminal` exists to emit.
- **Phase 8**: `check_integrity` after US2 (shared-parent) and US4 (abandoned) so the messy-run test can exercise all three conditions.
- **Polish (P9)**: last.

### Parallel opportunities

- Test-writing tasks T004/T005, T007/T008, T010/T011, T015/T016, T020/T021, T024/T025 within their phases
- `Run` method tasks T012–T014 (US3) are independent of T017–T019 (US4) — different methods; only `Engine.step`/`promote` edits (T018/T019) touch shared lines, do them sequentially

---

## Parallel Example: User Story 3

```bash
Task: "T010 test_run_tree.py — restorability predicate cases"
Task: "T011 test_run_tree.py — restore_targets + set_head refusal"
```

---

## Implementation Strategy

### MVP (US1 + US2)

1. Setup + Foundational (T001–T003)
2. US1 (T004–T006) + US2 (T007–T009)
3. **STOP and VALIDATE**: stable ids, ordered steps, a parent with two children, one head.

### Incremental

US1/US2 (tree shape) → US3 (restorability) → US4 (branch outcome) → US5 (render) → integrity check → polish.

---

## Notes

- All `Run` operations stay pure over in-memory state (NFR-001-01). No test in
  this feature imports a provider or touches the network.
- `Checkpoint` field additions go at the **end** of the dataclass so the
  positional `Checkpoint(index=..., step_id=..., ...)` construction in `engine.py`
  is unaffected (all existing construction is keyword-based — verify in T002).
- `Engine.step` / `Engine.promote` get one added line each; their behaviour is
  otherwise untouched (Constitution Article V).
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
