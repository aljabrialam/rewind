# Implementation Plan: Timeline Console

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/006-timeline-console/`

**Input**: Feature specification from `specs/006-timeline-console/spec.md`

## Summary

Harden the existing `ui/console.html` into the demonstration surface for all of
Rewind. It renders, from one recorded fixture and with no runtime connection: the
run as an ordered checkpoint rail with the head distinguished; fan-out branches as
parallel lanes under their common parent, each showing the runtime's sandbox id,
its running state, and its elapsed time, live-updating on a poll; the captured
evidence (exit + output) for any selected checkpoint or branch, with the agent's
rationale shown separately and labelled as not-evidence; and an always-visible
counter bar (live sandbox count, session elapsed). It lets the operator select a
checkpoint and record a restore request or a fan-out request without the console
touching the runtime. Runtime-issued values render in monospace, console-derived
values in the interface face, and the layout stays legible at a projector zoom.

Technical approach: (1) add a pure `console_fixture(...)` builder in `engine.py`
that emits the Spec 001 `as_tree` form enriched with per-branch progress (Spec
004), the live sandbox count, the session elapsed time, and the verdict; (2) have
`demo.py` write that instead of raw `as_tree()`; (3) rework `ui/console.html` for
the ten FRs — restore/fan-out request controls, branch progress + elapsed,
mono/interface-face discipline, reduced-scale legibility, lanes visibly under
their parent; (4) commit a representative `fixtures/tree.json` and freeze the
finished look as `.rewind/console-mockup.html`. Per Constitution Article VI there
are **no automated UI-rendering tests** — only the fixture *shape* is unit-tested;
the console is proven by a build and the live demo.

## Technical Context

**Language/Version**: Python 3.11+ for the fixture builder; the console is a
single static HTML file (HTML + CSS + vanilla JS, no framework, no build)

**Primary Dependencies**: none new. `engine.py` (Spec 001 `as_tree`, Spec 004
`FanOutResult`), `rank_by_evidence`. `pytest` for the fixture-shape test. A
static file server (`python -m http.server`) to open the console so it can read
the fixture.

**Storage**: `fixtures/tree.json` — the recorded console fixture

**Testing**: `pytest` for `console_fixture()` shape/contents (pure logic, offline).
**No UI-rendering tests** (Article VI). Visual acceptance is a manual checklist +
the live demo.

**Target Platform**: a browser (Chrome/Safari) pointed at a served static file;
projector at ~67–80% zoom, 1280px wide

**Project Type**: single project — internal library + a static UI page

**Performance Goals**: fixture re-read + re-render on a ≤2s interval (NFR-006-02);
render is trivial for the demo-scale tree (tens of nodes)

**Constraints**: no runtime connection from the console (NFR-006-01); single
self-contained page, no build (NFR-006-04); dark theme only; must match the
Design Reference palette/type/layout (NFR-006-03); legible at reduced scale
(FR-006-10)

**Scale/Scope**: one run, ~10–20 checkpoints, ≤3 branches; 10 FRs, 4 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | The deliverable is the two-minute live demo; work must reach the screen | This feature **is** the screen. Everything specs 000–005 built becomes visible here. **Pass** |
| II — Specification First | Tech names only in the plan | Spec 006 names no tech beyond "a browser"; this plan names HTML/CSS/JS and `python -m http.server`. **Pass** |
| VI — Traceability & Pyramid + "what is not tested" | FR → named test; **UI rendering is not tested** | The `console_fixture()` shape gets pure-logic tests; the console's rendering is explicitly out of automated test scope per Article VI, proven by build + demo. FR→check map in [quickstart.md](quickstart.md). **Pass** |
| X — Evidence Over Assertion | Evidence and rationale visually distinct; a verdict shows its evidence | FR-006-06 + FR-006-08 are exactly this — the rationale is a separate, labelled, non-evidence area; the verdict block is marked "judged on execution evidence". **Pass** |
| XI — Proven In The Runtime, Live | The demo runs live on stage; the backup recording is not the plan | The console renders from a fixture so it can be *built* offline, but the demo drives it from a live `demo.py` writing the fixture. NFR-006-01 is rehearsal insurance, not the plan. **Pass** |
| XII — Resource Hygiene | Live sandbox count visible on screen at all times | FR-006-07 makes the live sandbox count a permanent element of the counter bar. **Pass** |
| XIII — Honest Framing | No overclaiming; rationale labelled as rationale | The rationale area literally reads "the agent's account, not evidence"; the fixture-only fallback says it is a sample (SC-009). **Pass** |

**Result**: No violations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-timeline-console/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── console-fixture.md      # the fixture the console reads: fields, provenance, the request-intent shape
├── checklists/
│   ├── requirements.md
│   └── visual-acceptance.md    # the manual FR-by-FR check (Article VI — no automated UI test)
└── tasks.md
```

### Source Code (repository root)

```text
src/rewind/
└── engine.py          # EDIT (additive) — console_fixture(engine, *, verdict=None) -> dict:
                        #   as_tree() enriched with per-branch `progress` (state, elapsed_seconds),
                        #   `live_sandboxes`, `session_elapsed`, `verdict`, `runtime_version`

ui/
└── console.html       # EDIT — the 10 FRs: restore/fan-out request controls (FR-006-03/04);
                        #   branch lane running-state + elapsed from `progress` (FR-006-05);
                        #   live sandbox count + session elapsed from the fixture (FR-006-07);
                        #   mono = runtime-issued, interface face = derived (FR-006-09);
                        #   reduced-scale legibility pass (FR-006-10); lanes captioned by parent id (FR-006-02)

demo.py                # EDIT — write console_fixture(e, verdict=verdict) to fixtures/tree.json
                        #   (replacing the raw as_tree() dump); keep every existing beat

fixtures/
└── tree.json          # COMMIT a representative fixture (a full run: steps, a failure, a fan-out
                        #   with mixed branch states, a verdict) so the console renders standalone

.rewind/
└── console-mockup.html  # NEW — a frozen copy of the finished console, the visual reference

tests/
└── unit/
    └── test_console_fixture.py   # NEW — pure-logic: the fixture has every field the console reads
```

**Structure Decision**: Single-project layout unchanged. The only Python change
is one additive pure function in `engine.py`. The console is one file. No build
tooling is introduced.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 006 has no `[NEEDS CLARIFICATION]`. Phase 0
records: what the existing `ui/console.html` already covers vs the ten FRs; the
enriched fixture field list and where each field comes from; how "record a
request" is realised without a runtime connection; the mono-vs-face rule as a
concrete class discipline; the reduced-scale approach; and why this feature's
only automated test is the fixture shape.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — the Console Fixture shape, the Branch Progress
  entry, the Action Request intent, and the Session Counters, as concrete field
  lists with provenance
- [contracts/console-fixture.md](contracts/console-fixture.md) — every field the
  console reads, its source (Spec 001 / Spec 004 / computed), and the
  restore/fan-out request intent format
- [checklists/visual-acceptance.md](checklists/visual-acceptance.md) — the manual
  FR-by-FR acceptance pass run at build and before the demo (Article VI stand-in
  for automated UI tests)
- [quickstart.md](quickstart.md) — how to build and view the console; the FR →
  (fixture test | visual-acceptance item) map

Post-design Constitution re-check: unchanged — one additive function, one static
file, no new dependency, UI rendering explicitly untested per Article VI.
