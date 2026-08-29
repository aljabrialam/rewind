# Phase 0 Research: Deployable Console

Spec 009 carries no `[NEEDS CLARIFICATION]`. Decisions for design. Evidence:
`ui/console.html` (228 lines, single file — the Specification 006 console),
`demo.py` (writes `console_fixture(e, verdict=verdict)` to `fixtures/tree.json`),
`src/rewind/engine.py` (`console_fixture`, unchanged here), Constitution Articles
I, II, IV, VI ("UI rendering … is not tested"), VIII (additive-integration stop
line), XI, XIII.

---

## R1. Why a component framework + build, and why that forces a new spec

**Decision**: build the hosted console as a React + TypeScript app under `web/`,
compiled by Vite. Do **not** extend `ui/console.html`.

**Rationale**:
- Specification 006 NFR-006-04 is explicit: `ui/console.html` is *"a single
  self-contained page — no build step"*. A public URL for viewers who run nothing
  locally needs a hosted build and a data endpoint — the opposite constraint.
  Amending Specification 006 would contradict its own signed-off NFR, so this is
  a separate feature (009) that carries Specification 006's view forward under a
  different deployment constraint (NFR-009-01).
- Components (`Rail`, `BranchLanes`, `EvidencePanel`, `Footer`, `VerdictCard`,
  `RequestsList`) plus a `types.ts` mirror of `console_fixture()` output make the
  Specification 006 regions individually legible and the fixture shape explicit
  at the type level.
- Vite + React is the deploy target's default preset — zero custom build config,
  static output plus a serverless `api/` directory.

**Alternatives considered**:
- *Port `console.html` verbatim and host the file* — rejected: it polls a
  relative `../fixtures/tree.json` that does not exist on a host, and offers no
  way for `demo.py` to update a deployed view.
- *Next.js* — rejected: server rendering buys nothing here (the payload is one
  JSON blob) and adds framework surface; a static SPA + one function is smaller.
- *Amend Specification 006* — rejected, see above (contradicts NFR-006-04).

---

## R2. The data source — one endpoint, one object

**Decision**: a single serverless function `web/api/fixture.ts`. `GET` returns
the current fixture; `POST` (shared-secret + shape + size checked) replaces it.
Behind it: one object in the deploy target's blob store, keyed by a fixed name,
with a filesystem fallback to the bundled `web/public/tree.json`.

**Rationale**:
- The console reads one thing (parity with Specification 006 NFR-006-01). One
  endpoint returning one `ConsoleFixture` keeps that.
- No database: the endpoint holds exactly the current run's fixture — no history,
  no versions, no concurrent runs (spec Out of Scope). A single named object is
  the whole storage need.
- The filesystem fallback means the deployment renders even with no blob store
  configured — `GET` serves the bundled fixture, `POST` returns `501`
  (FR-009-07, contract P5).

**Alternatives considered**:
- *Commit the fixture and redeploy to update it* — rejected: a redeploy per demo
  beat is not "updates within one refresh interval" (FR-009-03 / SC-009-03).
- *A KV/database row* — rejected: more setup and credentials for a single blob.
- *Client uploads straight to blob storage* — rejected: that needs a storage
  credential in the browser (violates NFR-009-05).

---

## R3. The upload auth model

**Decision**: `POST` requires an `x-rewind-token` header equal to the server-side
`REWIND_CONSOLE_TOKEN` (constant-time compare). No token / wrong token → `401`,
no state change. The token is **never** `VITE_`-prefixed, so Vite cannot place it
in the client bundle.

**Rationale**: the endpoint is public and one bad `POST` could blank the view
mid-demonstration (User Story 3). This is upload protection for a demo surface,
not user identity — a shared secret held by the presenter's machine is the right
weight. `constant-time` compare avoids a timing oracle for near-zero cost.

**Alternatives considered**:
- *No auth, rely on obscurity* — rejected: FR-009-05 exists precisely against
  this.
- *Signed requests / JWT* — rejected: overbuilt for one presenter pushing one
  file.

---

## R4. The fallback chain (FR-009-07, NFR-009-06)

**Decision**: `useFixture` polls in this order and tracks the source —

1. `GET /api/fixture` → `source = "live"`.
2. on failure / non-2xx → `GET /tree.json` (bundled) → `source = "shipped"`.
3. on failure → in-code `SAMPLE` → `source = "sample"`.

A poll that fails or returns a body failing the client shape check **keeps the
last good fixture and its source** — a good view is never replaced by a broken
one. The console shows an on-screen notice whenever `source !== "live"`.

**Rationale**: mirrors Specification 006's `SAMPLE` fallback and "never
half-and-half" Edge Case, extended for the two-hop hosted case. The visible
notice is Article XIII — a hosted URL must not present stale sample data as a
live run.

---

## R5. The `demo.py` push kept best-effort and env-gated (FR-009-09)

**Decision**: `tools/push_console.py` POSTs `fixtures/tree.json` to
`REWIND_CONSOLE_ENDPOINT` with `REWIND_CONSOLE_TOKEN`, using only `urllib`. At
the end of `demo.py`, after `fixtures/tree.json` is written, a `try/except` block
calls it **only when both env vars are set**; any failure prints one line and is
ignored.

**Rationale**: Article XI — the live demo runs locally and must be unaffected by
a hosting concern. Article VIII — an additive surface carries a stop line and may
not sit on the critical path. Gating on env vars means the default `demo.py` run
is byte-for-byte the Specification 006 behaviour; the push is opt-in.

**Alternatives considered**:
- *Always push* — rejected: couples the local run to network availability.
- *A `requests` dependency* — rejected: `urllib` covers a one-shot POST; no new
  dependency (Article VI seam discipline — keep the offline path clean).

---

## R6. Why the automated tests are the endpoint logic + the fixture shape

**Decision**: Constitution Article VI, "What is not tested": *UI rendering … is
not tested.* So **no** headless-browser or DOM tests for the hosted console. The
automated tests are:

- `web/api/__tests__/fixture.test.ts` — pure-logic over the handler: valid
  upload accepted; missing / wrong token → `401` with no state change; malformed
  body → `422` with no state change; oversize body → `413`; `GET` with an empty
  store returns the bundled fixture; method other than GET/POST → `405`.
- the existing `tests/unit/test_console_fixture.py` (Specification 006) is the
  contract the pushed payload must satisfy — reused, not duplicated.

The Specification 006 run view on the hosted console is signed off with
Specification 006's `checklists/visual-acceptance.md` plus the three deploy-only
items in this feature's checklist, run at build and before the demo.

---

## R7. Secret hygiene in the build (NFR-009-05, SC-009-07)

**Decision**: only `VITE_`-prefixed env vars reach client code; the two secrets
(`REWIND_CONSOLE_TOKEN`, `BLOB_READ_WRITE_TOKEN`) are un-prefixed and read only
inside `web/api/`. A build-output grep for the token value is part of the
visual-acceptance pass.

---

## Open items carried to Phase 1

- The transport shapes + client types + env-var table → [data-model.md](data-model.md)
- `GET` / `POST` obligations + the 422 shape gate + fallback order → [contracts/fixture-endpoint.md](contracts/fixture-endpoint.md)
- The reused Specification 006 FR pass + the deploy-only items → [checklists/visual-acceptance.md](checklists/visual-acceptance.md)
