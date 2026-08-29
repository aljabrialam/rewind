---
description: "Task list for Demo Harness implementation"
---

# Tasks: Demo Harness

**Feature**: `007-demo-harness`

**Input**: Design documents from `specs/007-demo-harness/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/harness.md](contracts/harness.md), [checklists/rehearsal.md](checklists/rehearsal.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED. The harness's **logic** (budget / leak / seed / stage-order) is a pure-logic unit layer (NFR-007-04). The live end-to-end run is a `@pytest.mark.live` E2E test + the manual pre-freeze rehearsal. This is the pyramid's top.

**Depends on**: 000–006 — all implemented. Composes `Engine` (`start`/`step`/`fan_out`/`judge_and_promote`/`restore`/`shutdown`/`console_fixture`), `DaytonaProvider`/`FakeProvider`, `ReplayReasoner`/`RecordingReasoner`. Adds **no** sandbox/reasoning/tree behaviour.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US6, on user-story tasks only

## Path Conventions

`src/rewind/harness.py` (new — the harness), `demo.py` (thinned to a front end), `tools/capture_demo_fixtures.py` (new), `tests/unit/test_harness.py` (new), `tests/e2e/test_demo_path.py` (new).

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_harness.py` and `tests/e2e/test_demo_path.py` (docstrings + imports; a `_canned(*payloads)` reasoner helper and a `_seed_steps()` returning the calculator-regression command list)

**Checkpoint**: `pytest -q` still green (193 passed from specs 000–006).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the pure check functions + `DemoResult` + `STAGES`. Blocks Phases 3–7.

- [X] T002 In `src/rewind/harness.py` add `STAGES = ("prepare","seed","observe-failure","rewind","fan-out","verdict","promote","console-fixture","teardown","leak-check")` and the `DemoResult` dataclass per [data-model.md](data-model.md) §2 with `as_dict()`
- [X] T003 In `src/rewind/harness.py` add the pure checks per [contracts/harness.md](contracts/harness.md): `check_budget(path_seconds, budget) -> bool`; `check_no_leak(provider) -> list[str]` (ids from `getattr(provider,"live",None)` else `getattr(provider,"_live",None)`, plus `getattr(provider,"leaks",[])` sandbox_ids); `check_seed_reproduced(checkpoints) -> bool` (last non-root step checkpoint has `evidence.exit_code != 0`); `enough_fixtures(reasoner, need) -> bool` (len of the reasoner's queued responses ≥ `need`, tolerant of a non-ReplayReasoner)

**Checkpoint**: `from rewind.harness import check_budget, check_no_leak, DemoResult, STAGES`.

---

## Phase 3: Foundational check tests (NFR-007-04 / SC-011)

- [X] T004 [P] `tests/unit/test_harness.py`: `test_check_budget` (`<=` passes, over fails), `test_check_seed_reproduced_true` / `test_check_seed_not_reproduced` (last step exit 0 → False)
- [X] T005 [P] `tests/unit/test_harness.py`: `test_check_no_leak_clean` (`FakeProvider` with nothing live → `[]`), `test_check_no_leak_names_live` (a fake with a live id → that id), `test_enough_fixtures` (a stub reasoner with N queued → `>= N` true, `> N` false)

**Checkpoint**: `pytest tests/unit/test_harness.py -q` green; the checks need no runtime.

---

## Phase 4: User Story 1 + 3 + 5 — `run_demo` happy path, prepare, replayed (Priority: P1) 🎯 MVP

**Goal**: one function runs the whole path against the given provider + reasoners; prepare is outside the timer; stages recorded in order; fixture written.

### Tests

- [X] T006 [P] [US1] `tests/unit/test_harness.py`: `test_run_demo_completes_offline` (`run_demo(FakeProvider(), _canned(...strategies...), _canned(verdict), budget=30)` → `res.ok is True`, `res.stages == list(STAGES)`, `res.error is None`, no stdin read), `test_console_fixture_written` (`res.fixture_written` and the file parses with a `head`/`nodes` — SC-010)
- [X] T007 [P] [US5] `tests/unit/test_harness.py`: `test_prepare_runs_before_timer` (`"prepare"` is `stages[0]`; `res.prepare_seconds >= 0`), `test_path_seconds_excludes_prepare` (with a `latency`-bearing fake, `res.path_seconds` < total and does not include the prepare delay — SC-007), `test_warm_false_skips_prepare` (`warm=False` → no `"prepare"` stage)
- [X] T008 [P] [US3] `tests/unit/test_harness.py`: `test_two_runs_identical` (two `run_demo` over the same canned reasoners → equal `stages`, `branch_instructions`, `verdict["chosen"]`/`["reason"]` — SC-002)

### Implementation

- [X] T009 [US1] In `src/rewind/harness.py` add `_prepare_runtime(provider)` — `h = provider.spawn(); provider.run(h, "echo warm"); provider.destroy(h)` — and `run_demo(provider, strategist, critic, *, budget, warm=True, fixture_out="fixtures/tree.json") -> DemoResult` skeleton: if `warm`, run prepare (timed into `prepare_seconds`) before `path_t0`; append stages as entered; `finally` → teardown + leak-check (Phase 6 fills these); return `DemoResult`
- [X] T010 [US1] In `run_demo` execute the scripted path via the engine API: `e = Engine(provider); e.start()`; run `_seed_steps()` via `e.step(...)`, keeping the first ok+snapshot checkpoint as `good`; `fan-out` → `e.fan_out(good, strategist, 3)` (record `branch_instructions`); `verdict`+`promote` → `e.judge_and_promote(fo.children, critic)` (record `verdict`); `rewind` → `e.restore(good, RestoreCheck(...))`; `console-fixture` → write `console_fixture(e)` to `fixture_out`, set `fixture_written`
- [X] T011 [US1] In `run_demo` set `path_seconds = time.time() - path_t0` at the end of `console-fixture`; `over_budget = not check_budget(path_seconds, budget)`

**Checkpoint**: MVP — `run_demo(FakeProvider(), canned, canned, budget=30)` returns `ok=True` with the full stage list.

---

## Phase 5: User Story 3 (cont.) — reasoning fixtures fail-clear (Priority: P1)

### Tests

- [X] T012 [P] [US3] `tests/unit/test_harness.py`: `test_missing_fixture_named_error` (a `ReplayReasoner` over an empty dir + `enough_fixtures` precheck → `run_demo` returns `error` naming the shortfall, no path run), `test_exhausted_fixture_named_error` (a reasoner that raises `LookupError` on the 2nd call → `error = "reasoning fixture exhausted at <stage>"`, `ok False`)

### Implementation

- [X] T013 [US3] In `run_demo` wrap each reasoner-driven stage: a `LookupError` (Spec 002 exhaustion) → `error = f"reasoning fixture exhausted at {stage}"`, abort to `finally`. Add an upfront `enough_fixtures` guard when the reasoner exposes a queue length (`ReplayReasoner`), else proceed
- [X] T014 [US3] In `run_demo` make **no** direct reasoning call — the strategist/critic args are the only source (add an assertion-style comment + a test-visible `run_demo` that never imports `LiveReasoner`)

**Checkpoint**: a fixture problem is a named non-zero `DemoResult`, never a live call.

---

## Phase 6: User Story 4 + 6 — budget + seed + teardown + leak (Priority: P1)

### Tests

- [X] T015 [P] [US4] `tests/unit/test_harness.py`: `test_reports_path_seconds` (`isinstance(res.path_seconds, float)`), `test_over_budget_fails` (`budget=0.0` → `res.over_budget is True`, `res.ok is False`, `res.error`/detail names budget + actual — SC-006), `test_budget_env_override` (a helper reads `REWIND_DEMO_BUDGET`; default ~90)
- [X] T016 [P] [US4] `tests/unit/test_harness.py`: `test_seed_not_reproduced_fails` (a provider/strategy where the "mistake" step still exits 0 → `res.error == "seed did not reproduce the failure"`, path aborted, teardown+leak still ran)
- [X] T017 [P] [US6] `tests/unit/test_harness.py`: `test_leak_check_clean_on_success` (`res.leak == []`), `test_leak_check_runs_on_failure` (force a mid-path error → `"teardown"` and `"leak-check"` still in `res.stages`), `test_leaked_sandbox_named_and_fails` (a provider whose `shutdown`/`destroy` leaves one id live → `res.leak == [that id]`, `res.ok is False` — SC-008), `test_teardown_then_leakcheck_order` (`stages.index("teardown") < stages.index("leak-check")`)
- [X] T018 [P] [SC-009] `tests/unit/test_harness.py`: `test_ok_requires_budget_and_leak` (`ok` is False if `over_budget` even with `leak==[]`, and False if `leak` non-empty even within budget)

### Implementation

- [X] T019 [US4] In `run_demo` after the seed steps: `if not check_seed_reproduced(e.run's step checkpoints): error = "seed did not reproduce the failure"` and abort to `finally`
- [X] T020 [US6] In `run_demo`'s `finally`: append `"teardown"`, `e.shutdown()` + destroy the warm handle if still held (best-effort); append `"leak-check"`, `res.leak = check_no_leak(provider)`
- [X] T021 [US4/US6] In `run_demo` compute `res.ok = (set(path stages) reached) and res.error is None and not res.over_budget and not res.leak` (FR-007-09)

**Checkpoint**: every failure route sets `ok=False` with a named cause; both checks gate exit 0.

---

## Phase 7: `demo.py` front end + capture tool + E2E

- [X] T022 [US1] Rewrite `demo.py` as a thin front end (keep `if __name__ == "__main__": raise SystemExit(main())`): read `DAYTONA_API_KEY` — if absent and not `FAKE`, print `"DAYTONA_API_KEY not set — the demo path runs live"` and `return 1` (SC-012); `budget = float(os.environ.get("REWIND_DEMO_BUDGET", 90))`; `FAKE=1` → `FakeProvider()` + canned reasoners (print "offline dev path — not the demonstration path"); else `DaytonaProvider()` + `ReplayReasoner("fixtures/reasoning")` for both roles, and if `enough_fixtures` fails print `"missing reasoning fixtures: fixtures/reasoning — run tools/capture_demo_fixtures.py"` and `return 1` (SC-005); call `run_demo(...)`; print `res.stages`, `res.path_seconds` vs `budget`, `res.verdict["reason"]`, `res.leak`; `return 0 if res.ok else 1`
- [X] T023 [P] `tools/capture_demo_fixtures.py` — one-time: `RecordingReasoner(LiveReasoner(), "fixtures/reasoning")` wrapped around a `run_demo(DaytonaProvider(), <recording strategist>, <recording critic>, budget=999)`; writes `fixtures/reasoning/*.json` with provenance; prints what it captured. Guards on `LLM_API_KEY` + `DAYTONA_API_KEY`
- [X] T024 [P] `tests/unit/test_harness.py`: `test_demo_py_exit_codes` (subprocess: `FAKE=1 python demo.py` → exit 0; `FAKE=1 REWIND_DEMO_BUDGET=0 python demo.py` → exit 1; `python demo.py` with no `DAYTONA_API_KEY` → exit 1, message on stderr — NFR-007-01 / SC-012)
- [X] T025 `tests/e2e/test_demo_path.py` (`@pytest.mark.live`): `test_path_uses_live_provider` (asserts the harness ran against `DaytonaProvider`, every sandbox op was a live call), `test_live_run_within_budget_no_leak` (`run_demo(DaytonaProvider(), ReplayReasoner(...), ReplayReasoner(...), budget=90)` → `res.ok`, `res.leak == []`, `res.path_seconds < 90`) — skipped without creds + fixtures

---

## Phase 8: Polish

- [X] T026 [P] Add `docs/demo-harness.md` linking [contracts/harness.md](contracts/harness.md) and [checklists/rehearsal.md](checklists/rehearsal.md); one-line "how to rehearse before the freeze"
- [X] T027 Verify the FR/NFR/SC → test map in [quickstart.md](quickstart.md): every row resolves to a unit test, an e2e test, or a named rehearsal item
- [X] T028 `pytest -q` full offline suite green (000–006 + the harness unit layer); `FAKE=1 python demo.py` exits 0 and runs every stage; restore `fixtures/tree.json`; in `docs/gates.md` record spec 007 done and the G3 rehearsal as **pending a live two-run pass**

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T003)** blocks everything.
- **Phase 3 (T004–T005)**: the pure checks — independent, right after Foundational.
- **Phase 4 (T006–T011)**: MVP — `run_demo` happy path + prepare + stages + fixture.
- **Phase 5 (T012–T014)**: fixture fail-clear — extends `run_demo` (sequential on it).
- **Phase 6 (T015–T021)**: budget + seed + teardown + leak — extends `run_demo`/`finally` (sequential on it).
- **Phase 7 (T022–T025)**: `demo.py` after `run_demo` is complete; `tools/` + e2e in parallel.
- **Phase 8**: last.

### Parallel opportunities

- Test-writing tasks within each phase (T004/T005, T006/T007/T008, T015–T018)
- T023 / T026 in their phases
- `src/rewind/harness.py` `run_demo` body — edited by T009, T010, T011, T013, T019, T020, T021 — **sequential**

---

## Implementation Strategy

### MVP (offline `run_demo`)

1. Setup + Foundational (T001–T003) + check tests (T004–T005)
2. Phase 4 (T006–T011) — `run_demo` completes offline with the full stage list
3. **STOP and VALIDATE**: `run_demo(FakeProvider(), canned, canned, budget=30)` → `ok=True`, `stages == STAGES`, fixture written.

### Incremental

pure checks → `run_demo` happy path (prepare, stages, fixture) → fixture fail-clear → budget + seed + teardown + leak (exit-0 gating) → `demo.py` front end + capture tool + live E2E → rehearsal checklist.

---

## Notes

- `run_demo` is pure of the environment (no env reads, no prints, no `sys.exit`);
  `demo.py` owns the env and the exit code (Article VI seam; NFR-007-04).
- The harness **adds no capability** — it only composes 000–006 through the
  engine + provider + reasoner APIs (spec Out of Scope).
- `demo.py` stays runnable today: `FAKE=1` → full offline path, exit 0; the live
  path is exit 1 with a named pointer until `fixtures/reasoning/` is captured
  (correct per SC-005).
- G3 evidence is `python demo.py` clean **twice** live + the failure spot check
  ([rehearsal.md](checklists/rehearsal.md)) — a manual pre-freeze step.
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
