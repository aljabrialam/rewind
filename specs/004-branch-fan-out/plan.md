# Implementation Plan: Branch Fan-Out

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/004-branch-fan-out/`

**Input**: Feature specification from `specs/004-branch-fan-out/spec.md`

## Summary

Harden the existing `Engine.branch_from` into a governed fan-out and add a
reasoning-driven entry point `Engine.fan_out`. The fan-out asks the strategist
(reasoning port, Spec 002) for N structured strategies, derives one isolated
sandbox per strategy from the common parent checkpoint via the fastest derivation
the capability map declares (recording which), runs the branches **concurrently**,
records each as a child checkpoint of the parent with its **own** captured
snapshot and independent evidence, reports live per-branch progress (checkpoint
id, runtime sandbox id, running state) as structured data, isolates per-branch
failures, keeps the head at the parent, never breaches the concurrency ceiling,
and destroys every branch sandbox on the success, branch-failure, and
operation-raised paths.

Technical approach: additive to `engine.py`. Rewrite the sequential execution
loop in `branch_from` to a concurrent one with per-branch exception isolation and
a `try/finally` that destroys every created branch sandbox; give each child its
own `provider.checkpoint`; add a `_select_derivation()` helper and record the
choice; add an optional `observer` for the progress report; add `fan_out(...)`
that pulls + validates strategies and returns a `FanOutResult`. `promote` (Spec
005, code present) is updated minimally to re-derive the winner from its own
snapshot, since branch sandboxes are now cleaned up — flagged provisional pending
Spec 005.

## Technical Context

**Language/Version**: Python 3.11+ (venv 3.14)

**Primary Dependencies**: none new — capability port (Spec 000), run tree (Spec
001), reasoning port (Spec 002). `concurrent.futures.ThreadPoolExecutor` (stdlib,
already used in `providers.py`). `pytest`.

**Storage**: none — in-memory run

**Testing**: `pytest`; base layer offline against `FakeProvider` (with `latency`
to prove concurrency) + `ReplayReasoner`; one live contract test
(`@pytest.mark.live`) for ordered-call parity and the wall-clock budget

**Target Platform**: local dev + CI; branches execute on Daytona sandboxes live

**Project Type**: single project — internal library, `src/rewind/engine.py`

**Performance Goals**: total time ≈ slowest branch, ≤ 1.5× one branch for N equal
branches (NFR-004-01 / SC-003); offline fan-out sub-second

**Constraints**: concurrent execution (FR-004-04); ceiling never breached
(FR-004-09); every branch sandbox destroyed on all paths (FR-004-10); head
unchanged (FR-004-05); identifiers verbatim (NFR-004-02); identical ordered port
ops live vs fake, fully offline on the fake (NFR-004-03)

**Scale/Scope**: N ≤ `MAX_BRANCHES` = 3; 10 FRs, 4 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work reaches the screen | The fan-out IS the visual centrepiece — three live sandbox ids + running states on screen. **Pass** |
| II — Specification First | Tech names only in plan | Spec 004 names no tech; this plan names the ports and `ThreadPoolExecutor`. **Pass** |
| IV — Nothing Is Invented | One port per dependency; derivation from the verified map | `_select_derivation` reads `capabilities.VERIFIED_OPS` — it can only pick a derivation the map declares (`branch` today; a faster op only if added). No SDK import. **Pass** |
| V — Vertical Slices / no refactor | Additive | `branch_from`'s loop is reworked in place (concurrency + cleanup + own snapshot); `fan_out` and `_select_derivation` are new; `start`/`step`/`restore`/`shutdown` untouched; `promote` gets one provisional edit. **Pass** |
| VI — Traceability & Pyramid + Seam Rule | FR → named test; fake for the dependency; offline; fixtures from live | `FakeProvider` (with latency) + `ReplayReasoner` cover concurrency, failure isolation, cleanup, ceiling offline; 1 live parity test. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| VIII — Sponsor Integration Is Load-Bearing | The graded integration, used cleverly | Fan-out over isolated sandboxes derived from one checkpoint is the primitive most teams cannot do — `_select_derivation` uses the fastest the platform offers. **Pass** |
| IX — Multi-Agent Feedback Loop | A verdict changes what happens next | The fan-out produces the evidence the Spec 005 critic acts on; the loop closes in 005, this is its exploration leg. **Partial by design.** |
| X — Evidence Over Assertion | Decide on observed results; render evidence | Each branch's evidence is captured independently and returned; the progress report is structured, not narrated. **Pass** |
| XI — Proven In The Runtime, Live | Live sandbox lifecycle on stage | Branches are real concurrent sandboxes; the offline path is rehearsal insurance. **Pass** |
| XII — Resource Hygiene | Every sandbox bounded + destroyed; ceiling respected; count visible | FR-004-10 `try/finally` cleanup on all paths; FR-004-09 defers to Spec 000's ceiling; the progress report shows the live ids. **Pass** |

**Result**: No violations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-branch-fan-out/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fan-out.md          # fan_out/branch_from contract: strategies, derivation, concurrency,
│                           #   progress, failure isolation, ordered calls, cleanup
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/rewind/
├── engine.py          # EDIT (additive + branch_from loop reworked) —
│                      #   FanOutResult / BranchProgress dataclasses;
│                      #   Engine._select_derivation(); Engine.branch_from(...) concurrent
│                      #   + per-branch failure isolation + own snapshots + try/finally cleanup
│                      #   + optional observer; Engine.fan_out(step_id, reasoner, n, ...);
│                      #   Engine.promote re-derives the winner (provisional, → Spec 005)
├── ports.py           # UNCHANGED
├── providers.py       # UNCHANGED
├── capabilities.py    # UNCHANGED (read only, for derivation selection)
└── reasoning.py       # UNCHANGED

tests/
├── unit/
│   └── test_fan_out.py         # NEW — offline: N sandboxes from one parent, concurrency,
│                               #   derivation choice, failure isolation, progress, cleanup, ceiling
└── contract/
    └── test_fan_out_contract.py   # NEW — @pytest.mark.live: ordered-call parity + wall-clock budget

demo.py                # EDIT (additive) — use Engine.fan_out with the fixture strategist and
                       #   print the per-branch progress (id + state); keep the rest of the beat
```

**Structure Decision**: Single-project layout unchanged. Feature code is additive
in `engine.py` plus the in-place concurrency/cleanup rework of `branch_from`'s
loop. One new unit test file, one new live contract test.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 004 has no `[NEEDS CLARIFICATION]`. Phase 0
records: the concurrency mechanism and thread-safety of `run.add`; the derivation
selector and how "fastest available" is expressed against the map; the progress
report shape and how it stays thread-safe; per-branch failure isolation; the
branch-sandbox cleanup contract on all three paths; each branch child getting its
own snapshot and the resulting provisional `promote` change; and the ordered-call
parity observable.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `FanOutRequest`, `Strategy`, `BranchProgress`,
  `FanOutResult`, `Derivation`, and the branch lifecycle states
- [contracts/fan-out.md](contracts/fan-out.md) — `fan_out` / `branch_from`
  inputs, the derivation-selection rule, the concurrency + failure-isolation
  guarantees, the ordered port calls, the progress-report shape, and the cleanup
  obligations on every path
- [quickstart.md](quickstart.md) — run guide + FR/NFR/SC → named-test matrix

Post-design Constitution re-check: unchanged — additive, no new dependency.
