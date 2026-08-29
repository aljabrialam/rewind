---
description: "Task list for Restore to Checkpoint implementation"
---

# Tasks: Restore to Checkpoint

**Feature**: `003-restore-to-checkpoint`

**Input**: Design documents from `specs/003-restore-to-checkpoint/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/restore.md](contracts/restore.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED (Constitution Article VI). Test names are the source of truth in [quickstart.md](quickstart.md).

**Depends on**: Spec 000 (port: `branch`/create-from-snapshot, `run`, `destroy`, `CallRecord`) and Spec 001 (`Run.get`/`is_restorable`/`set_head`/`check_integrity`, `Checkpoint.state`/`snapshot`) — both done. All edits are **additive** to `engine.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US6, on user-story tasks only

## Path Conventions

Single project. All feature code in `src/rewind/engine.py`; tests in `tests/unit/test_restore.py` (new) and `tests/contract/test_restore_contract.py` (new).

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_restore.py` and `tests/contract/test_restore_contract.py` (module docstrings + imports only)

**Checkpoint**: `pytest -q` still green (100 passed from specs 000/001/002).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the result dataclasses + the `restore` skeleton. Blocks Phases 3–8.

- [X] T002 In `src/rewind/engine.py` add three dataclasses per [data-model.md](data-model.md): `RestoreCheck` (frozen: `before: list[tuple[str,str]] = []`, `after: list[tuple[str,str]] = []` via `field(default_factory=list)`), `RestoreVerification` (`status: str`, `before: list[dict]`, `after: list[dict]`), `RestoreResult` (`checkpoint_id`, `sandbox_id`, `elapsed_seconds`, `verification`, `error`, `head_moved`) with an `as_dict()` method
- [X] T003 In `src/rewind/engine.py` add `Engine._verify_restore(handle, check: RestoreCheck | None) -> RestoreVerification` per the verification rule table in [contracts/restore.md](contracts/restore.md): `None`/both-empty → `not-checked`; ≥1 before ∧ ≥1 after ∧ all pass → `verified`; else `not-verified`. Each check dict is `{command, marker, observed, passed}`; `observed` truncated to ~200 chars.
- [X] T004 In `src/rewind/engine.py` add `Engine.restore(checkpoint_id, verify: RestoreCheck | None = None) -> RestoreResult` skeleton: measure `t0`; look up `self.run.get(checkpoint_id)`; return refusal `RestoreResult`s for unknown / `state != "live"` / `snapshot is None` (errors `"unknown"` / `"released"` / `"unreachable"` / `"unreachable"`) with `elapsed_seconds` set and **no port calls**

**Checkpoint**: `from rewind.engine import RestoreCheck, RestoreResult` works; `restore("ghost")` returns `error="unknown"` with an elapsed time.

---

## Phase 3: User Story 1 — Resume from before the mistake (Priority: P1) 🎯 MVP

**Goal**: name a checkpoint → usable sandbox matching it → head now there.

**Independent Test**: build a run, restore an early checkpoint, confirm the produced sandbox reflects that checkpoint's state and the head is that checkpoint.

### Tests for User Story 1

- [X] T005 [P] [US1] `tests/unit/test_restore.py`: `test_restore_produces_matching_sandbox` (write A, checkpoint mid, write B; restore mid; `cat log.txt` in the restored sandbox shows A not B — SC-001), `test_head_moves_to_restored_checkpoint` (SC-002), `test_next_step_after_restore_parents_on_restored_cp`
- [X] T006 [P] [US1] `tests/unit/test_restore.py`: `test_restore_current_head_still_produces_sandbox`, `test_restore_root_when_root_has_snapshot`

### Implementation for User Story 1

- [X] T007 [US1] In `Engine.restore`: on a restorable target, `handles = self.p.branch(cp.snapshot, 1)`; take `new = handles[0]`; wrap in try/except → on raise return `RestoreResult(error=<classify(e) message>, sandbox_id=None, head_moved=False, elapsed_seconds=...)`
- [X] T008 [US1] In `Engine.restore`: after producing the sandbox, `self.run.set_head(checkpoint_id)`; `self.live[checkpoint_id] = new`; set `head_moved` (`True` unless the target was already the head); return `RestoreResult(sandbox_id=new.id, ...)`

**Checkpoint**: MVP — restore re-materialises state and moves the head.

---

## Phase 4: User Story 2 — The restoration is verified, on screen (Priority: P1)

**Goal**: before-present / after-absent checks, structured for rendering, never a false "verified".

### Tests for User Story 2

- [X] T009 [P] [US2] `tests/unit/test_restore.py`: `test_verified_when_before_present_and_after_absent` (status `verified`), `test_not_verified_when_after_still_present`, `test_not_verified_when_before_missing`, `test_not_checked_without_verify` (SC-009)
- [X] T010 [P] [US2] `tests/unit/test_restore.py`: `test_not_verified_when_only_before_supplied`, `test_failing_probe_does_not_abort_restore` (head still moves, status `not-verified`), `test_as_dict_has_renderable_verification` (NFR-003-01 / SC-007 — `as_dict()["verification"]` has `status`, `before`, `after` lists of `{command,marker,observed,passed}`)

### Implementation for User Story 2

- [X] T011 [US2] Wire `Engine._verify_restore(new, verify)` into `restore` between producing the sandbox and moving the head; attach the result to `RestoreResult.verification`; a failing check never raises

**Checkpoint**: US1 + US2 — every restore carries a rendered before/after proof.

---

## Phase 5: User Story 3 — Restoring does not destroy the road not taken (Priority: P2)

**Goal**: every later checkpoint stays in the tree, unchanged; integrity holds.

### Tests for User Story 3

- [X] T012 [P] [US3] `tests/unit/test_restore.py`: `test_tail_checkpoints_preserved` (ids, instructions, `snapshot` of every post-target checkpoint unchanged after restore — SC-003), `test_integrity_after_restore` (`e.run.check_integrity() == []`)
- [X] T013 [P] [US3] `tests/unit/test_restore.py`: `test_later_checkpoint_still_restorable_after_restore` (restore to X, then restore to a checkpoint that was after X — still works from its own snapshot)

### Implementation for User Story 3

- [X] T014 [US3] Confirm `Engine.restore` never removes from / mutates `self.run.order` or `self.run.checkpoints` beyond `head`; add an assertion in the test helper that `order` is identical before/after

**Checkpoint**: the tail survives; restore is not "start over".

---

## Phase 6: User Story 4 — A gone checkpoint cannot be restored, and says why (Priority: P2)

**Goal**: refuse released / unreachable / unknown, name the reason, no sandbox, head unchanged.

### Tests for User Story 4

- [X] T015 [P] [US4] `tests/unit/test_restore.py`: `test_refuse_released_names_reason` (`error == "released"`), `test_refuse_unreachable_names_reason` (`error == "unreachable"` — state set OR snapshot None), `test_refuse_unknown_id` (`error == "unknown"`)
- [X] T016 [P] [US4] `tests/unit/test_restore.py`: `test_refusal_makes_no_port_calls` (`provider.calls` unchanged), `test_refusal_leaves_head_unchanged`, `test_refusal_still_reports_elapsed` (FR-003-06)

### Implementation for User Story 4

- [X] T017 [US4] Verify the refusal branch in `Engine.restore` (from T004) covers all four conditions with the right `error` string and returns before any `self.p.*` call; `verification.status == "not-checked"`

**Checkpoint**: restoring a gone state is impossible and explained.

---

## Phase 7: User Story 5 — Fast enough for the stage, reports its cost (Priority: P3)

### Tests for User Story 5

- [X] T018 [P] [US5] `tests/unit/test_restore.py`: `test_elapsed_reported_on_success`, `test_elapsed_reported_on_refusal` (SC-005), `test_offline_restore_is_fast` (`elapsed_seconds < 0.5` against `FakeProvider` — NFR-003-02, SC-008)

### Implementation for User Story 5

- [X] T019 [US5] In `Engine.restore`: `elapsed_seconds = time.time() - t0` set on **every** return path (refusal, failure, success), measured around produce + verify

**Checkpoint**: every restore reports its cost; offline is instant.

---

## Phase 8: User Story 6 — The old working sandbox is released (Priority: P3)

**Goal**: release the previous head's sandbox once unreferenced; net live count +1 at most; snapshots untouched.

### Tests for User Story 6

- [X] T020 [P] [US6] `tests/unit/test_restore.py`: `test_old_head_sandbox_released` (the old head's handle is `destroy`ed and gone from `e.live`), `test_live_count_grows_by_at_most_one` (SC-006 — `len(fake.live)` after == before + 1)
- [X] T021 [P] [US6] `tests/unit/test_restore.py`: `test_old_head_checkpoint_snapshot_untouched` (old head checkpoint still has its `snapshot` and stays `is_restorable`), `test_ordered_calls_are_fixed` (NFR-003-03 — `["branch","run","run","destroy"]` for one before + one after check)

### Implementation for User Story 6

- [X] T022 [US6] In `Engine.restore` after the head move: `old = self.live.pop(old_head, None)`; if `old` and `old.id not in {h.id for h in self.live.values()}` → `self.p.destroy(old)`. Never touch any checkpoint's `snapshot`. On the failure/refusal path do not release (old head is still the head) — instead rely on the port having destroyed any partial restored sandbox.

**Checkpoint**: no idle sandbox left behind.

---

## Phase 9: Live contract + Polish

- [X] T023 `tests/contract/test_restore_contract.py` (`@pytest.mark.live`): `test_ordered_calls_match_live` (a scripted restore against `DaytonaProvider` yields the same `provider.calls` op sequence as the fake), `test_live_restore_within_budget` (`elapsed_seconds` under a documented few-second budget)
- [X] T024 [P] `demo.py` (additive): after the branch/promote beat, add a `e.restore(<early good checkpoint>, RestoreCheck(before=[("cat log.txt","step1")], after=[("cat log.txt","only-")]))` beat that prints `result.as_dict()`'s verification and elapsed; keep everything else
- [X] T025 [P] Add `docs/restore-to-checkpoint.md` linking [contracts/restore.md](contracts/restore.md) and the FR→test matrix
- [X] T026 Verify the FR/NFR/SC → named-test matrix in [quickstart.md](quickstart.md): every row resolves to a passing (or live-skipped) test (Article VI gate)
- [X] T027 `pytest -q` full offline suite green (000 + 001 + 002 + 003); `FAKE=1 python demo.py` still runs; restore `fixtures/tree.json`; note count in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T004)** blocks everything.
- **US1 (P3, T005–T008)**: MVP. After Foundational.
- **US2 (P4, T009–T011)**: after US1 (needs a produced sandbox to verify).
- **US3 (P5)**, **US4 (P6)**, **US5 (P7)**, **US6 (P8)**: after US1; US4 only needs the refusal branch (T004) so it can start right after Foundational; US6's `destroy` edit is the last write to `restore`.
- **Phase 9**: after all US phases.

### Parallel opportunities

- Test-writing tasks within each phase (T005/T006, T009/T010, T012/T013, T015/T016, T020/T021)
- T024 / T025 in Phase 9
- The single `Engine.restore` body is edited by T004, T007, T008, T011, T019, T022 — **sequential** (same method)

---

## Parallel Example: User Story 4

```bash
Task: "T015 test_restore.py — refuse released/unreachable/unknown with named reason"
Task: "T016 test_restore.py — refusal makes no port calls, head unchanged, elapsed still reported"
```

---

## Implementation Strategy

### MVP (US1)

1. Setup + Foundational (T001–T004)
2. US1 (T005–T008)
3. **STOP and VALIDATE**: restore an early checkpoint, confirm the sandbox matches and the head moved.

### Incremental

US1 (restore + head) → US2 (verified on screen) → US4 (refusals) → US3 (tail preserved) → US5 (elapsed) → US6 (release old sandbox) → live contract + demo beat + polish.

---

## Notes

- `Engine.restore` is one new method; `start`, `step`, `next_step`, `branch_from`,
  `promote`, `shutdown` are untouched (Constitution Article V).
- Restore reuses `provider.branch(snapshot, 1)` — the exact path
  `test_ports.py::test_restore_returns_prior_state` already proves.
- No new external dependency; every unit test runs offline.
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
