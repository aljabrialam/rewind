---
description: "Task list for Sandbox Capability Contract implementation"
---

# Tasks: Sandbox Capability Contract

**Feature**: `000-sandbox-capability-contract`

**Input**: Design documents from `specs/000-sandbox-capability-contract/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: INCLUDED. Constitution Article VI makes a named test per requirement the sufficiency gate, and the spec carries testable NFRs for the contract suite and fixtures. The FR → named-test matrix in [quickstart.md](quickstart.md) is the source of truth for test names.

**Organization**: Phases 3–7 are one user story each, in priority order. US1 is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different file, no dependency on an incomplete task)
- **[Story]**: US1–US5, on user-story tasks only

## Path Conventions

Single project. Source in `src/rewind/`, tests in `tests/`, live tooling in `tools/`, generated data in `.rewind/` and `fixtures/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: test scaffolding and runner configuration

- [ ] T001 Create test directories `tests/contract/` and `tests/e2e/` with empty `__init__.py`, and `fixtures/daytona/` with a `.gitkeep`
- [ ] T002 In `pyproject.toml` `[tool.pytest.ini_options]`, register the `live` marker and set `addopts = "-m 'not live'"` so the default `pytest` run stays offline
- [ ] T003 [P] Add `tests/conftest.py` with a `pytest_collection_modifyitems` hook that skips `@pytest.mark.live` tests when `DAYTONA_API_KEY` is unset

**Checkpoint**: `pytest -q` runs, collects existing `tests/unit`, skips nothing yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the capability map and the import-time guard. Nothing in Phases 3–7 can run until `import rewind.ports` succeeds against a validated map.

**⚠️ CRITICAL**: no user-story work begins until this phase is complete.

- [ ] T004 Extend `tools/spine_test.py` to emit `.rewind/capability-map.toml` after the live run, following the schema and generation obligations G1–G5 in [contracts/capability-map-schema.md](contracts/capability-map-schema.md) (atomic overwrite; write an operation only after its post-condition asserted; omit `fork`)
- [ ] T005 Create `.rewind/capability-map.toml` with `runtime_version = "v0.207.0"`, `account_cpu_total = 10`, `max_branches = 3`, `classes = ["container", "vm"]`, and `[[operation]]` entries for `spawn`, `run`, `checkpoint`, `branch`, `destroy` (each with `required_class`, `post_condition`, `experimental = false`) taken from `.rewind/daytona-capability-map.md`
- [ ] T006 Create `src/rewind/capabilities.py`: load + parse `.rewind/capability-map.toml` with `tomllib` at module import; expose `VERIFIED_OPS: frozenset[str]`, `CLASS_OF: Mapping[str,str]`, `CEILING: int`, `MAX_BRANCHES: int`, `EXPERIMENTAL: Mapping[str,str]`; define `CapabilityError(ImportError)`; define declared bound constants `READINESS_WAIT=30.0`, `SLOT_WAIT=20.0`, `DESTROY_RETRIES=3`, `DESTROY_RETRY_GAP=2.0`, `AUTO_STOP_MIN`, `AUTO_DELETE_MIN` (env-overridable per [research.md](research.md) R5)
- [ ] T007 In `src/rewind/capabilities.py` implement `assert_declared(ops)` and `assert_class(op, handle)` raising `CapabilityError` naming the offending operation/class (consumer obligations P1–P4 in [contracts/capability-map-schema.md](contracts/capability-map-schema.md))
- [ ] T008 In `src/rewind/ports.py` add `PORT_OPERATIONS = ("spawn","run","checkpoint","branch","destroy")`, add `from . import capabilities` and a module-level `capabilities.assert_declared(PORT_OPERATIONS)` call, and add `sandbox_class: str | None = None` to `Handle`
- [ ] T009 [P] In `src/rewind/ports.py` add type aliases `SandboxClass = Literal["container","vm"]`, `ErrorClass = Literal["retryable","capacity","terminal"]`, and a `CallRecord` dataclass with fields `operation`, `outcome`, `elapsed_seconds`, `error_class`, `waited_seconds`, `retries` per [data-model.md](data-model.md) §5

**Checkpoint**: `python -c "import rewind.ports"` succeeds; corrupting the map fails it with a `CapabilityError` that names the map.

---

## Phase 3: User Story 1 — Invented capability cannot be committed (Priority: P1) 🎯 MVP

**Goal**: any lifecycle operation not in the verified map, or invoked against an unsupported class, stops the process at import time.

**Independent Test**: reference an undeclared operation from feature code, `import rewind.ports` → `CapabilityError` naming it; reference only declared ops → import succeeds; call a `vm`-only op on a `container` handle → refused with class mismatch and no runtime call.

### Tests for User Story 1

- [ ] T010 [P] [US1] Create `tests/unit/test_capabilities.py` with `test_map_loads_and_is_complete`, `test_undeclared_op_raises_on_import` (monkeypatch `PORT_OPERATIONS` / a temp map), `test_experimental_without_marker_rejected`, `test_missing_post_condition_rejected`
- [ ] T011 [P] [US1] Add to `tests/unit/test_capabilities.py`: `test_class_mismatch_raises_without_call` (uses a spy provider asserting no SDK call happened), `test_identifier_is_opaque` (no public function constructs/parses an id)
- [ ] T012 [P] [US1] Add `tests/unit/test_capabilities.py::test_no_sdk_import_outside_providers` — AST-scan every module under `src/rewind/` and assert only `providers.py` imports `daytona`

### Implementation for User Story 1

- [ ] T013 [US1] In `src/rewind/capabilities.py` implement the completeness validation from [contracts/capability-map-schema.md](contracts/capability-map-schema.md): each entry has non-empty `name`, `required_class ∈ classes`, non-empty `post_condition`; `experimental_marker` present iff `experimental` — else `CapabilityError("<name>: incomplete declaration")`
- [ ] T014 [US1] In `src/rewind/providers.py` `DaytonaProvider`, tag each `Handle` with its `sandbox_class` at creation and call `capabilities.assert_class(op, handle)` at the top of `run`, `checkpoint`, `branch`, `destroy` before any SDK call
- [ ] T015 [US1] In `src/rewind/providers.py` `FakeProvider`, mirror `assert_class` and reject any operation not in `capabilities.VERIFIED_OPS` identically to `DaytonaProvider` (spec Edge Cases, FR-000-05)
- [ ] T016 [US1] Audit `src/rewind/ports.py` and `src/rewind/providers.py` for any id string-manipulation; remove it; confirm identifiers flow verbatim from `sb.id` to `Handle.id` to use (FR-000-06)

**Checkpoint**: MVP. Undeclared or misclassed operations cannot reach the runtime; failure is at import, not demo.

---

## Phase 4: User Story 2 — Full system runs offline with no credentials (Priority: P1)

**Goal**: the whole orchestrator and unit suite run with no network and no credentials; the offline port matches recorded live behaviour for every declared operation.

**Independent Test**: unset `DAYTONA_API_KEY`, disable network, run `pytest tests/unit` and `python demo.py` against `FakeProvider` — every declared operation completes and its observable result equals the recorded live result.

### Tests for User Story 2

- [ ] T017 [P] [US2] Create `tests/unit/test_lifecycle.py` with `test_fake_matches_recorded_result` — for each declared op, `FakeProvider` output equals the matching `fixtures/daytona/*.json` result shape
- [ ] T018 [P] [US2] Add `tests/unit/test_lifecycle.py::test_fake_latency_configurable` (observed delay tracks `latency`) and extend `tests/unit/test_ports.py` failure-rate assertion for `NFR-000-04`
- [ ] T019 [P] [US2] Add `tests/unit/test_capabilities.py::test_fixtures_have_provenance` — every file in `fixtures/daytona/` carries `recorded_at` and `runtime_version` (NFR-000-03)

### Implementation for User Story 2

- [ ] T020 [US2] Create `src/rewind/recording.py` with `RecordingProvider(inner)` that delegates every declared op, then writes `fixtures/daytona/<op>-<seq>.json` containing request args, serialized `Handle`/`ExecResult`, `elapsed`, any classified error, `recorded_at`, `runtime_version`
- [ ] T021 [US2] In `src/rewind/recording.py` add `ReplayProvider(fixtures_dir)` implementing the port from recorded files, for unit tests that need live-shaped results without a network
- [ ] T022 [US2] [P] Capture fixtures: run `RecordingProvider(DaytonaProvider())` over `spawn → run → checkpoint → branch(3) → destroy` against the live account and commit the resulting `fixtures/daytona/*.json`
- [ ] T023 [US2] Add a CI job / documented command in [quickstart.md](quickstart.md) §1 proving `pytest tests/unit` passes with `DAYTONA_API_KEY` and network absent (SC-002)

**Checkpoint**: offline unit suite green; fixtures provable from live runs.

---

## Phase 5: User Story 3 — Every sandbox is bounded and always cleaned up (Priority: P2)

**Goal**: every created sandbox has stop + delete intervals and is command-ready before hand-off; it is destroyed on the return and the raise path; the concurrency ceiling is never breached and surplus fan-out requests fail `capacity` after a bounded wait.

**Independent Test**: force the using op to raise → sandbox destroyed; make a sandbox never become ready → creation fails and the half-created sandbox is destroyed; start a fan-out larger than headroom → the fit requests succeed, surplus block then fail `capacity`, live count never exceeds the ceiling; make `destroy` fail → retried, then recorded as a leak that still counts.

### Tests for User Story 3

- [ ] T024 [P] [US3] Add to `tests/unit/test_lifecycle.py`: `test_intervals_attached_on_create`, `test_not_ready_fails_creation_and_destroys`
- [ ] T025 [P] [US3] Add to `tests/unit/test_lifecycle.py`: `test_ceiling_blocks_then_capacity` (surplus request returns `capacity` within `SLOT_WAIT`, siblings stay live), `test_bounds_are_declared_constants` (all waits/retries come from `capabilities` constants and appear in `CallRecord`)
- [ ] T026 [P] [US3] Add to `tests/unit/test_lifecycle.py`: `test_destroy_retry_then_leak` (unconfirmed destroy → `UnconfirmedDestroyLeak` recorded, permit held, terminal error surfaced); confirm existing `tests/unit/test_ports.py::test_cleanup_always_runs` still passes
- [ ] T027 [P] [US3] Add `tests/unit/test_lifecycle.py::test_cleanup_failure_preserves_original_error` (using op raises AND cleanup fails → original error preserved, cleanup failure also surfaced)

### Implementation for User Story 3

- [ ] T028 [US3] In `src/rewind/providers.py` implement the readiness gate in `DaytonaProvider.spawn` and `.branch` (FR-000-08a): block ≤ `READINESS_WAIT` for `echo ok` exit 0; on timeout fail the creation and `destroy` the half-created sandbox; mirror in `FakeProvider`
- [ ] T029 [US3] In `src/rewind/providers.py` make the auto-stop + auto-delete interval attachment on every `spawn`/`branch` a required step (not best-effort `except: pass`); record it on the `CallRecord`; mirror the interval fields in `FakeProvider`
- [ ] T030 [US3] In `src/rewind/providers.py` `DaytonaProvider.__init__` add `threading.BoundedSemaphore(capabilities.CEILING)`; `spawn`/`branch` `acquire(timeout=capabilities.SLOT_WAIT)` before create; on timeout raise a `capacity`-classified error without touching created siblings; track `live_count` (leaks included) and mirror the count in `FakeProvider`
- [ ] T031 [US3] In `src/rewind/providers.py` implement destroy retry (`DESTROY_RETRIES` attempts, `DESTROY_RETRY_GAP` apart); on exhaustion record an `UnconfirmedDestroyLeak` (`sandbox_id`, `first_seen`, `retries_attempted`), keep the semaphore permit held, surface a `terminal`-class error; add the `leaked` state to the `Handle`/lifecycle
- [ ] T032 [US3] In `src/rewind/providers.py` guarantee a `destroy` is attempted for every sandbox that came into existence, including when creation failed mid-way; preserve the original exception when cleanup also raises (FR-000-09); verify `engine.py` `promote`/`shutdown` still satisfy this without modification

**Checkpoint**: ceiling never breached; no sandbox silently assumed gone.

---

## Phase 6: User Story 4 — Every runtime call is observable and its errors are classified (Priority: P2)

**Goal**: every runtime call produces a record with operation, outcome, elapsed, and (on failure) exactly one classification; account-quota and transient-capacity both map to `capacity`; an undecidable capacity-or-terminal failure maps to `capacity`.

**Independent Test**: run a sequence with a success and one induced failure of each class; inspect the records — each has operation/outcome/elapsed; each failure has the expected class; the ambiguous case is `capacity`, never `terminal`.

### Tests for User Story 4

- [ ] T033 [P] [US4] Create `tests/unit/test_error_classification.py` with `test_transient_is_retryable`, `test_quota_is_capacity`, `test_bad_request_is_terminal`, `test_ambiguous_defaults_to_capacity` driven by the decision table in [contracts/error-classification.md](contracts/error-classification.md)
- [ ] T034 [P] [US4] Add `tests/unit/test_error_classification.py::test_classification_on_record` and `tests/unit/test_lifecycle.py::test_call_record_fields` (operation, outcome, elapsed_seconds, waited_seconds, retries all populated) for FR-000-07 / SC-006

### Implementation for User Story 4

- [ ] T035 [US4] In `src/rewind/providers.py` implement `classify(exc) -> ErrorClass` per the 10-row decision table and special cases in [contracts/error-classification.md](contracts/error-classification.md)
- [ ] T036 [US4] In `src/rewind/providers.py` replace `DaytonaProvider.calls: list[tuple[str,float]]` with a `list[CallRecord]`; populate every field in the `_timed` wrapper (including `waited_seconds` from the readiness/ceiling waits and `retries` from the destroy path); retain for the session (FR-000-07)
- [ ] T037 [P] [US4] In `src/rewind/providers.py` attach the `ErrorClass` to every raised runtime error so callers read the classification through the port (FR-000-10)
- [ ] T038 [US4] In `src/rewind/providers.py` `FakeProvider`, emit `CallRecord`s and route the `fail_rate` path through `classify` so offline tests exercise the same classification (NFR-000-04)

**Checkpoint**: every failed call carries exactly one class; ambiguous → `capacity`.

---

## Phase 7: User Story 5 — Contract drift is caught in under thirty seconds (Priority: P3)

**Goal**: a live suite exercises every declared operation, re-asserts each recorded post-condition, pins experimental names, checks the runtime version, and finishes in under thirty seconds, distinguishing credentials / capability / budget failures.

**Independent Test**: `time pytest tests/contract -m live` against the live account — every declared op exercised, per-op pass/fail, wall clock < 30s; rename an op in the map → that op reported failed; unset credentials → reported as a credentials failure, not a capability failure.

### Tests for User Story 5 (the deliverable is the suite)

- [ ] T039 [US5] Create `tests/contract/test_daytona_contract.py` (`@pytest.mark.live`) with `test_each_op_postcondition` — for every `[[operation]]` in the map, run it and assert its recorded `post_condition` holds (FR-000-01a, SC-007)
- [ ] T040 [P] [US5] Add `tests/contract/test_daytona_contract.py::test_experimental_name_pinned` — for each `experimental` entry assert the exact `experimental_marker` name still resolves on the SDK (FR-000-01b)
- [ ] T041 [P] [US5] Add `tests/contract/test_daytona_contract.py::test_runtime_version_matches` (map `runtime_version` vs live) and `test_intervals_live` (a live-created sandbox carries both intervals)
- [ ] T042 [P] [US5] Add `tests/contract/test_daytona_contract.py::test_suite_under_30s` (self-timed session fixture) and `test_failure_kinds_distinguished` — credentials vs capability vs budget-exceeded are separately reported (NFR-000-02, NFR-000-06)
- [ ] T043 [P] [US5] Add `tests/contract/test_daytona_contract.py::test_absent_precondition_resource_is_capability_failure` — a declared op whose required snapshot is missing is reported as a capability failure distinct from a credentials failure (spec US5 §5)

**Checkpoint**: `time pytest tests/contract -m live` < 30s with per-operation verdicts.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T044 [P] Add `docs/capability-contract.md` summarising the enforced contract and linking [contracts/](contracts/), [data-model.md](data-model.md)
- [ ] T045 [P] Update `.env.example` if any new override name was introduced in `capabilities.py` (readiness/slot/destroy bounds)
- [ ] T046 Run every section of [quickstart.md](quickstart.md) (offline suite, import-rejection proof, live regen, < 30s contract check, E2E) and fix any drift
- [ ] T047 Verify the FR/NFR/SC → named-test matrix in [quickstart.md](quickstart.md): every row resolves to a test that exists and passes (Constitution Article VI traceability gate)
- [ ] T048 [P] Commit `.rewind/capability-map.toml` and `fixtures/daytona/*.json`; confirm they are present in the public repo
- [ ] T049 Record gate `g2` in `docs/gates.md` once `pytest tests/unit` (offline) and `pytest tests/contract -m live` (< 30s) are both green; tag `g2`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — **blocks Phases 3–7**. T004→T005→T006→T007→T008; T009 [P] alongside T008
- **US1 (Phase 3)**: depends on Phase 2. MVP
- **US2 (Phase 4)**: depends on Phase 2; T017/T019 assume fixtures from T022; `FakeProvider` parity (T015) lands in US1
- **US3 (Phase 5)**: depends on Phase 2; uses `CallRecord` (T009) and `classify` is nicer-with but US3 can raise plain `capacity` errors and let US4 refine
- **US4 (Phase 6)**: depends on Phase 2; refines the error/record objects US3 introduced. If US3 and US6 run in parallel, coordinate on `providers.py`
- **US5 (Phase 7)**: depends on Phase 2 and a populated `.rewind/capability-map.toml` (T005); independent of US2–US4 code but its assertions cover their behaviour live
- **Polish (Phase 8)**: after all targeted stories

### User Story Dependencies

- US1 — after Foundational. No dependency on other stories
- US2 — after Foundational. Shares `FakeProvider` parity work with US1 (T015); otherwise independent
- US3 — after Foundational. Independent; touches `providers.py` heavily
- US4 — after Foundational. Independent, but co-edits `providers.py` with US3 — sequence US3 → US4 if single-threaded
- US5 — after Foundational + T005. Independent (live suite)

### Within Each User Story

- Tests are written first and expected to fail
- `capabilities.py` validation before provider wiring
- Provider changes before the live contract assertions that check them

### Parallel Opportunities

- T003 with T001/T002
- All of T010–T012 (US1 tests, distinct test files/functions)
- T017–T019 (US2 tests) once fixtures exist
- T024–T027 (US3 tests) together
- T033–T034 (US4 tests) together
- T040–T043 (US5 tests) together
- T044, T045, T048 in Phase 8
- Cross-story: US1, US2, and US5 can proceed in parallel after Phase 2; keep US3 and US4 serialized on `providers.py`

---

## Parallel Example: User Story 1

```bash
# Phase 3 tests — all new, independent functions across one or two files:
Task: "T010 test_capabilities.py: map completeness + undeclared-op import failure"
Task: "T011 test_capabilities.py: class mismatch without call + identifier opacity"
Task: "T012 test_capabilities.py: AST scan — only providers.py imports daytona"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → Phase 2 Foundational (T004–T009)
2. Phase 3 US1 (T010–T016)
3. **STOP and VALIDATE**: undeclared op → `import rewind.ports` fails naming it; declared ops import clean; class mismatch refused with no SDK call
4. This alone satisfies the feature's core promise (Constitution Article IV enforcement) and is demo-worthy

### Incremental Delivery

1. Setup + Foundational → import guard live
2. US1 → invented capability blocked at load → **MVP / possible demo beat**
3. US2 → whole system runs offline → venue-network insurance in place (Seam Rule, by 13:00)
4. US3 → bounded + always-cleaned-up sandboxes → resource hygiene (Article XII)
5. US4 → observable calls + error classes → "is it us or them" answerable
6. US5 → < 30s live drift check → re-run at G3 (15:00 freeze)
7. Polish → traceability matrix verified, gate `g2` tagged

### Parallel Team Strategy

After Phase 2: Dev A on US1, Dev B on US2 + fixtures, Dev C on US5 suite. Fold US3 then US4 back onto whoever owns `providers.py` to avoid merge conflicts in that file.

---

## Notes

- `[P]` = different file, no dependency on an incomplete task
- `src/rewind/engine.py` is intentionally **not** in any task — it already depends only on the port Protocol (Constitution Article V, no refactor after 15:00)
- `src/rewind/providers.py` is the single SDK boundary and is edited by US1, US3, US4 — serialize those edits
- Commit after each task or logical group; tag gates in `docs/gates.md` as they pass (Article XIV)
- Every task traces to an FR/NFR/SC via the matrix in [quickstart.md](quickstart.md); an unmapped task is out of scope
