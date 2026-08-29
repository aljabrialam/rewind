# Implementation Plan: Deployable Console

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/009-deployable-console/`

**Input**: Feature specification from `specs/009-deployable-console/spec.md`

## Summary

Re-implement the Specification 006 timeline console as a small React application,
deploy it to a public URL, and feed it from one serverless fixture endpoint that
`demo.py` can push `fixtures/tree.json` to. The hosted console reproduces every
Specification 006 region and behaviour — checkpoint rail with the head marked,
branch lanes under their common parent, evidence panel with a separately labelled
rationale, verdict block, persistent counter bar, client-side restore / fan-out
request recording, and the monospace-vs-interface-face type rule — reading the
endpoint on a ≤2s poll. When nothing has been pushed it renders a fixture bundled
with the deployment; when the endpoint is unreachable it renders a built-in
sample and says so. `ui/console.html` and the engine are untouched.

Technical approach: (1) a Vite + React + TypeScript app under `web/`, one
component per Specification 006 region, styled from the Specification 006 Design
Reference palette/type as CSS custom properties; (2) a `web/api/fixture.ts`
serverless function — `GET` returns the current fixture (single-object store →
bundled shipped fixture), `POST` validates a shared-secret header and the Console
Fixture shape, then replaces the stored object; (3) a `useFixture` polling hook
with the fallback chain endpoint → bundled `tree.json` → in-code sample; (4)
`tools/push_console.py` plus an optional env-gated push at the end of `demo.py`,
both best-effort; (5) reuse Specification 006's visual-acceptance checklist for
the run view and add unit tests only for the endpoint's accept/reject/serve
logic and the fixture shape. Per Constitution Article VI there are **no automated
UI-rendering tests**.

## Technical Context

**Language/Version**: TypeScript 5 / React 18 for the console (built with Vite 5);
Node 20 serverless runtime for `web/api/fixture.ts`; Python 3.11+ (stdlib
`urllib`) for the push helper.

**Primary Dependencies**: `react`, `react-dom`, `vite`, `@vitejs/plugin-react`,
`typescript`. Serverless single-object store: `@vercel/blob` (the deploy target's
native blob store) with a filesystem fallback to the bundled fixture. No new
Python dependency — the push helper uses `urllib`.

**Storage**: one object — the current console fixture — in the deploy target's
blob store, keyed by a fixed name; `web/public/tree.json` (a copy of the
Specification 006 committed `fixtures/tree.json`) is the shipped fallback baked
into the build.

**Testing**: `vitest` (or plain node test) for `web/api` accept/reject/serve
logic — valid upload accepted, missing/wrong secret rejected, malformed body
rejected, oversize body rejected, read after a rejected write unchanged, read
with an empty store returns the shipped fixture. Python `pytest` reuse of the
Specification 006 `console_fixture` shape test as the contract the payload must
satisfy. **No UI-rendering tests** (Article VI) — the run view is signed off with
Specification 006's `checklists/visual-acceptance.md`.

**Target Platform**: Vercel (static build for `web/` + one Node serverless
function). Any static-host-with-functions provider works; Vercel is the named
target. Root directory `web/`.

**Project Type**: single project — internal Python library + the existing static
UI page (Specification 006) + a new deployable web app in `web/`.

**Performance Goals**: endpoint read + re-render on a ≤2s interval (NFR-009-06);
render is trivial at demo scale (tens of nodes); the serverless `GET` is a single
object fetch.

**Constraints**: no runtime/engine connection from the console (FR-009-08);
Console Fixture shape unchanged (dependency on Specification 006); no secret in
the client bundle (NFR-009-05); upload size-capped and stored as data only
(NFR-009-04); dark theme only; must match Specification 006's Design Reference
(NFR-009-03); deployable from `web/` alone (NFR-009-02).

**Scale/Scope**: one run, ~10–20 checkpoints, ≤3 branches; one endpoint holding
one fixture; 10 FRs, 6 NFRs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work must reach the screen; the deliverable is the 2-minute live demo | The live demo is unchanged — it drives `ui/console.html` locally. This feature is a **shared** surface for remote viewers, explicitly off the critical path (spec Assumptions). It reaches *a* screen — a URL others can open. **Pass, with the honest framing that it is not the demo itself.** |
| II — Specification First | Tech names only in the plan | Spec 009 names only "a public URL", "a build step", "a fixture endpoint", "a shared secret". This plan names React / Vite / TypeScript / Vercel / `@vercel/blob`. **Pass** |
| IV — Nothing Is Invented | No runtime capability used unless observed; all runtime access via one port | This feature makes **no** runtime call — the console reads a fixture, the endpoint stores a blob. `@vercel/blob` is a hosting concern, not the sandbox runtime; it is not behind the sandbox port and does not need to be. **Pass** |
| VI — Traceability & Pyramid + "what is not tested" | FR → named test; **UI rendering is not tested** | The endpoint's accept/reject/serve logic gets pure-logic tests; the Console Fixture shape is the reused Specification 006 test; the run view's rendering is out of automated scope per Article VI, signed off with Specification 006's visual-acceptance checklist. FR→check map in [quickstart.md](quickstart.md). **Pass** |
| VIII — Sponsor Integration Is Load-Bearing; additive integrations carry a stop line | No hour spent on additive integrations before the graded one is demo-complete; nothing additive on the critical path | This is a hosting/visibility feature, not a sponsor integration. It touches no sandbox runtime and no reasoning provider, and sits off the demo critical path. It is built only after Specifications 000–006 are demo-complete. **Pass** |
| X — Evidence Over Assertion | Evidence and rationale visually distinct; a verdict shows its evidence | Reproduced verbatim from Specification 006 — FR-009-01 carries FR-006-06 and FR-006-08 forward; the verdict block stays marked "judged on execution evidence". **Pass** |
| XI — Proven In The Runtime, Live | The demo runs live on stage; the backup recording is not the plan | The hosted console renders a fixture and is **not** presented as the live proof. The sandbox lifecycle stays proven locally on stage. This feature does not touch that. **Pass** |
| XII — Resource Hygiene | Live sandbox count visible on screen at all times | Carried forward from Specification 006 — the counter bar with the live sandbox count is FR-009-01. The endpoint creates no sandboxes. **Pass** |
| XIII — Honest Framing | No overclaiming; sample data labelled | FR-009-07 requires the console to state on screen when it is showing sample or shipped data rather than a live push. The README entry will call the hosted console a shared view, not the demo. **Pass** |

**Result**: No violations. The one thing to keep honest — this is a shared
convenience surface, not the graded demo — is written into the spec Assumptions
and the README entry. Complexity Tracking below notes the single deviation from
Specification 006 (the build step) and why it is contained.

## Project Structure

### Documentation (this feature)

```text
specs/009-deployable-console/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fixture-endpoint.md      # GET/POST contract: methods, auth header, status codes, size cap, validation, fallback order
└── checklists/
    ├── requirements.md
    └── visual-acceptance.md      # points at Specification 006's checklist + the deploy-only items
```

### Source Code (repository root)

```text
web/                              # NEW — the deployable console. Self-contained; deploy root = web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.node.json
├── index.html
├── vercel.json                   # framework: vite; the api/ dir is the serverless function
├── .env.example                  # REWIND_CONSOLE_TOKEN (server), BLOB_READ_WRITE_TOKEN (server) — never VITE_-prefixed
├── public/
│   └── tree.json                 # COPY of the Specification 006 committed fixtures/tree.json — the shipped fallback
├── api/
│   └── fixture.ts                # GET current fixture (blob → bundled); POST (token + shape + size checked) replaces it
└── src/
    ├── main.tsx
    ├── App.tsx                    # layout + shared run-fixture state + selection
    ├── theme.css                  # Specification 006 palette + type as CSS custom properties (NFR-009-03)
    ├── sample.ts                  # the built-in SAMPLE fixture (FR-009-07)
    ├── types.ts                   # ConsoleFixture, RailNode, BranchProgress, Verdict — mirrors console_fixture() output
    ├── useFixture.ts              # poll hook: /api/fixture → /tree.json → SAMPLE; keep last good on failure (NFR-009-06)
    └── components/
        ├── Rail.tsx               # FR-009-01 (rail, head marked) — FR-006-01
        ├── BranchLanes.tsx        # FR-009-01 (lanes under parent, state word, elapsed) — FR-006-02/05
        ├── VerdictCard.tsx        # FR-009-01 (verdict block when present) — Article X
        ├── EvidencePanel.tsx      # FR-009-01 (exit + output; rationale separate & labelled) — FR-006-06/08
        ├── RequestsList.tsx       # FR-009-01 (restore/fan-out recorded client-side, no runtime call) — FR-006-03/04
        └── Footer.tsx             # FR-009-01 (live sandboxes, checkpoints, branches, session elapsed) — FR-006-07

tools/
└── push_console.py               # NEW — POST fixtures/tree.json to the endpoint with REWIND_CONSOLE_TOKEN; best-effort

demo.py                           # EDIT (minimal, additive) — in main(), after run_demo() returns with
                                  #   res.fixture_written, if REWIND_CONSOLE_ENDPOINT and REWIND_CONSOLE_TOKEN
                                  #   are set, call the push helper inside try/except; any failure prints one
                                  #   line and is ignored (FR-009-09). The fixture itself is written by
                                  #   rewind.harness.run_demo (spec 007) — that is not touched.

web/api/__tests__/fixture.test.ts # NEW — accept/reject/serve logic (Article VI: not a UI-rendering test)
```

### Repository-root impact

`src/rewind/` — **untouched**. `ui/console.html` — **untouched**. `demo.py` — one
additive, env-gated, exception-wrapped block at the end. `fixtures/tree.json` —
read only (copied into `web/public/`). Everything else new is under `web/` or
`tools/`.

**Structure Decision**: The deployable console is fully contained in `web/` so it
can be a Vercel project with root directory `web/` and no awareness of the Python
package. The Python side gains one optional helper and one guarded call.

## Complexity Tracking

| Deviation | Why it is needed | Why it is contained |
|---|---|---|
| A build step (Vite) — Specification 006 NFR-006-04 forbids one for `ui/console.html` | A public URL for non-local viewers needs a hosted build; a single `file://` page cannot be shared or fed by an endpoint | NFR-009-01 scopes the deviation to `web/` only; `ui/console.html` keeps its no-build guarantee and stays the live-demo surface |
| A serverless function + blob object | The hosted console needs a data source that `demo.py` can push to without the viewer running anything | One function, one object, no database; `web/api/` is the entire server surface; it makes no runtime call |
| A new dependency (`@vercel/blob`) | The single-object store on the named deploy target | Isolated to `web/api/fixture.ts`; a filesystem fallback to the bundled fixture means the console still works if the store is absent |

## Phase 0 — Research

See [research.md](research.md). Spec 009 has no `[NEEDS CLARIFICATION]`. Phase 0
records: why a component framework + build over extending `ui/console.html` (and
why that forces a new spec rather than a Specification 006 amendment); the
single-object store choice over a database; the shared-secret upload model and
why no secret can be `VITE_`-prefixed; the endpoint → bundled → sample fallback
chain; the `demo.py` push kept best-effort and env-gated; and why Article VI
keeps the run view out of automated tests while the endpoint logic stays in.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — the `ConsoleFixture` TypeScript shape (mirror
  of `console_fixture()` output), the endpoint request/response shapes, the
  environment variables and which side each lives on, and the fallback-state the
  console tracks (live / shipped / sample).
- [contracts/fixture-endpoint.md](contracts/fixture-endpoint.md) — `GET` and
  `POST` on the fixture endpoint: methods, the auth header, status codes, the
  size cap, the shape-validation rules (what makes a body a well-formed console
  fixture), and the exact fallback order on read.
- [checklists/visual-acceptance.md](checklists/visual-acceptance.md) — reuse of
  Specification 006's FR-by-FR pass against the hosted console, plus the
  deploy-only items (opens at a URL with nothing local running; sample-data
  notice; no secret in the bundle).
- [quickstart.md](quickstart.md) — local dev, deploy (root dir, env vars),
  pushing a fixture from `demo.py` or `tools/push_console.py`, and the FR →
  (endpoint test | Specification 006 visual-acceptance item | deploy check) map.

Post-design Constitution re-check: unchanged — no runtime call, no engine change,
the Console Fixture shape untouched, UI rendering explicitly untested per Article
VI, the build-step deviation contained to `web/`.
