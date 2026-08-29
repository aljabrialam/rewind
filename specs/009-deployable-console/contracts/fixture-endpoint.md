# Contract: Fixture Endpoint

`web/api/fixture.ts` — one serverless function, one current fixture. The hosted
console reads it and nothing else (FR-009-08). The demonstration's push helper
writes it. It makes **no** sandbox-runtime or engine call.

Traces: FR-009-03 … FR-009-09, NFR-009-04, NFR-009-05, NFR-009-06.

---

## GET /api/fixture

Returns the current console fixture.

| # | Obligation | Trace |
|---|---|---|
| G1 | Responds `200` with a JSON body that is a well-formed `ConsoleFixture` (Specification 006 shape). | FR-009-01, FR-009-03 |
| G2 | Source order: the stored object if one exists, else the fixture bundled with the deployment (`tree.json`). A well-formed deploy never 404s this route. | FR-009-07 |
| G3 | `Cache-Control: no-store` — the console polls and must see the latest accepted fixture. | FR-009-03, NFR-009-06 |
| G4 | Never executes or evaluates the stored bytes — reads and returns them as data. | NFR-009-04 |
| G5 | No authentication — the view is public once deployed. | spec Out of Scope |

---

## POST /api/fixture

Replaces the current fixture. Authenticated, shape-checked, size-capped.

| # | Obligation | Trace |
|---|---|---|
| P1 | Requires `x-rewind-token` equal to `REWIND_CONSOLE_TOKEN` (constant-time compare). Missing or wrong → `401`, **no state change**. | FR-009-05 |
| P2 | Body over 512 KiB → `413` before parsing, **no state change**. | NFR-009-04 |
| P3 | Body that is not a well-formed `ConsoleFixture` (see rules below) → `422`, **no state change**. | FR-009-06 |
| P4 | Valid token + valid shape + within size → store the document verbatim; subsequent `GET` returns it. Respond `200`. | FR-009-04 |
| P5 | No write store configured (`BLOB_READ_WRITE_TOKEN` unset) → `501`; the deployment still serves the bundled fixture on `GET`. | FR-009-07 |
| P6 | The stored document is never executed or evaluated — persisted and served as data only. | NFR-009-04 |
| P7 | `REWIND_CONSOLE_TOKEN` and any store credential are read only server-side and are absent from the client bundle. | NFR-009-05, SC-009-07 |

### Well-formed `ConsoleFixture` (the P3 gate)

Reject with `422` unless **all** hold:

1. the body parses as a JSON **object**;
2. `head` is a string;
3. `nodes` is an array, and every element is an object with a string `id` and a
   number `index`;
4. if present, `live_sandboxes` and `session_elapsed` are numbers;
5. if present, `verdict` is `null` or an object.

Structural only, and deliberately lenient — it rejects "this is not a run
fixture", not "this fixture is imperfect". A body that passes but is semantically
odd (e.g. `head` names no node, a node is missing `stdout`) is still accepted;
the console fills defaults and degrades gracefully, as in Specification 006's
Edge Cases. This matches what `console_fixture()` actually emits today, including
the leaner shape written by `FAKE=1 demo.py`.

---

## Other methods

| # | Obligation | Trace |
|---|---|---|
| M1 | Any method other than `GET` or `POST` → `405` with an `Allow: GET, POST` header. | — |

---

## Console read obligations (what the hosted page depends on)

| The console MUST | To satisfy |
|---|---|
| resolve the endpoint **relative to its own location** (`fetch("api/fixture")` / `fetch("/api/fixture")`), never an absolute host | Edge Cases (sub-path deploys) |
| poll `GET /api/fixture` on an interval ≤ 2s | FR-009-03, NFR-009-06 |
| on a failed or non-2xx `GET`, fall back to bundled `GET /tree.json`, then to the in-code `SAMPLE` | FR-009-07 |
| on a `GET` whose body fails the client shape check, **keep the last good fixture** | NFR-009-06, Edge Cases |
| show an on-screen notice whenever the rendered fixture came from the bundled file or the sample, not a live `GET` | FR-009-07, SC-009-06 |
| make **no** other network call — no runtime, no engine, no websocket | FR-009-08 |

---

## Push helper obligations (`demo.py` hook / `tools/push_console.py`)

```
POST {REWIND_CONSOLE_ENDPOINT}   x-rewind-token: {REWIND_CONSOLE_TOKEN}
body: the current fixtures/tree.json
```

| # | Obligation | Trace |
|---|---|---|
| H1 | Runs only when both `REWIND_CONSOLE_ENDPOINT` and `REWIND_CONSOLE_TOKEN` are set. | FR-009-09 |
| H2 | Wrapped so any failure (network, non-2xx, timeout) prints one line and is otherwise ignored — the local run and local console are unaffected. | FR-009-09, SC-009-05 |
| H3 | Sends the file bytes as-is; performs no transformation of the fixture. | dependency on Specification 006 shape |
| H4 | Uses only the Python standard library (`urllib`) — no new dependency. | plan Technical Context |
