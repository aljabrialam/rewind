# Phase 0 Research: Timeline Console

Spec 006 carries no `[NEEDS CLARIFICATION]`. Decisions for design. Evidence:
`ui/console.html` (168 lines, single file — the current console), `demo.py`
(`json.dump(e.run.as_tree(), f)`), `src/rewind/engine.py`
(`Run.as_tree`, `FanOutResult`, `rank_by_evidence`), Constitution Articles I, VI
("UI rendering … is not tested"), X, XI, XII.

---

## R1. What the existing `ui/console.html` already does

| FR | State today |
|---|---|
| FR-006-01 rail, head marked | **done** — `.rail`, `.node.head` glow ring, run order |
| FR-006-02 branches as lanes | **partial** — lanes render, but as a flat list; not captioned by the common parent |
| FR-006-03 select + request restore | **missing** — selection works; no restore control/intent |
| FR-006-04 request fan-out | **missing** |
| FR-006-05 branch id + state + elapsed, live | **partial** — shows sandbox id + exit; no running-state word, no elapsed; poll exists (`setInterval(load, 2000)`) |
| FR-006-06 evidence for selection | **done** — exit + `<pre>` output panel, works for a checkpoint or a lane |
| FR-006-07 live count + session elapsed, always | **partial** — footer is persistent, but `fLive` counts nodes with `state==="live"` (not sandboxes) and `fTime` is page-open time (not session time) |
| FR-006-08 rationale ≠ evidence | **done** — `.rationale` area, italic, muted, `"agent rationale — not evidence:"`, hidden when absent |
| FR-006-09 mono vs interface face | **partial** — runtime values are mono; but the derived footer counters are also `.mono` |
| FR-006-10 legible at reduced scale | **partial** — has `@media(max-width:900px)`; no explicit projector-zoom pass |

**Decision**: keep the file, its palette, and its structure; close the partials
and the two missing controls. No rewrite.

---

## R2. The enriched Console Fixture (NFR-006-01, FR-006-05/07)

**Decision**: add `Engine.console_fixture(engine, *, verdict=None) -> dict` (a
pure function over engine state — no runtime call). It returns `run.as_tree()`
plus:

| Added field | Source | Feeds |
|---|---|---|
| `live_sandboxes` | `len(engine.p.live)` (the provider's live-sandbox set) — falls back to `len(engine.live)` | FR-006-07 counter |
| `session_elapsed` | seconds since `engine`-creation (a `t0` recorded in `Engine.__init__`) | FR-006-07 counter |
| `runtime_version` | `capabilities.RUNTIME_VERSION` | footer chip |
| `verdict` | the `rank_by_evidence(...)` dict passed in by the caller (or `None`) | Verdict Block |
| `nodes[i].progress` | for branch nodes only — `{state, elapsed_seconds}` merged from `engine._fan_progress` / the last `FanOutResult.progress` by `checkpoint_id` | FR-006-05 lane |

`demo.py` writes `console_fixture(e, verdict=verdict)` instead of `e.run.as_tree()`.

**Rationale**: `as_tree()` (Spec 001) is deliberately the run *structure*; the
console also needs live operational numbers and Spec 004 branch progress. Keeping
that composition in one pure builder makes it the single thing a unit test checks
(the only automated test this feature has).

**Alternatives considered**:
- Put `live_sandboxes` / `session_elapsed` on `as_tree()` — rejected: Spec 001
  said `as_tree` is the pure structural form; operational counters are a console
  concern.
- A separate second fixture file — rejected: the console reads one file
  (NFR-006-01); one enriched file is simpler.

---

## R3. "Record a request" without a runtime connection (FR-006-03/04)

**Decision**: with a checkpoint selected, the console shows two buttons —
**Restore to this checkpoint** and **Fan out from this checkpoint**. Triggering
one appends an `ActionRequest` — `{kind: "restore" | "fan_out", checkpoint_id,
requested_at}` — to an on-screen "Requests" list and `console.log`s it as JSON.
The console makes no `fetch` to any runtime. When nothing is selected the buttons
are disabled.

**Rationale**: NFR-006-01 forbids a runtime connection; the spec's out-of-scope
says the orchestrator consuming the request is separate. A visible, logged,
inspectable intent is the demonstrable minimum and keeps the console a static
page (NFR-006-04). `localStorage` is avoided (Out of Scope: no persistence across
reload).

---

## R4. Mono vs interface face as a class discipline (FR-006-09, SC-008)

**Decision**: one rule — `.mono` on, and only on, values that came from the
sandbox runtime or the reasoning agent: sandbox ids, checkpoint ids, exit codes,
captured `stdout`, executed instructions, `runtime_version`. Everything the
console computed or labelled — section titles, the footer's numeric counters
(`live sandboxes`, `checkpoints`, `branches`, `elapsed`), state words
("running", "promoted"), verdict prose — uses the interface face (no `.mono`).
The footer counters lose their current `.mono` class. A checkpoint id inside a
heading keeps `.mono` (runtime-issued wins).

**Rationale**: FR-006-09 is a trust signal at a glance; a single origin-based rule
is auditable in the visual-acceptance check.

---

## R5. Reduced-scale legibility (FR-006-10, SC-007)

**Decision**: verify and adjust for ~67–80% browser zoom at 1280px on the demo
fixture. Concrete guards: the grid already collapses < 900px; ensure the `<pre>`
output stays `overflow:auto` with a bounded `max-height` (it does); ensure lane
and rail text use `text-overflow: ellipsis` on the one-line command rows (rail
does; add to lanes); ensure the footer wraps rather than clipping (`flex-wrap`);
no fixed pixel widths that overflow 1280px. No new breakpoint framework — a
handful of CSS additions.

---

## R6. Why the only automated test is the fixture shape (Article VI)

**Decision**: Constitution Article VI, "What is not tested": *UI rendering … is
not tested.* So there are **no** headless-browser or DOM tests. The one automated
test is `test_console_fixture.py` — a pure-logic check that
`console_fixture(...)` returns every field the console reads (`head`, `nodes[]`
with the FR-006-01/06/08 fields, branch nodes with `progress.state` +
`progress.elapsed_seconds`, `live_sandboxes`, `session_elapsed`, `verdict`). The
ten FRs are otherwise verified by `checklists/visual-acceptance.md`, run at build
time and again before the demo (mirrors the Article VI contract-test cadence).

---

## R7. The frozen mockup (`.rewind/console-mockup.html`)

**Decision**: after the console is finished, copy it to
`.rewind/console-mockup.html` as the frozen visual reference the spec's Design
Reference section points at. It is documentation, not a second live page.

---

## Open items carried to Phase 1

- Exact fixture field list + provenance → [data-model.md](data-model.md)
- Fixture contract + ActionRequest shape → [contracts/console-fixture.md](contracts/console-fixture.md)
- The FR-by-FR manual pass → [checklists/visual-acceptance.md](checklists/visual-acceptance.md)
