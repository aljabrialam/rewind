# Feature Specification: Timeline Console

**Feature ID**: `006-timeline-console`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Operational Visibility

**Business Actors**: Developer; Judge or observer

**Input**: User description: "Make the run's tree, its live branches, and the evidence behind every decision visible and operable on one screen."

## Business Context

### Business Goal

Make the run's tree, its live branches, and the evidence behind every decision
visible and operable on one screen.

### Business Value

Nothing before this specification can be demonstrated. Completeness is assessed on
what is proven live, and this is the surface on which it is proven.

### Dependencies

- **Specification 001 — Run and Checkpoint Model**: the console renders the run
  tree in its renderable form (the `as_tree` shape) — every node with its
  identifier, index, instruction, parent, children, state, sandbox identifier,
  creation time, outcome, and rationale.
- **Specification 004 — Branch Fan-Out**: the console renders the per-branch
  progress — for each branch, its checkpoint identifier, its runtime sandbox
  identifier, and its running state.
- **Data source**: `demo.py` writes the combined renderable form and progress to
  `fixtures/tree.json`. The console reads that file; it holds no other connection
  to the runtime (NFR-006-01).

## Design Reference *(mandatory for this feature)*

The visual target is `.rewind/console-mockup.html`, embodied by the working
console at `ui/console.html`. This section governs palette, type, and layout;
implementation must not drift from it.

### Palette

| Token | Value | Use |
|---|---|---|
| ground | `#0D1117` | page background |
| rail | `#1F2937` | rails, borders, inactive dots |
| ink | `#E6EDF3` | primary text |
| muted | `#8B949E` | secondary text, metadata, labels |
| live | `#00D492` | the head, a live/successful checkpoint, selection accent (the sponsor green) |
| branch | `#D29922` | a branch that is still running / pending |
| won | `#388BFD` | a promoted branch |
| killed | `#8B3A34` | a failed checkpoint, a released branch |

Dark theme only. No light mode.

### Type

- **Interface face**: system sans (`-apple-system, "Segoe UI", …`), 15px base,
  1.5 line height. Used for everything the console *derived* itself — headings,
  labels, counts, verdict prose, section titles.
- **Monospace face**: `ui-monospace, SFMono-Regular, Menlo, …`. Used for every
  value the *runtime issued* — sandbox identifiers, checkpoint identifiers, exit
  codes, captured output, instructions as executed.
- Section titles: 11px, uppercase, `0.12em` tracking, muted, weight 600.

### Layout

- Two columns on a wide screen: a left **rail** (`min-width 300px`) of ordered
  checkpoints, a right column (`min-width 340px`) holding **branch lanes**, the
  **verdict**, and the **evidence** panel.
- Collapses to a single column below 900px.
- A fixed **footer bar** shows the session counters (live sandbox count, session
  elapsed, node count, branch count) at all times.
- Checkpoints are a vertical rail with a connecting line and a status dot per
  node; the head node carries a glow ring.
- Branches are bordered lanes stacked under a heading, each with a coloured
  inset edge by state (running / promoted / released).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the whole run at a glance (Priority: P1)

A developer, or a judge watching the demonstration, opens one screen and sees the
run as an ordered rail of checkpoints with the current head clearly marked, and
any branches as parallel lanes hanging off their common parent. No scrolling
between tools, no separate log window.

**Why this priority**: This is the feature. If the run's shape is not legible on
one screen, there is nothing to demonstrate.

**Independent Test**: Load the console against a recorded fixture containing a
multi-step run with one fan-out; confirm the rail shows the steps in order, the
head is visually distinct from the rest, and the branches appear as separate
lanes under the checkpoint they came from.

**Acceptance Scenarios**:

1. **Given** a fixture with N ordered checkpoints, **When** the console renders,
   **Then** the rail shows all N in run order, top to bottom.
2. **Given** a fixture whose head is a specific checkpoint, **When** the console
   renders, **Then** that checkpoint is visually distinguished from every other.
3. **Given** a fixture containing a fan-out of B branches from one parent,
   **When** the console renders, **Then** the B branches appear as B parallel
   lanes associated with that parent, not interleaved into the rail.

---

### User Story 2 - Read the evidence behind any point (Priority: P1)

Selecting any checkpoint or branch shows its captured evidence — the exit status
and the output — and, when the reasoning agent gave a rationale for that step,
shows the rationale too, clearly marked as rationale and not as evidence.

**Why this priority**: Constitution Article X — a verdict shown without the
evidence behind it is a defect, and the audience built the runtime. The console
is where "evidence over assertion" is made visible.

**Independent Test**: Select a checkpoint that has an exit code, output, and a
rationale; confirm all three are shown, with the exit code and output presented
as evidence and the rationale visibly separated and labelled as the agent's
account.

**Acceptance Scenarios**:

1. **Given** a selected checkpoint with captured evidence, **When** the evidence
   panel renders, **Then** it shows the exit status and the output.
2. **Given** a selected checkpoint that also has a rationale, **When** the panel
   renders, **Then** the rationale is shown in a separate, labelled area that
   states it is the agent's account, not evidence.
3. **Given** a selected checkpoint with no rationale, **When** the panel renders,
   **Then** no rationale area is shown — an absent rationale is not rendered as
   an empty one.
4. **Given** a selected branch, **When** the panel renders, **Then** it shows
   that branch's own evidence, independent of the other branches.

---

### User Story 3 - Act on the run from the console (Priority: P2)

With a checkpoint selected, the developer can request a restoration to it, or
request a fan-out from it. The console surfaces the action and records the
request; carrying it out is the orchestrator's job — the console holds no live
runtime connection.

**Why this priority**: "Visible and operable on one screen" is the goal. A
console that can only watch forces the presenter back to a terminal mid-demo.

**Independent Test**: Select a checkpoint; confirm a restore action and a fan-out
action are offered; trigger each and confirm the console records the request
(identifying the target checkpoint) in a form the orchestrator can consume,
without the console itself contacting the runtime.

**Acceptance Scenarios**:

1. **Given** a checkpoint is selected, **When** the developer looks at the
   controls, **Then** a "restore to this checkpoint" action and a "fan out from
   this checkpoint" action are available.
2. **Given** no checkpoint is selected, **When** the developer looks at the
   controls, **Then** those actions are unavailable or clearly inert.
3. **Given** the developer triggers restore, **When** the action fires, **Then**
   the console records a restore request naming the selected checkpoint, and
   makes no runtime call itself.
4. **Given** the developer triggers fan-out, **When** the action fires, **Then**
   the console records a fan-out request naming the selected checkpoint.

---

### User Story 4 - Watch three machines work at once (Priority: P1)

While a fan-out runs, each branch lane shows that branch's live sandbox
identifier exactly as the runtime issued it, its running state (creating,
running, done, or failed), and its elapsed time — and these update on screen as
the branches progress, without anyone refreshing the page.

**Why this priority**: Constitution Article XI — the demo runs live, and the
visible proof that three real machines are working simultaneously is the
centrepiece. Stale or manually refreshed numbers undercut it.

**Independent Test**: Point the console at a fixture that changes over time (or a
sequence of fixtures) representing a fan-out progressing from creating to done;
confirm each lane's sandbox identifier, state, and elapsed time are shown and
that the display advances without a manual refresh.

**Acceptance Scenarios**:

1. **Given** a fan-out in progress, **When** the console renders a branch lane,
   **Then** it shows that branch's runtime sandbox identifier, its running
   state, and its elapsed time.
2. **Given** the underlying fixture changes while the console is open, **When**
   time passes, **Then** the branch lanes reflect the new state without a manual
   page refresh.
3. **Given** a branch that has finished, **When** its lane renders, **Then** its
   state reads done or failed and its lane is styled to match (promoted /
   running / released).

---

### User Story 5 - Keep the session counters in view (Priority: P2)

At all times the console shows how many sandboxes are currently live and how long
the session has been running. These are always visible, not hidden behind a
selection or a scroll.

**Why this priority**: Constitution Article XII — the live sandbox count on
screen is the guard against an exhausted quota during the demo; the session
timer is what lets the presenter stay inside two minutes.

**Independent Test**: Load any fixture; confirm the live sandbox count and the
session elapsed time are shown in a persistent area; change the fixture's live
count and confirm the displayed count follows.

**Acceptance Scenarios**:

1. **Given** the console is open on any view, **When** it renders, **Then** the
   current live sandbox count and the session elapsed time are both visible.
2. **Given** a checkpoint is selected and the evidence panel is open, **When**
   the console renders, **Then** the counters remain visible.
3. **Given** the fixture's live sandbox count changes, **When** the console next
   renders, **Then** the displayed count matches.

---

### User Story 6 - Legible from the back of the room (Priority: P2)

The console remains readable when the browser is zoomed out or the window is
small — the case where it is projected and the audience is not at the keyboard.
Runtime-issued values stay in monospace and console-derived values stay in the
interface face at every scale, so the two are never confused.

**Why this priority**: FR-006-09 and FR-006-10 together are what make the screen
trustworthy at a glance during a live judged demonstration.

**Independent Test**: Reduce the browser zoom to a level a projector would use
and shrink the window; confirm the rail, the lanes, the evidence panel, and the
counters are all still readable and none collapse into unreadable overlap;
confirm sandbox and checkpoint identifiers, exit codes, and output are in
monospace and headings, labels, and counts are in the interface face.

**Acceptance Scenarios**:

1. **Given** the browser at a reduced zoom and a narrow window, **When** the
   console renders, **Then** all four regions (rail, lanes, evidence, counters)
   remain readable with no overlapping or clipped text in the demo fixture.
2. **Given** any rendered value, **When** it is a runtime-issued value (sandbox
   id, checkpoint id, exit code, captured output, executed instruction), **Then**
   it is shown in monospace.
3. **Given** any rendered value that the console derived (heading, label, count,
   verdict prose, state word), **When** it is shown, **Then** it is in the
   interface face.

---

### Edge Cases

- What happens before any run has been recorded — the fixture is missing or
  empty? The console shows a placeholder state ("waiting for the run") rather
  than a broken layout, and recovers on its own once the fixture appears.
- What happens when the fixture cannot be reached because the page was opened
  directly from disk rather than served? The console falls back to a built-in
  sample so the layout is still demonstrable, and says so.
- What happens when a checkpoint has output far longer than the panel? The output
  area scrolls within itself; the rest of the layout does not grow or shift.
- What happens when a fan-out has more branches than fit side by side? The lanes
  stack; each stays fully readable; the layout does not overflow the screen
  horizontally.
- What happens when the fixture updates mid-render? The next render uses the new
  fixture whole; the console never shows half of one state and half of another.
- What happens when a selected checkpoint disappears from a later fixture (it was
  released)? The selection clears or falls back to the head; the evidence panel
  does not show stale data as current.
- What happens when the same value is both runtime-issued and shown in a heading
  (e.g. a checkpoint id in a section title)? It is shown in monospace — the
  runtime-issued rule wins over the heading rule.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-006-01**: The console MUST render the run as a rail of checkpoints in run
  order, with the head visually distinguished from every other checkpoint.
- **FR-006-02**: The console MUST render branches as parallel lanes associated
  with their common parent checkpoint, not interleaved into the ordered rail.
- **FR-006-03**: The console MUST permit selecting any checkpoint and, for the
  selected checkpoint, requesting a restoration to it — recording the request
  without itself contacting the runtime.
- **FR-006-04**: The console MUST permit requesting a fan-out from the selected
  checkpoint — recording the request without itself contacting the runtime.
- **FR-006-05**: The console MUST display, for every branch, its live sandbox
  identifier (as issued), its running state, and its elapsed time, and MUST
  update these on screen as the underlying fixture changes, with no manual
  refresh.
- **FR-006-06**: The console MUST display the captured evidence — exit status and
  output — for any selected checkpoint or branch.
- **FR-006-07**: The console MUST display the number of currently live sandboxes
  and the total elapsed time of the session, visible at all times regardless of
  selection or scroll position.
- **FR-006-08**: The console MUST distinguish a reasoning agent's rationale from
  captured evidence wherever both are shown — a separate, labelled area that
  states the rationale is the agent's account, not evidence — and MUST NOT render
  an absent rationale.
- **FR-006-09**: The console MUST render every runtime-issued value (sandbox
  identifiers, checkpoint identifiers, exit codes, captured output, executed
  instructions) in monospace, and every value it derived itself (headings,
  labels, counts, verdict prose, state words) in the interface face.
- **FR-006-10**: The console MUST remain legible — no overlapping, clipped, or
  unreadable text in the demo fixture — when viewed at a reduced browser zoom and
  a narrow window.

### Non-Functional Requirements

- **NFR-006-01**: The console MUST render entirely from a recorded fixture with
  no runtime connection, so it can be built and rehearsed independently of the
  integration. Opened without a served fixture, it MUST fall back to a built-in
  sample and remain demonstrable.
- **NFR-006-02**: State updates MUST reach the screen without a manual refresh —
  the console re-reads the fixture on its own and re-renders.
- **NFR-006-03**: The console MUST match the Design Reference — palette, type
  faces, and the two-column-collapsing-to-one layout with a persistent counter
  bar.
- **NFR-006-04**: The console MUST be a single self-contained page — no build
  step, no external runtime dependency — so it opens by pointing a browser at it.

### Key Entities

- **Rail Checkpoint**: One node on the ordered rail — its index, identifier,
  executed instruction, sandbox identifier, state, and whether it is the head.
  Rendered top-to-bottom in run order.
- **Branch Lane**: One branch of a fan-out — its checkpoint identifier, runtime
  sandbox identifier, running state (creating / running / done / failed),
  elapsed time, exit status, and its promoted / running / released styling.
- **Evidence Panel**: The captured result for the selected checkpoint or branch —
  exit status and output — plus, when present, the separately labelled rationale.
- **Session Counters**: The always-visible figures — currently live sandbox
  count, session elapsed time, total checkpoint count, branch count.
- **Action Request**: A recorded intent produced by the console — a restore
  request or a fan-out request — naming the target checkpoint, consumable by the
  orchestrator, produced without any runtime call from the console.
- **Console Fixture**: The recorded file the console reads — the run tree in its
  renderable form (Specification 001) enriched with per-branch progress
  (Specification 004), the live sandbox count, and the session elapsed time.
- **Verdict Block**: When the fixture carries a ranking result, the promoted
  branch and the one-line reason, marked as judged on execution evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the demo fixture, 100% of checkpoints appear on the rail in run
  order and the head is distinguishable from every other node at a glance.
- **SC-002**: On the demo fixture, every fan-out branch appears as its own lane
  under the common parent; 0 branches are interleaved into the rail.
- **SC-003**: Selecting any checkpoint or branch shows its exit status and output
  within one render; 100% of selections with a rationale show the rationale in a
  separate labelled area, and 0 selections without one show an empty rationale
  area.
- **SC-004**: With a selected checkpoint, a restore action and a fan-out action
  are available; triggering either records a request naming that checkpoint and
  produces 0 runtime calls from the console.
- **SC-005**: While the fixture changes over a fan-out, each branch lane's
  sandbox identifier, state, and elapsed time update on screen with no manual
  refresh, within one refresh interval of the fixture changing.
- **SC-006**: The live sandbox count and session elapsed time are visible in
  100% of console states, including with the evidence panel open and the page
  scrolled.
- **SC-007**: At a reduced browser zoom and a narrow window, all four regions
  remain readable on the demo fixture with no overlapping or clipped text.
- **SC-008**: 100% of runtime-issued values on screen are in monospace and 100%
  of console-derived values are in the interface face.
- **SC-009**: Opened directly from disk with no served fixture, the console
  renders its built-in sample and states that it is a sample.
- **SC-010**: The console is one file that opens in a browser with no build step
  and no runtime running.

## Assumptions

- **The console is a single static page.** No framework, no build, no server of
  its own — it is opened in a browser (served from a static file server so it can
  read the fixture) and needs nothing else running (NFR-006-04).
- **"Without a manual refresh" is periodic re-reading of the fixture.** The
  console re-fetches `fixtures/tree.json` on a short interval and re-renders; a
  few seconds of latency between a fixture change and the screen is acceptable
  for the demonstration.
- **The Console Fixture is `fixtures/tree.json`**, written by `demo.py`. This
  feature may require `demo.py` (or a small fixture writer) to add fields the
  Specification 001 `as_tree` form does not carry on its own: the per-branch
  progress (Specification 004), the live sandbox count, and the session elapsed
  time. Defining those additions is in scope; changing the run tree model is
  not.
- **"Recording a request" is writing a small structured intent** the console
  emits — for the demonstration it is sufficient for this to be visible and
  inspectable (for example, shown on screen and logged); wiring the orchestrator
  to consume it is out of scope for this feature.
- **"Reduced scale" means a browser zoom and window size a projector would use**
  — roughly 67–80% zoom at 1280px wide — not an arbitrary minimum. The demo
  fixture is the reference content for the legibility check.
- **Runtime-issued vs derived** is decided by origin: a value that came from the
  sandbox runtime or the reasoning agent is runtime-issued (monospace); a value
  the console computed, counted, or labelled is derived (interface face). A
  checkpoint identifier shown inside a heading is still monospace.
- **This feature has no automated UI-rendering tests** (Constitution Article VI —
  "UI rendering … is not tested"). The fixture *shape* — the fields the console
  depends on — may have a pure-logic test. The console itself is proven by
  building it against the fixture and by the live demonstration.
- **Dark theme only**, per the Design Reference; there is no light mode and no
  theme toggle.

## Out of Scope

- Authentication or any access control.
- Multiple concurrent runs — one run at a time.
- Persistence of console state (selection, scroll) across a page reload.
- The orchestrator consuming the console's restore / fan-out requests — this
  feature records the request; acting on it belongs to the orchestrator.
- Editing checkpoints, instructions, or evidence from the console.
- A light theme or a theme toggle.
- Any automated test of visual rendering.
- Changing the run tree model or the `as_tree` form (Specification 001).
