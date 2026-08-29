# Feature Specification: Deployable Console

**Feature ID**: `009-deployable-console`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Operational Visibility — shared

**Business Actors**: Developer; Judge or observer not at the presenter's machine

**Input**: User description: "Create the timeline console as a deployable web
application instead of the single local file, so it can be shown at a public URL,
fed by an endpoint the demonstration can push run fixtures to."

## Business Context

### Business Goal

The timeline console (Specification 006) renders only when someone serves the
repository and runs `demo.py` on the same machine. Give it a public URL so the
run can be shown to someone who is not at the presenter's terminal — a remote
judge, a teammate, a reviewer after the event — without changing what the live
demonstration runs.

### Business Value

Specification 006 proved the view. This makes the view shareable. It costs
nothing on the demonstration's critical path: the live judged demo still drives
the local `ui/console.html` from `demo.py` (Constitution Article XI); the hosted
console is the same view at a link, for everyone who cannot stand at the laptop.

### Dependencies

- **Specification 006 — Timeline Console**: this feature reproduces Specification
  006's run view in full — the ordered checkpoint rail with the head marked, the
  branch lanes under their common parent, the evidence panel, the persistent
  session-counter bar, the restore / fan-out request recording, and the
  monospace-vs-interface-face type rule. It adds a build step, a public
  deployment, and a fixture endpoint; it removes no Specification 006 behaviour.
- **Specification 006 — Console Fixture**: the data the hosted console renders is
  exactly the Console Fixture shape Specification 006 defines
  (`console_fixture(engine)` output). This feature transports and renders it; it
  does not extend it.
- **Data source**: a single fixture endpoint. The demonstration's fixture writer
  (`demo.py` or a small helper) pushes the current `fixtures/tree.json` to that
  endpoint; the hosted console reads it back on an interval. Neither the console
  nor the endpoint holds any connection to the sandbox runtime or the engine.

## Design Reference *(mandatory for this feature)*

The visual target is unchanged from Specification 006: `.rewind/console-mockup.html`
and the working `ui/console.html`. The hosted console MUST match Specification
006's Design Reference — palette, type faces, and the two-column-collapsing-to-one
layout with a persistent counter bar — section by section. That document governs;
this feature re-implements against it and must not drift from it.

Dark theme only. No light mode. No theme toggle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open the run at a link (Priority: P1)

A remote judge, or a teammate on another machine, is given a URL. They open it in
a browser and see the current run exactly as the local console shows it — the
checkpoint rail with the head marked, the branch lanes, the evidence panel, and
the counter bar — without cloning the repository, installing anything, or running
`demo.py`.

**Why this priority**: This is the feature. If the view is not reachable at a
plain URL by someone with no local setup, nothing here has been delivered.

**Independent Test**: Deploy the build; open the deployed URL in a clean browser
profile with no local server running; confirm the full Specification 006 run view
renders from the endpoint's current fixture.

**Acceptance Scenarios**:

1. **Given** the deployment is live and a fixture has been pushed, **When** a
   viewer opens the URL, **Then** the run view renders with every Specification
   006 region present (rail, lanes, verdict when present, evidence, counter bar).
2. **Given** the viewer has nothing from the repository running locally, **When**
   they open the URL, **Then** the console still renders — its only network call
   is to the fixture endpoint.
3. **Given** a checkpoint or a branch is selected, **When** the evidence panel
   renders, **Then** it behaves as in Specification 006 — exit status and output
   shown, rationale in a separate labelled area, absent rationale not rendered.

---

### User Story 2 - Push the run to the link (Priority: P1)

The presenter runs the demonstration locally as always. With one environment
setting, each time `demo.py` writes `fixtures/tree.json` it also pushes that
fixture to the endpoint, and the hosted console reflects the new state within one
refresh interval — without the presenter touching the deployment.

**Why this priority**: A hosted console that shows a frozen fixture is a
screenshot. The value is that the remote viewer watches the same run advance that
the room is watching.

**Independent Test**: Point the push setting at a deployed endpoint; run
`demo.py`; with the hosted URL open in another browser, confirm the rail, lanes,
and counters advance to match the local console within one interval, with no
manual action on the deployment.

**Acceptance Scenarios**:

1. **Given** the push setting is configured, **When** `demo.py` writes the
   fixture, **Then** the same fixture is sent to the endpoint and becomes what
   the endpoint serves.
2. **Given** the hosted URL is open, **When** a new fixture is pushed, **Then**
   the hosted view updates to the new state within one refresh interval, with no
   manual refresh.
3. **Given** the push setting is absent or the endpoint is unreachable, **When**
   `demo.py` runs, **Then** the local run and the local console are completely
   unaffected — the push is best-effort and its failure is silent to the run.

---

### User Story 3 - Reject anything that is not this run's fixture (Priority: P1)

The endpoint accepts a new fixture only from someone holding the shared secret,
and only when the payload is a well-formed console fixture. A request without the
secret, or with a malformed body, is refused and leaves the served fixture
unchanged.

**Why this priority**: The endpoint is public. Without an auth check and a shape
check, any request could blank or corrupt the view mid-demonstration.

**Independent Test**: Send an upload with no secret, an upload with a wrong
secret, and an upload with a valid secret but a body that is not a console
fixture; confirm each is rejected with a clear status and that a subsequent read
still returns the last good fixture.

**Acceptance Scenarios**:

1. **Given** an upload with no shared secret or a wrong one, **When** the
   endpoint handles it, **Then** it is rejected and the served fixture is
   unchanged.
2. **Given** an upload with a valid secret but a body that is not a well-formed
   console fixture, **When** the endpoint handles it, **Then** it is rejected and
   the served fixture is unchanged.
3. **Given** an upload with a valid secret and a well-formed fixture, **When** the
   endpoint handles it, **Then** it is accepted and becomes what the endpoint
   serves.
4. **Given** any uploaded content, **When** the endpoint stores it, **Then** it
   is stored and served as data only — never executed or evaluated — and is
   subject to a maximum size.

---

### User Story 4 - Legible before the first push (Priority: P2)

Before any fixture has been pushed, or when the endpoint cannot be reached, the
hosted console still shows a coherent run view — a representative fixture shipped
with the deployment, and failing that a built-in sample — and says plainly when
what is on screen is sample data, not a live run.

**Why this priority**: Constitution Article XIII — a hosted URL that shows a
broken layout, or silently shows stale sample data as if it were live, misleads
the exact audience this feature is for.

**Independent Test**: Open the deployment with the endpoint returning nothing
yet; confirm the shipped representative fixture renders. Simulate the endpoint
unreachable; confirm the built-in sample renders and the console states it is a
sample.

**Acceptance Scenarios**:

1. **Given** no fixture has been pushed, **When** a viewer opens the URL, **Then**
   the shipped representative fixture renders as a full run view.
2. **Given** the endpoint is unreachable, **When** the console loads, **Then** the
   built-in sample renders and the console states on screen that it is showing
   sample data.
3. **Given** the console is showing sample or shipped data, **When** a real
   fixture later becomes available, **Then** the console picks it up on its next
   interval with no manual refresh.

---

### User Story 5 - Replay the run for a viewer (Priority: P3)

A viewer who arrives after the run has finished can press one control and watch
the run's shape play back through the same console — seed steps appearing, a step
failing, the head returning to the last good checkpoint, three branches fanning
out, then the verdict — over a short span, then the console returns to the live
view.

**Why this priority**: The hosted console's audience often opens the link when
nothing is running. A replay turns a static end-state into the story the room
saw, without touching the engine.

**Independent Test**: With the console showing a finished run, press the replay
control; confirm the view animates through the run's stages and, on completion,
returns to whatever the fixture endpoint currently serves; confirm the console
states plainly, throughout, that a replay is playing and it is not a live push.

**Acceptance Scenarios**:

1. **Given** a finished run is on screen, **When** the viewer starts a replay,
   **Then** the console steps through the run's stages (seed → failure → rewind →
   fan-out → verdict) derived from the current fixture, making no network call.
2. **Given** a replay is playing, **When** the console renders, **Then** it shows
   an on-screen statement that a recorded replay is playing, not a live push.
3. **Given** a replay reaches its end, or the viewer stops it, **When** it
   finishes, **Then** the console resumes rendering the fixture the endpoint
   serves, on the normal poll.

---

### Edge Cases

- The endpoint is reachable but returns a fixture that fails the shape check on
  the client — the console keeps the last good fixture it rendered and does not
  replace a good view with a broken one.
- Two pushes arrive close together — the endpoint serves the most recently
  accepted one; there is no merge and no history.
- The upload body is far larger than any real fixture — it is rejected on size
  before any parsing.
- The viewer's browser blocks the poll (offline, network error) — the console
  keeps rendering the last fixture it has and recovers on a later interval.
- The deployment is opened at a sub-path or with a trailing slash — the console
  resolves the endpoint relative to its own location, not an absolute host.
- A secret is present in the client bundle — this MUST NOT happen; the secret is
  only ever compared on the endpoint side (NFR-009-05).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-009-01**: The hosted console MUST present the Specification 006 run view in
  full — ordered checkpoint rail with the head distinguished, branch lanes
  associated with their common parent, evidence panel (exit status + output) for
  any selected checkpoint or branch, the agent rationale as a separate labelled
  non-evidence area absent when there is none, the verdict block when the fixture
  carries one, and the persistent session-counter bar — with no loss of any
  Specification 006 functional behaviour.
- **FR-009-02**: The hosted console MUST be reachable at a public URL and MUST
  render without the viewer running any part of the repository locally.
- **FR-009-03**: The hosted console MUST obtain its run data from a single
  fixture endpoint, re-read that endpoint on a short interval, and re-render on
  change with no manual refresh (parity with NFR-006-02).
- **FR-009-04**: The fixture endpoint MUST accept an authenticated upload of a new
  console fixture and MUST serve the most recently accepted fixture to the
  console on read.
- **FR-009-05**: An upload without a valid shared secret MUST be rejected and MUST
  NOT change what the endpoint serves.
- **FR-009-06**: An upload whose body is not a well-formed console fixture MUST be
  rejected and MUST NOT change what the endpoint serves.
- **FR-009-07**: With no fixture yet accepted, or the endpoint unreachable, the
  console MUST fall back — first to a representative fixture shipped with the
  deployment, then to a built-in sample — remain legible, and state on screen
  when it is showing sample data (parity with NFR-006-01 / SC-009).
- **FR-009-08**: The hosted console MUST hold no connection to the sandbox
  runtime or the engine; its only network call MUST be to the fixture endpoint
  (parity with NFR-006-01).
- **FR-009-09**: The demonstration's fixture writer MUST be able to push the
  current `fixtures/tree.json` to the endpoint, and this push MUST be optional —
  its absence, misconfiguration, or failure MUST NOT affect the local run or the
  local console.
- **FR-009-10**: The hosted console MUST render every runtime-issued value
  (sandbox identifiers, checkpoint identifiers, exit codes, captured output,
  executed instructions) in monospace and every console-derived value (headings,
  labels, counts, verdict prose, state words) in the interface face, matching
  Specification 006 FR-006-09.
- **FR-009-11**: The hosted console MUST offer a replay control that, from the
  currently displayed fixture, plays the run's stages back through the same view
  over a short span and then resumes the live view — deriving every frame
  client-side, making no network call, and stating on screen throughout that a
  recorded replay is playing and it is not a live push.

### Non-Functional Requirements

- **NFR-009-01**: The hosted console is a built web application — a build step is
  expected and permitted. This is the single place Specification 006's
  "one self-contained page, no build step" constraint (NFR-006-04) does not
  apply. Specification 006's `ui/console.html` is unchanged by this feature.
- **NFR-009-02**: The web application MUST be deployable to a static host with
  serverless functions from a single `web/` directory, with no repository-root
  change required other than the optional push hook in `demo.py`.
- **NFR-009-03**: The hosted console MUST match Specification 006's Design
  Reference — palette, type faces, and the two-column-collapsing-to-one layout
  with a persistent counter bar.
- **NFR-009-04**: The fixture endpoint MUST enforce a maximum upload size and
  MUST store and serve uploaded content as data only — never executing or
  evaluating it.
- **NFR-009-05**: No secret — the upload shared secret, any storage credential —
  may be present in the browser bundle or reachable by client code.
- **NFR-009-06**: The console MUST re-read the endpoint on an interval no longer
  than Specification 006's (≤ 2s effective), and a failed or malformed read MUST
  leave the last good fixture on screen rather than clearing it.

### Key Entities

- **Hosted Console**: the built web application — one component per Specification
  006 region (rail, branch lanes, verdict block, evidence panel, requests list,
  counter bar) over a shared run-fixture state.
- **Fixture Endpoint**: the single URL the console reads and the writer pushes
  to. A read returns the current fixture; an authenticated write replaces it.
- **Current Fixture**: the most recently accepted upload — the Console Fixture
  shape from Specification 006, unchanged.
- **Shipped Fixture**: a representative Console Fixture bundled with the
  deployment, served when nothing has been accepted yet.
- **Built-in Sample**: the minimal in-code fixture the console renders when the
  endpoint cannot be reached at all.
- **Push Helper**: the optional client — in `demo.py` or a standalone tool — that
  sends `fixtures/tree.json` to the endpoint with the shared secret.
- **Shared Secret**: the token an upload must carry, compared only on the
  endpoint side, never shipped to the browser.
- **Replay**: a client-only playback that derives a short sequence of frames from
  the displayed fixture and steps the view through the run's stages, then resumes
  the live view. It never runs the engine and makes no network call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-009-01**: The deployed URL, opened in a clean browser with nothing from
  the repository running locally, renders the full Specification 006 run view
  from the endpoint's current fixture.
- **SC-009-02**: 100% of Specification 006's ten functional requirements are
  observable on the hosted console against the same demo fixture (verified by
  reusing Specification 006's visual-acceptance checklist).
- **SC-009-03**: With the push configured, running `demo.py` makes the hosted
  view advance to match the local console within one refresh interval, with 0
  manual actions on the deployment.
- **SC-009-04**: An upload with no secret, a wrong secret, or a malformed body is
  rejected in 100% of cases, and a read immediately afterwards returns the last
  good fixture unchanged.
- **SC-009-05**: With the push unconfigured or the endpoint down, `demo.py`
  completes every beat exactly as before and the local console is unaffected.
- **SC-009-06**: Opened with the endpoint returning nothing, the console renders
  the shipped fixture; with the endpoint unreachable, it renders the built-in
  sample and states on screen that it is a sample.
- **SC-009-07**: 0 secrets appear in the built client bundle (grep of the build
  output for the token value and any storage credential returns nothing).
- **SC-009-08**: 100% of runtime-issued values on the hosted console render in
  monospace and 100% of console-derived values in the interface face.
- **SC-009-09**: The `web/` directory builds and deploys with no change to
  `src/rewind/`, the engine, or the Console Fixture shape.
- **SC-009-10**: The replay control plays the run's stages (seed → failure →
  rewind → fan-out → verdict) from the displayed fixture with 0 network calls,
  shows a "recorded replay" statement for 100% of its duration, and returns to
  the live view on completion or when stopped.

## Assumptions

- **The hosted console is for sharing the view, not for running the demo.** The
  live judged demonstration runs locally against `ui/console.html` driven by
  `demo.py` (Constitution Article XI). The hosted URL is not on the demo's
  critical path and no time budgeted for the graded integration is spent on it.
- **The Console Fixture shape is exactly Specification 006's.** This feature
  transports and renders `console_fixture(engine)` output; adding fields to that
  shape is out of scope here.
- **"Fixture endpoint" is one serverless function with a single-object store
  behind it.** It holds one current fixture — no database, no run history, no
  merge.
- **"Authenticated" is a shared secret carried in a request header** and compared
  on the endpoint side. This is upload protection for a demo surface, not a user
  identity system.
- **"No manual refresh" is periodic polling**, as in Specification 006 — the
  console re-fetches on a short interval; a few seconds of latency between a push
  and the hosted screen is acceptable.
- **This feature has no automated UI-rendering tests** (Constitution Article VI —
  "UI rendering … is not tested"). The endpoint's accept / reject / serve logic
  and the fixture *shape* are unit-tested; the console is proven by a deploy and
  by reusing Specification 006's visual-acceptance checklist.
- **Dark theme only**, inherited from Specification 006. No light mode, no toggle.
- **A representative `fixtures/tree.json` already exists** (committed under
  Specification 006). The shipped fixture is a copy of it placed in the `web/`
  build.

## Out of Scope

- Any change to `ui/console.html`, `src/rewind/`, the engine, or the Console
  Fixture shape (Specification 006 / Specification 001).
- Viewer authentication or access control on the hosted console — the view is
  public once deployed.
- Server-side persistence or processing of the console's restore / fan-out
  requests — they remain recorded client-side only, exactly as in Specification
  006.
- Real-time streaming, websockets, or server-sent events — polling only, as in
  Specification 006.
- A run history, multiple concurrent runs, or fixture versioning on the endpoint
  — it holds one current fixture.
- A light theme or a theme toggle.
- Any automated test of visual rendering.
- Wiring the orchestrator to consume the recorded requests (already out of scope
  in Specification 006).
- Triggering a real engine run from the hosted console. The replay control
  (FR-009-11) is a client-only playback of an already-recorded fixture; it does
  not spawn a sandbox or call the engine. A real in-function run was considered
  and rejected — it would put `DAYTONA_API_KEY` on a public endpoint (quota-abuse
  surface, against Article XII) and a full run exceeds the deploy target's
  function time limit on the current plan.
