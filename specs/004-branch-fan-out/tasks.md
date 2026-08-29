---
description: "Task list for Branch Fan-Out implementation"
---

# Tasks: Branch Fan-Out

**Feature**: `004-branch-fan-out`

**Input**: Design documents from `specs/004-branch-fan-out/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/fan-out.md](contracts/fan-out.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED (Constitution Article VI). Test names are the source of truth in [quickstart.md](quickstart.md).

**Depends on**: Spec 000 (`provider.branch`/`run`/`checkpoint`/`destroy`, `BoundedSemaphore` ceiling, `classify`, `CallRecord`), Spec 001 (`Run.is_restorable`, `Checkpoint.snapshot`/`state`/`terminal`, `check_integrity`), Spec 002 (`ReasoningPort`, `validate`, `SchemaError`, `ExecResult`) — all done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US6, on user-story tasks only

## Path Conventions

Feature code in `src/rewind/engine.py`. Tests in `tests/unit/test_fan_out.py` (new) and `tests/contract/test_fan_out_contract.py` (new).

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_fan_out.py` and `tests/contract/test_fan_out_contract.py` (module docstrings + imports; add a `_canned_strategist(*payloads)` helper returning a `ReasoningPort` that yields those `{instruction, rationale}` dicts)

**Checkpoint**: `pytest -q` still green (128 passed from specs 000–003).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: dataclasses + derivation selector. Blocks Phases 3–8.

- [X] T002 In `src/rewind/engine.py` add `BranchProgress` dataclass (`checkpoint_id`, `sandbox_id`, `state`) and `FanOutResult` dataclass (`children`, `ran`, `requested`, `derivation`, `elapsed_seconds`, `progress: list[dict]`, `error: str | None = None`) with `as_dict()`
- [X] T003 In `src/rewind/engine.py` add `Engine._select_derivation() -> str`: preference `("fork", "branch")`; return the first whose backing op is in `capabilities.VERIFIED_OPS`; store on `self._last_derivation`. (`from . import capabilities` — add the import.)

**Checkpoint**: `from rewind.engine import FanOutResult`; `Engine(FakeProvider())._select_derivation() == "branch"`.

---

## Phase 3: User Story 1 — Three continuations at once from one point (Priority: P1) 🎯 MVP

**Goal**: N structured strategies → N isolated sandboxes from one parent → N child checkpoints; head unchanged.

### Tests for User Story 1

- [X] T004 [P] [US1] `tests/unit/test_fan_out.py`: `test_asks_reasoner_n_times`, `test_rejects_bad_strategy_schema` (`SchemaError`, nothing created), `test_dedupes_and_reports_ran`
- [X] T005 [P] [US1] `tests/unit/test_fan_out.py`: `test_one_sandbox_per_strategy_from_parent` (SC-001 — N children, all `parent_id == parent`), `test_children_are_parent_children`, `test_head_unchanged` (SC-002)

### Implementation for User Story 1

- [X] T006 [US1] In `src/rewind/engine.py` rework `branch_from(step_id, strategies, *, rationales=None, observer=None)`: keep the restorable-parent precondition (raise `ValueError` naming `state`/no-snapshot); cap `strategies` at `self.max_branches`; `self._last_derivation = self._select_derivation()`; `handles = self.p.branch(cp.snapshot, len(strategies))`; build/execute branches (Phase 4 makes this concurrent); `run.add` each child serially in strategy order with `parent_id=step_id`, its `instruction`, `rationale`, `sandbox_id`; **do not move `self.run.head`**; return `list[Checkpoint]`
- [X] T007 [US1] In `src/rewind/engine.py` add `Engine.fan_out(step_id, reasoner, n, context="", observer=None) -> FanOutResult`: refuse (return `FanOutResult(error=...)`) if the parent is not restorable or the strategist raises; else call `reasoner.next_instruction` `n` times, `validate()` each, dedupe by instruction, cap at `min(n, MAX_BRANCHES, distinct)`; delegate to `branch_from`; wrap into `FanOutResult` with `ran`, `requested`, `derivation=self._last_derivation`, `elapsed_seconds`, `progress`

**Checkpoint**: MVP — `fan_out(parent, strategist, 3)` yields 3 child checkpoints of the parent, head still the parent.

---

## Phase 4: User Story 2 — Branches run in parallel (Priority: P1)

**Goal**: overlapping executions; total ≈ slowest branch.

### Tests for User Story 2

- [X] T008 [P] [US2] `tests/unit/test_fan_out.py`: `test_branches_run_concurrently` (`FakeProvider(latency=0.1)`, 3 branches → `res.elapsed_seconds < 0.2` — SC-003), `test_offline_fan_out_is_fast` (`latency=0` → `< 0.5s` — SC-010)

### Implementation for User Story 2

- [X] T009 [US2] In `branch_from`: run the per-branch `provider.run(handle, strategy)` calls in a `ThreadPoolExecutor(max_workers=len(strategies))`; each worker builds its child `Checkpoint` (pure) and updates its progress entry; collect results; `run.add` the children serially afterwards in strategy order (no lock on `Run`)

**Checkpoint**: three 0.1s branches finish in ~0.1s, not 0.3s.

---

## Phase 5: User Story 3 — Fastest derivation available (Priority: P2)

### Tests for User Story 3

- [X] T010 [P] [US3] `tests/unit/test_fan_out.py`: `test_derivation_is_branch_by_default` (current map → `"branch"`), `test_prefers_faster_derivation_when_declared` (monkeypatch `capabilities.VERIFIED_OPS` to include `"fork"` → `"fork"`), `test_derivation_recorded` (`res.derivation` and `e._last_derivation` set — SC-009)

### Implementation for User Story 3

- [X] T011 [US3] Confirm `_select_derivation` (T003) is called once per `branch_from` and its result flows to `FanOutResult.derivation`; a preferred-but-absent op falls through to the next (`fork` absent → `branch`)

**Checkpoint**: the fan-out uses and records the fastest declared derivation.

---

## Phase 6: User Story 4 — A failing branch does not sink the others (Priority: P2)

### Tests for User Story 4

- [X] T012 [P] [US4] `tests/unit/test_fan_out.py`: `test_failing_branch_isolated` (one strategy contains `"BOOM"` → its child `evidence.exit_code != 0`, others carry their own good evidence, all returned — SC-005), `test_failed_branch_terminal_is_failed` (`child.terminal == "failed"`)
- [X] T013 [P] [US4] `tests/unit/test_fan_out.py`: `test_branch_creation_failure_reported` (a provider whose Nth `branch` handle is unusable → that branch `failed` with a reason, others fine)

### Implementation for User Story 4

- [X] T014 [US4] In the `branch_from` worker: wrap `provider.run` in try/except; on exception → `evidence = ExecResult(1, str(getattr(e,'error_class',None) or e))`, `child.terminal = "failed"`, progress `state = "failed"`; a non-zero exit likewise sets `child.terminal = "failed"`; never re-raise a branch failure out of the fan-out

**Checkpoint**: one bad strategy, two good results still returned.

---

## Phase 7: User Story 5 — Each branch's live machine is visible (Priority: P2)

### Tests for User Story 5

- [X] T015 [P] [US5] `tests/unit/test_fan_out.py`: `test_progress_reports_id_and_state` (each `progress` entry has `checkpoint_id`, `sandbox_id`, `state` — SC-008), `test_progress_advances_creating_running_done` (observer sees the transitions), `test_progress_sandbox_ids_are_verbatim` (`sandbox_id` == the handle's `id`, unmodified — SC-007 / NFR-004-02)
- [X] T016 [P] [US5] `tests/unit/test_fan_out.py`: `test_as_dict_progress_is_structured` (`FanOutResult.as_dict()["progress"]` is a list of plain dicts — NFR-004-04)

### Implementation for User Story 5

- [X] T017 [US5] In `branch_from`: hold `self._fan_progress: list[BranchProgress]` guarded by a `threading.Lock`; each branch starts `creating`, → `running` when its worker starts, → `done`/`failed` at the end; call `observer([bp.__dict__ for bp in progress])` after each transition; return the final list on `FanOutResult.progress`

**Checkpoint**: three live sandbox ids + advancing states, structured.

---

## Phase 8: User Story 6 — No branch sandbox left running (Priority: P1)

**Goal**: every branch sandbox destroyed on all three paths; ceiling never breached; count returns to baseline.

### Tests for User Story 6

- [X] T018 [P] [US6] `tests/unit/test_fan_out.py`: `test_all_branch_sandboxes_destroyed_on_success` (`len(fake.live)` back to pre-fan-out value — SC-006), `test_all_destroyed_when_a_branch_fails`, `test_all_destroyed_when_operation_raises` (inject a provider that raises mid-fan-out → `finally` still destroys the created ones)
- [X] T019 [P] [US6] `tests/unit/test_fan_out.py`: `test_ceiling_not_exceeded_during_fan_out` (`FakeProvider(ceiling=2)` + a sampler → live count never > 2), `test_op_counts_are_fixed` (`branch×1, run×N, checkpoint×N, destroy×N` — NFR-004-03)

### Implementation for User Story 6

- [X] T020 [US6] In `branch_from`: collect every created handle; in a `finally`, `provider.destroy` each — runs on success, per-branch-failure, and operation-raised paths. Each child's own `snapshot` is taken (via `provider.checkpoint`, for branches that exited 0) **before** its handle is destroyed. `self.run.head` unchanged; child checkpoints stay in the tree.
- [X] T021 [US6] In `src/rewind/engine.py` update `Engine.promote(winner, losers)` (provisional, → spec 005): since branch handles are gone, re-derive the winner — `self.live[winner] = self.p.branch(self.run.checkpoints[winner].snapshot, 1)[0]`; `self.run.head = winner`; losers → `state="released"`, `terminal="abandoned"`, no handle to destroy

**Checkpoint**: live count returns to baseline; ceiling held; `demo.py` still promotes and continues.

---

## Phase 9: Live contract + Polish

- [X] T022 `tests/contract/test_fan_out_contract.py` (`@pytest.mark.live`): `test_op_counts_match_live` (a 3-branch `fan_out` against `DaytonaProvider` → same per-op counts as the fake), `test_wall_clock_within_budget` (`res.elapsed_seconds` under a documented budget and materially less than 3× a single branch)
- [X] T023 [P] `demo.py` (additive): replace the hand-rolled `branch_from(STRATEGIES)` beat with `e.fan_out(good_step, <fixture strategist>, 3, observer=...)`; print each branch's `sandbox_id` + final `state` + the derivation used; keep `rank_by_evidence` + `promote`
- [X] T024 [P] Add `docs/branch-fan-out.md` linking [contracts/fan-out.md](contracts/fan-out.md) and the FR→test matrix
- [X] T025 Verify the FR/NFR/SC → named-test matrix in [quickstart.md](quickstart.md): every row resolves to a passing (or live-skipped) test (Article VI gate)
- [X] T026 `pytest -q` full offline suite green (000–004); `FAKE=1 python demo.py` still runs the branch + promote + restore beats; restore `fixtures/tree.json`; note count in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T003)** blocks everything.
- **US1 (T004–T007)**: MVP. `branch_from` rework starts here (T006), `fan_out` (T007).
- **US2 (T008–T009)**: makes T006's loop concurrent — sequential on `branch_from` after US1.
- **US3 (T010–T011)**: independent (derivation selector) — can land right after Foundational.
- **US4 (T012–T014)**, **US5 (T015–T017)**, **US6 (T018–T021)**: all edit the `branch_from` body → **sequential** among themselves; order US4 → US5 → US6.
- **Phase 9**: after all US phases. T021 (`promote`) must land before T023/T026 so `demo.py` works.

### Parallel opportunities

- Test-writing tasks within each phase (T004/T005, T012/T013, T015/T016, T018/T019)
- T023 / T024 in Phase 9
- The `branch_from` / `fan_out` body is edited by T006, T007, T009, T014, T017, T020 — **sequential**

---

## Parallel Example: User Story 4

```bash
Task: "T012 test_fan_out.py — failing branch isolated, others returned"
Task: "T013 test_fan_out.py — branch creation failure reported per-branch"
```

---

## Implementation Strategy

### MVP (US1)

1. Setup + Foundational (T001–T003)
2. US1 (T004–T007) — `branch_from` rework (still sequential exec) + `fan_out`
3. **STOP and VALIDATE**: `fan_out(parent, strategist, 3)` → 3 child checkpoints of the parent, head unchanged.

### Incremental

US1 (fan-out shape) → US2 (concurrent) → US3 (derivation) → US4 (failure isolation) → US5 (progress) → US6 (cleanup + ceiling + provisional promote) → live contract + demo + polish.

---

## Notes

- `branch_from`'s loop is reworked in place (concurrency, own snapshots, cleanup,
  progress); `start`/`step`/`next_step`/`restore`/`shutdown` are untouched
  (Constitution Article V). `promote` gets one provisional edit (→ spec 005).
- `_select_derivation` reads only `capabilities.VERIFIED_OPS` — it can never pick
  a derivation the map does not declare (Article IV).
- `Run.add` stays single-threaded — children are added serially after the parallel
  section (no lock on the Spec 001 pure model).
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
