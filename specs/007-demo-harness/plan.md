# Implementation Plan: Demo Harness

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/007-demo-harness/`

**Input**: Feature specification from `specs/007-demo-harness/`

## Summary

Harden the existing `demo.py` into an unattended, budgeted, leak-checked harness
for the scripted end-to-end demonstration path. Extract the path into a pure-ish
`run_demo(...)` seam so the harness's own logic — seed-failure check, path timer,
budget check, leak check, stage ordering — is testable offline (NFR-007-04),
while the demonstration path itself runs live-sandbox + fixture-replay reasoning
(FR-007-02/03). Add a preparation stage that warms a sandbox before the timer
starts (FR-007-06); assert the seeded failure actually reproduced (FR-007-04);
after teardown, verify the harness's provider holds zero live sandboxes and name
any that remain (FR-007-07/08); require the path, the budget check, and the leak
check to all pass for a zero exit (FR-007-09); keep writing `fixtures/tree.json`
(FR-007-10). `demo.py` stays the single no-argument command.

Technical approach: new `src/rewind/harness.py` with `run_demo(provider,
strategist, critic, *, budget, warm=True, fixture_out=…) -> DemoResult` and pure
check functions (`check_budget`, `check_no_leak`, `check_seed_reproduced`,
`STAGES`). `demo.py` becomes a thin front end: build the live `DaytonaProvider` +
`ReplayReasoner` for both reasoning roles (or the canned/offline path under
`FAKE=1`), call `run_demo`, print, `SystemExit(0 if result.ok else 1)`. A missing
or exhausted reasoning fixture fails clear and non-zero. A one-time
`tools/capture_demo_fixtures.py` records the reasoning fixtures from a live run.

## Technical Context

**Language/Version**: Python 3.11+ (venv 3.14)

**Primary Dependencies**: none new — composes `engine.py` (000–005),
`providers.py` (000), `reasoning.py` (`ReplayReasoner`, `RecordingReasoner`),
`console_fixture` (006). `pytest`.

**Storage**: `fixtures/tree.json` (console fixture, overwritten per run);
`fixtures/reasoning/` (recorded strategist + critic responses, one-time capture)

**Testing**: `pytest`. **Offline pure-logic layer** — the check functions + a
full `run_demo` against `FakeProvider` + canned reasoners (NFR-007-04 / SC-011).
**Live E2E** — `@pytest.mark.live` `run_demo` against `DaytonaProvider` +
`ReplayReasoner`, within budget, no leak.

**Target Platform**: local dev + CI; the demonstration path runs on Daytona
sandboxes live

**Performance Goals**: the demonstration path completes within the budget
(default ~90s live; sub-second offline); preparation is outside the timed path

**Constraints**: no interactive input (NFR-007-02); non-zero exit on any failure
(NFR-007-01); live sandbox + replayed reasoning on the demo path — no simulation,
no live reasoning call (FR-007-02/03); budget is one declared, overridable value
(NFR-007-03); both budget and leak checks must pass for exit 0 (FR-007-09)

**Scale/Scope**: one scripted path; 10 FRs, 4 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | The deliverable is the two-minute live demo; the demo script is written before the code | The harness runs exactly the scripted path (seed → steps → fail → rewind → fan-out → verdict → promote → fixture → teardown). **Pass** |
| II — Specification First | Tech names only in the plan | Spec 007 names no tech beyond "a command"; this plan names `python`, `pytest`. **Pass** |
| III — Spine Rule temperament | The ugliest thing that works | `run_demo` is one function with a provider/reasoner seam; the checks are four small pure functions. No framework. **Pass** |
| V — Vertical Slices / no refactor | Additive; `demo.py` stays the entry point | The path logic moves into `harness.py`; `demo.py` becomes a thin caller. `engine.py` and every other spec's code are untouched. **Pass** |
| VI — Traceability & Pyramid | This is the pyramid's **top** — the scripted E2E, one test, run twice before 15:45 | Offline pure-logic layer for the checks (NFR-007-04); one live E2E test; FR→test map in [quickstart.md](quickstart.md). **Pass** |
| X — Evidence Over Assertion | Decide on observed results | The budget check is on measured wall-clock; the leak check is on the provider's own live count; the seed check is on the failing step's captured exit code. **Pass** |
| XI — Proven In The Runtime, Live | The demonstration runs live on stage; the backup recording is not the plan; pre-warm, seeded workspace, replayed reasoning | FR-007-02 (live sandbox), FR-007-03 (replayed reasoning), FR-007-04 (seeded workspace), FR-007-06 (pre-warm) are this article, made executable. **Pass** |
| XII — Resource Hygiene | Every sandbox destroyed on success and failure; live count visible | FR-007-07/08 — teardown then a leak check on both routes; a non-zero live count fails the run. **Pass** |
| XIV — Living Evidence | Gates recorded | The harness running clean twice is the G3 evidence; recorded in `docs/gates.md`. **Pass** |

**Result**: No violations. Complexity Tracking empty. This feature makes the
constitution's demo-assurance articles (I, XI, XII) executable.

## Project Structure

### Documentation (this feature)

```text
specs/007-demo-harness/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── harness.md          # run_demo seam, the check functions, exit-code rules, stage order
├── checklists/
│   ├── requirements.md
│   └── rehearsal.md         # the pre-freeze two-run manual checklist (Article XI / G3)
└── tasks.md
```

### Source Code (repository root)

```text
src/rewind/
└── harness.py         # NEW — run_demo(provider, strategist, critic, *, budget, warm, fixture_out)
                        #   -> DemoResult; STAGES; check_budget / check_no_leak /
                        #   check_seed_reproduced (pure); _prepare_runtime (pre-warm)

demo.py                # EDIT — thin front end: pick provider (live default / FAKE fake) and
                        #   reasoners (ReplayReasoner default / canned under FAKE or an explicit
                        #   opt-in), call run_demo, print stages, SystemExit(0 if ok else 1);
                        #   fail-clear + non-zero if reasoning fixtures are missing/exhausted

tools/
└── capture_demo_fixtures.py   # NEW — one-time: RecordingReasoner over a live run writes
                                #   fixtures/reasoning/{strategist,critic}-*.json

tests/
├── unit/
│   └── test_harness.py        # NEW — pure-logic: the check functions; a full run_demo against
│                              #   FakeProvider + canned reasoners (stages, budget pass, no leak,
│                              #   seed failed, fixture written) — SC-011
└── e2e/
    └── test_demo_path.py      # NEW — @pytest.mark.live: run_demo(DaytonaProvider, ReplayReasoner)
                                #   within budget, zero leak, exit-0 conditions

fixtures/
├── tree.json                  # console fixture — overwritten per run (FR-007-10)
└── reasoning/                 # recorded strategist + critic responses (one-time capture)
```

**Structure Decision**: Single-project layout unchanged. One new module
(`harness.py`), one new tool, two new test files. `demo.py` stays the command;
`engine.py` and the other specs' code are not touched.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 007 has no `[NEEDS CLARIFICATION]`. Phase 0
records: the `run_demo` seam and why the pure checks are separable; the pre-warm
stage and how the path timer excludes it; how a missing/exhausted reasoning
fixture is detected and named; the leak check against the provider's live
accounting for both `FakeProvider` and `DaytonaProvider`; the seed-reproduced
check; the exit-code contract; and how `demo.py` keeps running today (offline)
while the live path awaits captured fixtures.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `DemoResult`, `Stage`, the check-function
  signatures, and the harness state machine
- [contracts/harness.md](contracts/harness.md) — `run_demo` inputs/outputs, the
  ordered stages, each check's pass/fail rule, the exit-code table, and the
  fixture-missing behaviour
- [checklists/rehearsal.md](checklists/rehearsal.md) — the pre-freeze two-run
  manual pass (Article XI / G3)
- [quickstart.md](quickstart.md) — run guide + FR/NFR/SC → (unit | e2e |
  rehearsal) map

Post-design Constitution re-check: unchanged — one additive module, `demo.py`
thinned, no new dependency; the top of the pyramid is now a real harness.
