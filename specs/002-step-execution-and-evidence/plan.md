# Implementation Plan: Step Execution and Evidence

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/002-step-execution-and-evidence/`

**Input**: Feature specification from `specs/002-step-execution-and-evidence/spec.md`

## Summary

Harden the step loop that already exists in `src/rewind/engine.py` into
**verified execution**: the next instruction comes from a reasoning agent as
schema-checked structured data (reject on non-conformance), it runs inside a
sandbox obtained through the Spec 000 capability port, and the exit status,
standard output, and elapsed time captured from the runtime are the *sole*
evidence attached to that step's checkpoint. A failing step halts the branch
without touching prior checkpoints; a single declared step bound halts it the
same way. The reasoning agent's rationale is stored in a distinct field and never
stands in for evidence. A reasoning port with a fixture-replay implementation
makes a rehearsed run deterministic and offline.

Technical approach: add a small `reasoning` module (the reasoning seam — an
`Instruction` schema + validator, a `ReasoningPort`, a `ReplayReasoner` over
recorded fixtures, and a live implementation that is the only reasoning-vendor
importer). Extend `Engine` additively with a step bound, a branch halt reason,
and a `next_step(reasoner)` entry point that pulls → validates → delegates to the
existing `step()`. `step()` gains the failure-halt guard. No restructure of the
run tree.

## Technical Context

**Language/Version**: Python 3.11+ (repo `requires-python >=3.11`; venv 3.14)

**Primary Dependencies**: the reasoning provider SDK (OpenAI-compatible chat
completions, per `.env.example` `LLM_BASE_URL` / `LLM_MODEL`) — isolated in one
module, mirroring how `daytona` is isolated in `providers.py`; `pytest`;
standard library for schema validation (`dataclasses`, no jsonschema dependency)

**Storage**: Files only — recorded reasoning fixtures under `fixtures/reasoning/`

**Testing**: `pytest`; base layer offline against `FakeProvider` +
`ReplayReasoner`; one live contract test (`@pytest.mark.live`) that the reasoning
schema still holds against the real provider

**Target Platform**: Local dev + CI; steps execute on Daytona sandboxes

**Project Type**: Single project — internal library, consumed by `demo.py`

**Performance Goals**: offline step-loop test sub-second; a scripted demo run
completes in seconds against the fake

**Constraints**: identical execution path live vs fake (NFR-002-01); full loop
runs with no network / no credentials on the fake path (NFR-002-03); reasoning
replayable from fixtures (NFR-002-02); evidence never substituted by rationale
(FR-002-04, Constitution Article X); one declared step bound (FR-002-07)

**Scale/Scope**: one branch advancing forward; step bound in the tens (default
50, per the reference "step 40 of 50"); instruction schema = `{instruction: str
non-empty, rationale: str}`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work reaches the screen | The captured exit codes + output are what the console and the 005 critic consume; the demo's credibility rests on this being real. **Pass** |
| II — Specification First | Tech names only in the plan; sandbox runtime is the one spec-level exception | Spec 002 names no tech; this plan names the reasoning provider and `pytest`. **Pass** |
| IV — Nothing Is Invented | One port per external dependency; no vendor import in feature code | New `reasoning` module is the sole reasoning-vendor boundary, exactly as `providers.py` is for `daytona`. **Pass** |
| VI — Traceability & Pyramid + Seam Rule | FR → named test; fake for every dependency; offline runnable; fixtures from live | `ReplayReasoner` is the reasoning fake; reasoning fixtures captured from a live call, never hand-authored. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| IX — Multi-Agent Feedback Loop | At least one closed loop where a verdict changes what happens next | This feature is the *evidence-producing* leg; the loop closes in Spec 005. The failure-halt (FR-002-06) is a verdict from execution evidence that changes what happens next (branch stops). **Partial by design** — full closure is 005. |
| X — Evidence Over Assertion | Decisions on observed results; evidence and rationale visually distinct | FR-002-04 / FR-002-08 are the whole point. `Checkpoint.evidence` vs `Checkpoint.rationale` are separate fields; outcome is derived from `evidence.exit_code` only. **Pass** |
| XI — Proven In The Runtime, Live | Sandbox lifecycle genuinely live | Steps run live via `DaytonaProvider`; the fake path is rehearsal insurance. **Pass** |
| XII — Resource Hygiene | Every sandbox bounded + destroyed | Inherited from Spec 000 provider; this feature adds no new sandbox creation path beyond `provider.run` on an existing handle. **Pass** |

**Result**: No violations. `engine.py` changes are additive (new params, new
method, one guard clause) — not a restructure. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-step-execution-and-evidence/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── reasoning-port.md        # the reasoning seam: Instruction schema, rejection rules
│   └── step-evidence.md         # what a step captures and attaches; halt semantics
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks output
```

### Source Code (repository root)

```text
src/rewind/
├── reasoning.py       # NEW — Instruction dataclass + validate(); SchemaError;
│                      #   ReasoningPort protocol; ReplayReasoner (fixtures);
│                      #   LiveReasoner (only reasoning-vendor importer)
├── ports.py           # EDIT — replace the LLMClient stub with the ReasoningPort
│                      #   contract; add Checkpoint.halt_reason / branch-halt fields
├── engine.py          # EDIT (additive) — Engine(max_steps=50); step() halts on
│                      #   non-zero exit and on bound; next_step(reasoner) entry point
├── providers.py       # UNCHANGED
└── capabilities.py    # UNCHANGED

tests/
├── unit/
│   ├── test_reasoning.py        # NEW — schema accept/reject, replay determinism, no vendor import
│   ├── test_stepping.py         # NEW — evidence capture + attach, failure halt, step bound,
│   │                            #   evidence-over-rationale, live/fake path parity
│   └── test_ports.py            # UNCHANGED
├── contract/
│   └── test_reasoning_contract.py   # NEW — @pytest.mark.live: real provider still returns schema
└── e2e/ (demo.py covers the scripted path)

fixtures/
└── reasoning/*.json             # NEW — recorded reasoning responses (provenance-stamped)
```

**Structure Decision**: Single-project layout unchanged. One new module
(`reasoning.py`) is the reasoning seam. `engine.py` and `ports.py` get additive
edits only — the run tree, branching, and promotion are untouched.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 002 has no `[NEEDS CLARIFICATION]` (closed as
assumptions). Phase 0 records the technical decisions: reasoning schema shape and
validation approach, the reasoning port + fixture-replay design, how reasoning
fixtures are captured with provenance, the failure-halt / step-bound semantics on
`Engine`, and the live-vs-fake path-parity strategy.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `Instruction`, `Evidence`, `Rationale`,
  `Step`, `BranchHaltReason`, `RecordedReasoning` as concrete shapes with
  validation rules and the branch state machine
- [contracts/reasoning-port.md](contracts/reasoning-port.md) — the reasoning
  interface, the `Instruction` schema, the exact rejection rules, and the
  live/replay parity obligations
- [contracts/step-evidence.md](contracts/step-evidence.md) — what each step
  captures, how it attaches to a checkpoint, failure-halt and step-bound
  behaviour, and the evidence-over-rationale rule
- [quickstart.md](quickstart.md) — run guide + FR/NFR/SC → named-test matrix

Post-design Constitution re-check: unchanged — one new leaf module, additive
engine edits, no new third-party dependency beyond the reasoning provider already
anticipated in `.env.example`.
