---
description: "Task list for Step Execution and Evidence implementation"
---

# Tasks: Step Execution and Evidence

**Feature**: `002-step-execution-and-evidence`

**Input**: Design documents from `specs/002-step-execution-and-evidence/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: INCLUDED (Constitution Article VI). Test names are the source of truth in [quickstart.md](quickstart.md).

**Depends on**: Spec 000 (capability port + `FakeProvider` + `capabilities.py`) — done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US6, on user-story tasks only

## Path Conventions

Single project. Source in `src/rewind/`, tests in `tests/`, fixtures in `fixtures/`.

---

## Phase 1: Setup

- [X] T001 Create `fixtures/reasoning/` with a `.gitkeep`
- [X] T002 [P] Create empty test files `tests/unit/test_reasoning.py`, `tests/unit/test_stepping.py`, `tests/contract/test_reasoning_contract.py` (module docstring + imports only)

**Checkpoint**: `pytest -q` still green (35 passed from Spec 000, new files collect nothing yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the reasoning seam and the additive engine hooks. Blocks Phases 3–8.

- [X] T003 Create `src/rewind/reasoning.py`: `Instruction` frozen dataclass `{instruction, rationale}`; `SchemaError(ValueError)`; `validate(payload: Mapping) -> Instruction` per the rule table in [contracts/reasoning-port.md](contracts/reasoning-port.md) (non-empty instruction str, non-empty rationale str, unknown keys ignored)
- [X] T004 In `src/rewind/reasoning.py` add `ReasoningPort` `Protocol` (`next_instruction(context: str) -> Mapping`) and `ReplayReasoner(fixtures_dir=FIXTURES/'reasoning')` serving `*.json` in ascending `seq`, raising `LookupError` on exhaustion
- [X] T005 In `src/rewind/reasoning.py` add `RecordingReasoner(inner)` (writes `fixtures/reasoning/<seq>.json` with `context`, `response`, `recorded_at`, `model`, `seq`) and `LiveReasoner` (the only reasoning-vendor importer; OpenAI-compatible chat completion from `LLM_BASE_URL`/`LLM_MODEL`; returns the raw parsed object)
- [X] T006 In `src/rewind/ports.py` replace the `LLMClient` stub with a re-export of `ReasoningPort` (or a thin alias) and add `Checkpoint.halt_reason: str | None = None`; add a derived `Checkpoint.outcome` property = `"ok"` iff `evidence and evidence.ok` else `"failed"` (computed from `evidence` only)
- [X] T007 In `src/rewind/engine.py` (additive): `Engine.__init__(..., max_steps: int = int(os.environ.get("MAX_STEPS", 50)))`; add `self.halted = False` and `self.halt_reason: str | None = None`; add `BranchHalted(RuntimeError)`
- [X] T008 In `src/rewind/engine.py` add `Engine.next_step(reasoner, context: str = "") -> Checkpoint`: raise `BranchHalted` if halted/at bound; `raw = reasoner.next_instruction(context)`; `instr = validate(raw)`; return `self.step(instr.instruction, instr.rationale)` — `SchemaError` propagates, nothing executes

**Checkpoint**: `import rewind.reasoning, rewind.engine` clean; `validate({'instruction':'x','rationale':'y'})` returns an `Instruction`.

---

## Phase 3: User Story 1 — A step executes and its evidence is captured (Priority: P1) 🎯 MVP

**Goal**: one instruction runs through the capability port; exit status, stdout, elapsed time are captured and attached to the step's checkpoint.

**Independent Test**: run one well-formed instruction; the checkpoint carries exit status, output, `elapsed > 0`, all sourced from the runtime.

### Tests for User Story 1

- [X] T009 [P] [US1] `tests/unit/test_stepping.py`: `test_step_runs_through_the_port` (a `run` appears in `provider.calls`), `test_evidence_fields_captured` (exit_code, stdout, `elapsed > 0`), `test_empty_output_is_not_missing_evidence` (exit 0 + `stdout == ""` still recorded)
- [X] T010 [P] [US1] `tests/unit/test_stepping.py`: `test_evidence_attached_to_checkpoint` (`cp.evidence is result`), `test_call_sequence_is_fixed` (good step → `["run","checkpoint"]`)

### Implementation for User Story 1

- [X] T011 [US1] In `src/rewind/engine.py` `step()`: measure wall-clock around `provider.run`, guarantee `evidence.elapsed > 0` even when the provider reports 0 (floor to a tiny epsilon); confirm `FakeProvider` path produces the same shape
- [X] T012 [US1] Verify `step()` attaches `evidence` before `run.add` and only calls `provider.checkpoint` when `evidence.ok` (already true — add the assertions/tests, adjust if drift)

**Checkpoint**: MVP — a real step's result is on its checkpoint.

---

## Phase 4: User Story 2 — A malformed reasoning response is rejected before execution (Priority: P1)

**Goal**: non-conforming reasoning output is rejected; nothing runs, no checkpoint is created.

**Independent Test**: return a response missing a field / wrong shape → `SchemaError`, zero `provider.run` calls, no new checkpoint.

### Tests for User Story 2

- [X] T013 [P] [US2] `tests/unit/test_reasoning.py`: `test_valid_payload_accepted`, `test_missing_instruction_rejected`, `test_empty_instruction_rejected`, `test_missing_rationale_rejected`, `test_wrong_types_rejected`, `test_unknown_keys_ignored`
- [X] T014 [P] [US2] `tests/unit/test_stepping.py`: `test_reject_creates_no_checkpoint` (`next_step` with a bad `ReplayReasoner` payload → `SchemaError`, `len(engine.run.order)` unchanged, `provider.calls` unchanged)

### Implementation for User Story 2

- [X] T015 [US2] Confirm `Engine.next_step` calls `validate()` before any `provider` call and does not catch `SchemaError` (per [contracts/reasoning-port.md](contracts/reasoning-port.md) C1–C2); add a guard test-double reasoner that asserts `next_instruction` is not called again after a rejection

**Checkpoint**: US1 + US2 — verified execution only happens on a conforming instruction.

---

## Phase 5: User Story 3 — A failing step halts the branch without losing history (Priority: P2)

**Goal**: non-zero exit halts the branch; the failing step's checkpoint keeps its evidence; prior checkpoints are untouched.

**Independent Test**: a step exits non-zero → branch stops, failure recorded on that checkpoint, earlier checkpoints present with original evidence.

### Tests for User Story 3

- [X] T016 [P] [US3] `tests/unit/test_stepping.py`: `test_failure_halts_branch` (`engine.halted` true, `halt_reason == "step-failed"`), `test_failing_checkpoint_keeps_evidence` (`cp.evidence.exit_code != 0`, `cp.halt_reason == "step-failed"`)
- [X] T017 [P] [US3] `tests/unit/test_stepping.py`: `test_prior_checkpoints_survive_failure` (snapshot the pre-failure `as_tree()` nodes, run the failing step, assert those nodes are byte-identical), `test_step_on_halted_branch_raises` (`BranchHalted`, no `provider.run`)

### Implementation for User Story 3

- [X] T018 [US3] In `src/rewind/engine.py` `step()`: after `run.add`, if `not evidence.ok` → set `cp.halt_reason = "step-failed"`, `self.halted = True`, `self.halt_reason = "step-failed"`; never mutate any node other than the one just added
- [X] T019 [US3] In `src/rewind/engine.py` `step()` and `next_step()`: first line guard — `if self.halted: raise BranchHalted(self.halt_reason)`

**Checkpoint**: a dead branch stays dead; steps 1..n-1 are intact.

---

## Phase 6: User Story 4 — Evidence is the sole basis; rationale kept distinct (Priority: P2)

**Goal**: outcome derives from exit status only; rationale is stored in its own field and never substituted.

**Independent Test**: rationale claims success, command exits non-zero → recorded outcome is `failed`; rationale still stored, marked as rationale.

### Tests for User Story 4

- [X] T020 [P] [US4] `tests/unit/test_stepping.py`: `test_outcome_follows_exit_status_not_rationale` (rationale `"all good"`, exit 1 → `cp.outcome == "failed"` and branch halted), `test_rationale_and_evidence_are_separate_fields` (`cp.rationale` is the instruction's rationale; `cp.evidence` is the `ExecResult`; changing one does not touch the other)
- [X] T021 [P] [US4] `tests/unit/test_stepping.py`: `test_as_tree_separates_evidence_and_rationale` (`as_tree()` node has distinct `rationale` and `exit_code`/`stdout` keys)

### Implementation for User Story 4

- [X] T022 [US4] Confirm `Checkpoint.outcome` reads only `evidence`; add a grep/AST test `test_no_rationale_in_decisions` asserting `engine.py` never references `.rationale` inside `step`, the halt logic, or `outcome`
- [X] T023 [US4] Carry the validated `rationale` verbatim from `next_step` into `step(..., rationale=instr.rationale)` and onto `cp.rationale`

**Checkpoint**: Article X holds — no self-report stands in for a result.

---

## Phase 7: User Story 5 — Branch step count is bounded (Priority: P3)

**Goal**: one declared bound; reaching it stops the branch like a failure does.

**Independent Test**: drive a branch to `max_steps - 1`, then one more → stops at the bound, records `"step-bound"`, no further execution.

### Tests for User Story 5

- [X] T024 [P] [US5] `tests/unit/test_stepping.py`: `test_step_bound_stops_branch` (`Engine(p, max_steps=3)`; 3 steps ok; 4th → no `provider.run`, `engine.halted`, `halt_reason == "step-bound"`, `BranchHalted` raised), `test_bound_is_single_value` (the number is read from `engine.max_steps` only — one attribute)
- [X] T025 [P] [US5] `tests/unit/test_stepping.py`: `test_failure_reason_wins_over_bound` (a branch that both hits the bound and whose last step failed records `"step-failed"`)

### Implementation for User Story 5

- [X] T026 [US5] In `src/rewind/engine.py`: helper `_steps_in_branch()` (count of non-root checkpoints on the current lineage via `run.path_to(head)`); in `step()`/`next_step()` guard — if `_steps_in_branch() >= self.max_steps` → set `self.halted`, `self.halt_reason = "step-bound"` (unless already `"step-failed"`), raise `BranchHalted`

**Checkpoint**: no branch runs past the bound.

---

## Phase 8: User Story 6 — Live/fake path parity; reasoning replayable (Priority: P3)

**Goal**: the ordered actions of a step are identical for both providers; reasoning replays deterministically offline.

**Independent Test**: run the same scripted task against fake+replay and (live) against real; the ordered `provider.calls` operations and the ordered instructions match.

### Tests for User Story 6

- [X] T027 [P] [US6] `tests/unit/test_reasoning.py`: `test_replay_is_deterministic` (same fixtures dir → same ordered instructions twice), `test_replay_exhaustion_raises` (`LookupError` past the last fixture), `test_no_reasoning_sdk_outside_reasoning_module` (AST scan of `src/rewind/`)
- [X] T028 [P] [US6] `tests/unit/test_reasoning.py`: `test_every_reasoning_fixture_has_provenance` (`recorded_at` + `model` on every `fixtures/reasoning/*.json`; skips if none committed yet)
- [X] T029 [P] [US6] `tests/unit/test_stepping.py`: `test_full_loop_offline` (`FakeProvider` + `ReplayReasoner`, network off, no creds, a multi-step run completes) and `test_call_sequence_is_fixed` reused as the fake side of parity
- [X] T030 [US6] `tests/contract/test_reasoning_contract.py` (`@pytest.mark.live`): `test_live_response_passes_validate` (real provider → `validate()` succeeds), `test_call_sequence_matches_live` (a scripted 2-step run against `DaytonaProvider` yields the same ordered `provider.calls` ops as the fake)

### Implementation for User Story 6

- [ ] T031 [US6] Capture starter reasoning fixtures: run `RecordingReasoner(LiveReasoner())` over the `demo.py` step contexts; commit `fixtures/reasoning/*.json` (needs `LLM_*` creds — human step if unavailable)
- [X] T032 [US6] Wire `demo.py` to optionally use `ReplayReasoner` when `FAKE=1` and fixtures exist (additive; keep the hard-coded `STEPS` fallback)

**Checkpoint**: whole loop runs offline and deterministically.

---

## Phase 9: Polish & Cross-Cutting

- [X] T033 [P] Add `docs/step-execution.md` linking the contracts and the FR→test matrix
- [X] T034 [P] Update `.env.example` — confirm `MAX_STEPS` present; note `LLM_*` power the live reasoning path
- [X] T035 Verify the FR/NFR/SC → named-test matrix in [quickstart.md](quickstart.md): every row resolves to a passing (or live-skipped) test (Article VI gate)
- [X] T036 Run [quickstart.md](quickstart.md) §1–§3 and §6 end to end; fix drift
- [X] T037 `pytest -q` full offline suite green (Spec 000 + Spec 002); note count in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2)** blocks everything.
  T003→T004→T005 (reasoning.py); T006 (ports.py) after T003–T004; T007→T008 (engine.py) after T006.
- **US1 (P3)**: after Foundational. MVP.
- **US2 (P4)**: after Foundational. Independent of US1 (schema layer).
- **US3 (P5)**, **US4 (P6)**: after Foundational; both edit `engine.py` `step()` — sequence US3 → US4 if single-threaded.
- **US5 (P7)**: after Foundational; also edits `engine.py` guards — sequence after US3.
- **US6 (P8)**: after Foundational; mostly tests + fixtures; T031 needs live `LLM_*`.
- **Polish (P9)**: last.

### Parallel opportunities

- T002 alone in Setup
- T009+T010 (US1 tests); T013+T014 (US2 tests); T016+T017 (US3); T020+T021 (US4); T024+T025 (US5); T027+T028+T029 (US6)
- Cross-story: US1, US2, US6-tests can proceed in parallel after Foundational; serialize US3→US4→US5 on `engine.py`

---

## Parallel Example: User Story 2

```bash
Task: "T013 test_reasoning.py — schema accept/reject cases"
Task: "T014 test_stepping.py::test_reject_creates_no_checkpoint"
```

---

## Implementation Strategy

### MVP (US1 only)

1. Phase 1 Setup → Phase 2 Foundational (T003–T008)
2. Phase 3 US1 (T009–T012)
3. **STOP and VALIDATE**: a real step's exit code + output + elapsed are on its checkpoint, sourced from the runtime.

### Incremental

US1 (verified step) → US2 (reject junk) → US3 (halt keeps history) → US4 (evidence over assertion) → US5 (bound) → US6 (offline determinism) → Polish.

---

## Notes

- `engine.py` edits are additive: new `__init__` params, `next_step`, two guard
  clauses, one post-`add` halt block. The run tree, `path_to`, `as_tree`,
  `branch_from`, `promote` are untouched (Constitution Article V).
- `reasoning.py` is the sole reasoning-vendor boundary (Article IV), enforced by
  an AST test mirroring Spec 000's `test_no_sdk_import_outside_providers`.
- Reasoning fixtures come from live runs only (Article VI); provenance test
  enforces it.
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
