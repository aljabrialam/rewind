---
description: "Task list for Timeline Console implementation"
---

# Tasks: Timeline Console

**Feature**: `006-timeline-console`

**Input**: Design documents from `specs/006-timeline-console/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/console-fixture.md](contracts/console-fixture.md), [checklists/visual-acceptance.md](checklists/visual-acceptance.md), [quickstart.md](quickstart.md)

**Tests**: The **only** automated test is the Console Fixture *shape* (pure logic). Constitution Article VI — "UI rendering … is not tested" — so the ten FRs are otherwise verified by [checklists/visual-acceptance.md](checklists/visual-acceptance.md), run at build and before the demo.

**Depends on**: Spec 001 (`Run.as_tree`), Spec 004 (`FanOutResult` / `BranchProgress`, `engine._fan_progress`), `rank_by_evidence` — all done. Governs the existing `ui/console.html`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US6, on user-story tasks only

## Path Conventions

`src/rewind/engine.py` (one pure function), `ui/console.html` (the page), `demo.py` (fixture writer), `fixtures/tree.json` (committed fixture), `tests/unit/test_console_fixture.py` (new), `.rewind/console-mockup.html` (frozen reference).

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_console_fixture.py` (docstring + imports: `from rewind.engine import Engine, console_fixture` — or `Engine.console_fixture`; `from rewind.providers import FakeProvider`)

**Checkpoint**: `pytest -q` still green (153 passed from specs 000–004).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the enriched fixture builder. Blocks the console rework and `demo.py`.

- [X] T002 In `src/rewind/engine.py` `Engine.__init__` record `self._t0 = time.time()` (session start, for `session_elapsed`)
- [X] T003 In `src/rewind/engine.py` add `console_fixture(engine, *, verdict: dict | None = None) -> dict` (module-level pure function): start from `engine.run.as_tree()`; add `live_sandboxes = len(getattr(engine.p, "live", None) or engine.live)`, `session_elapsed = round(time.time() - engine._t0, 2)`, `runtime_version = capabilities.RUNTIME_VERSION`, `verdict` (verbatim or `None`); for every **branch node** (a node whose `parent` has >1 child) merge `progress = {"state": <from engine._fan_progress by checkpoint_id, fallback node terminal/state>, "elapsed_seconds": round(<branch evidence.elapsed or 0>, 3)}`; leave non-branch nodes without a `progress` key. Per [contracts/console-fixture.md](contracts/console-fixture.md). Make no network / provider call.

**Checkpoint**: `console_fixture(Engine(FakeProvider()))` returns a dict with `head`, `nodes`, `live_sandboxes`, `session_elapsed`, `runtime_version`, `verdict`.

---

## Phase 3: Fixture-shape tests (the only automated tests)

- [X] T004 [P] `tests/unit/test_console_fixture.py`: `test_has_head_and_ordered_nodes` (SC-001), `test_nodes_carry_exit_and_stdout` (every node has `exit_code`/`stdout` keys — FR-006-06), `test_rationale_field_passthrough` (a step with a rationale keeps it; one without has `""`/falsy — FR-006-08 / SC-003)
- [X] T005 [P] `tests/unit/test_console_fixture.py`: `test_live_sandboxes_is_provider_count` (`== len(engine.p.live)`, not node count — FR-006-07 / C2), `test_session_elapsed_present` (float ≥ 0 — FR-006-07 / C3), `test_fixture_is_json_serialisable` (`json.dumps` round-trips — C9)
- [X] T006 [P] `tests/unit/test_console_fixture.py`: `test_branch_nodes_have_progress` (after a `fan_out`, each branch node has `progress.state in {creating,running,done,failed}` and `progress.elapsed_seconds >= 0`; non-branch nodes have no `progress` — FR-006-05 / C6-C7), `test_branch_nodes_identifiable_by_parent` (branch nodes share a `parent` with >1 child — FR-006-02), `test_recompute_reflects_advance` (call `console_fixture` before and after another `step` → `nodes` grows, `session_elapsed` non-decreasing — NFR-006-02 / C10)

**Checkpoint**: `pytest tests/unit/test_console_fixture.py -q` green.

---

## Phase 4: Wire the fixture into the demo

- [X] T007 In `demo.py` replace `json.dump(e.run.as_tree(), f, indent=2)` with `json.dump(console_fixture(e, verdict=verdict), f, indent=2)`; keep every existing beat (steps, fan-out, promote, restore) and keep writing to `fixtures/tree.json`
- [X] T008 Run `FAKE=1 python demo.py`; commit the resulting `fixtures/tree.json` as the representative console fixture (a full run: steps, a failing step, a fan-out with mixed branch states, a verdict, a live count)

**Checkpoint**: `fixtures/tree.json` carries `live_sandboxes`, `session_elapsed`, `verdict`, and branch `progress`.

---

## Phase 5: User Story 1 — See the whole run at a glance (Priority: P1) 🎯 MVP

**Goal**: ordered rail with head marked; branches as lanes under their parent.

### Implementation

- [X] T009 [US1] In `ui/console.html` keep the rail (FR-006-01 already met); add a caption above the lanes — `Branches from <parent-id>` with `<parent-id>` in `.mono` — derived from the common `parent` of the branch nodes (FR-006-02)
- [X] T010 [US1] In `ui/console.html` `isBranch` / lane rendering: confirm branch nodes never also render on the rail; give each lane the parent-relative label `Branch i`

**Manual check**: [visual-acceptance.md](checklists/visual-acceptance.md) FR-006-01, FR-006-02.

---

## Phase 6: User Story 2 — Read the evidence behind any point (Priority: P1)

**Goal**: exit + output for any selected checkpoint/branch; rationale separate & labelled; absent rationale not rendered.

### Implementation

- [X] T011 [US2] In `ui/console.html` confirm the evidence panel (`#exit`, `#stdout`, `#rationale`) renders for a selected rail node **and** a selected lane; the `<pre>` stays `overflow:auto` with a bounded `max-height` (FR-006-06)
- [X] T012 [US2] In `ui/console.html` confirm `#rationale` is shown only when `n.rationale` is truthy, keeps the `"agent rationale — not evidence:"` label, and is styled distinct from the output (FR-006-08 — already largely present; verify + tidy the label)

**Manual check**: FR-006-06, FR-006-08.

---

## Phase 7: User Story 3 — Act on the run from the console (Priority: P2)

**Goal**: restore / fan-out request controls on a selection; recorded, no runtime call.

### Implementation

- [X] T013 [US3] In `ui/console.html` add two buttons near the evidence panel — **Restore to this checkpoint**, **Fan out from this checkpoint** — disabled when `sel` is null, enabled when a checkpoint is selected (FR-006-03/04, SC-004)
- [X] T014 [US3] In `ui/console.html` add a `recordRequest(kind)` that builds `{kind, checkpoint_id: sel, requested_at: new Date().toISOString()}`, appends a row to a visible **Requests** list, and `console.log`s it as JSON; it performs **no** `fetch`/XHR (per [contracts/console-fixture.md](contracts/console-fixture.md) A1–A4)

**Manual check**: FR-006-03, FR-006-04 (Network tab shows no runtime call).

---

## Phase 8: User Story 4 — Watch three machines work at once (Priority: P1)

**Goal**: per-branch sandbox id + running-state word + elapsed, live-updating on the poll.

### Implementation

- [X] T015 [US4] In `ui/console.html` lane rendering: read `n.progress.state` for the running-state word (creating/running/done/failed) with a fallback to `n.terminal`/`n.state`; keep the inset colour mapping (running → `branch`, promoted/head → `won`, released → `killed`)
- [X] T016 [US4] In `ui/console.html` lane rendering: show `n.progress.elapsed_seconds` as `Ns` (number in the interface face, `s` in the interface face); sandbox id stays `.mono`
- [X] T017 [US4] In `ui/console.html` confirm `setInterval(load, 2000)` re-reads `fixtures/tree.json` and re-renders; a failed/partial fetch keeps the last good `T` (never half-and-half — Edge Cases)

**Manual check**: FR-006-05 (re-run `demo.py` with the page open; lanes advance within ~2s).

---

## Phase 9: User Story 5 — Keep the session counters in view (Priority: P2)

**Goal**: live sandbox count + session elapsed always visible, from the fixture.

### Implementation

- [X] T018 [US5] In `ui/console.html` footer: bind the live-sandbox counter to `T.live_sandboxes` (not `T.nodes.filter(state==='live')`); bind the elapsed counter to `T.session_elapsed` (formatted `N.Ns`); keep `checkpoints`/`branches` counts
- [X] T019 [US5] In `ui/console.html` confirm the footer is `position:fixed` and visible with a selection open and the page scrolled; add `flex-wrap:wrap` so it never clips (FR-006-07 / SC-006)

**Manual check**: FR-006-07.

---

## Phase 10: User Story 6 — Legible from the back of the room (Priority: P2)

**Goal**: mono vs interface-face discipline; readable at projector zoom.

### Implementation

- [X] T020 [US6] In `ui/console.html` remove `.mono` from the derived footer counters (`fLive`, `fNodes`, `fBranch`, `fTime`) and from any other console-computed value (state words, verdict prose); keep `.mono` on sandbox ids, checkpoint ids, exit codes, `stdout`, executed instructions, `daytona <version>` (FR-006-09 / SC-008)
- [X] T021 [US6] In `ui/console.html` reduced-scale pass on the demo fixture at ~70% zoom / 1280px: add `text-overflow:ellipsis` to the lane command row; ensure no fixed width overflows 1280px; ensure `<pre>` and lanes scroll within themselves; verify the < 900px single-column collapse still reads (FR-006-10 / SC-007)

**Manual check**: FR-006-09, FR-006-10 (the two zoom/face items in visual-acceptance).

---

## Phase 11: Polish

- [X] T022 In `ui/console.html` confirm the built-in `SAMPLE` still renders on `file://` and add a small "sample data — serve with a static file server for live" note when the fetch fails (NFR-006-01 / SC-009)
- [X] T023 [P] Copy the finished `ui/console.html` to `.rewind/console-mockup.html` (the frozen visual reference the spec's Design Reference points at) — R7
- [X] T024 [P] Add `docs/timeline-console.md` linking the Design Reference, [contracts/console-fixture.md](contracts/console-fixture.md), and [checklists/visual-acceptance.md](checklists/visual-acceptance.md)
- [X] T025 Run the full [checklists/visual-acceptance.md](checklists/visual-acceptance.md) pass; record the result and any deferred item in `docs/gates.md`
- [X] T026 `pytest -q` full offline suite green (000–004 + the fixture-shape test); `FAKE=1 python demo.py` still runs every beat; note count in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T003)** blocks everything.
- **Phase 3 (T004–T006)**: after Foundational — the only automated tests.
- **Phase 4 (T007–T008)**: after Foundational — the console needs the enriched fixture.
- **Phases 5–10**: all edit `ui/console.html` → **sequential**; order US1 → US2 → US3 → US4 → US5 → US6 (US1/US2 are largely verification of what exists; US3/US4/US5/US6 add the new behaviour).
- **Phase 11**: last. T023 (freeze the mockup) only after Phase 10.

### Parallel opportunities

- Fixture-shape test tasks T004/T005/T006 (same file, distinct functions — can be written together)
- T023 / T024 in Phase 11
- `ui/console.html` is edited by T009–T022 — **sequential**

---

## Implementation Strategy

### MVP (US1 + fixture)

1. Setup + Foundational (T001–T003) + fixture-shape tests (T004–T006)
2. Wire the fixture (T007–T008) + US1 (T009–T010)
3. **STOP and VALIDATE**: serve the console, run `demo.py`, see the ordered rail with the head marked and branches as lanes captioned by their parent.

### Incremental

US1 (see the run) → US2 (evidence + rationale) → US3 (request restore/fan-out) → US4 (live branch state + elapsed) → US5 (session counters from the fixture) → US6 (face discipline + reduced scale) → freeze the mockup + visual-acceptance pass.

---

## Notes

- The console stays **one static file**, dark theme, no build (NFR-006-04). Every
  edit is CSS/JS inside `ui/console.html`.
- The **only** automated test is `console_fixture()`'s shape — Constitution
  Article VI keeps UI rendering out of automated testing; the ten FRs are signed
  off in [checklists/visual-acceptance.md](checklists/visual-acceptance.md).
- `Engine.console_fixture` is a pure read — no runtime call (NFR-006-01).
- `demo.py` keeps every beat; only its final `json.dump` target changes.
