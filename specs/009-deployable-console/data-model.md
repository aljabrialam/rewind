# Phase 1 Data Model: Deployable Console

The hosted console reads one endpoint and renders the **Specification 006 Console
Fixture** unchanged. This document is the transport shape (endpoint request /
response), the client-side types that mirror `console_fixture()` output, the
environment variables and which side each lives on, and the fallback state the
console tracks.

Nothing here extends the Console Fixture. For the fixture's own field
obligations see
[`specs/006-timeline-console/contracts/console-fixture.md`](../006-timeline-console/contracts/console-fixture.md).

---

## 1. ConsoleFixture  (client type — mirror of `console_fixture()` output)

```ts
type ConsoleFixture = {
  head: string;
  live_sandboxes: number;        // ≥ 0
  session_elapsed: number;       // ≥ 0, seconds
  runtime_version: string;
  verdict: Verdict | null;
  nodes: RailNode[];
};

type RailNode = {
  id: string; index: number; instruction: string;
  parent: string | null; children: string[];
  sandbox: string | null; state: string; snapshot: string | null;
  created_at: string;
  exit_code: number | null; stdout: string;
  outcome: string; terminal: string | null; rationale: string;
  branch?: boolean;                                  // Spec 006 enrichment
  progress?: { state: BranchState; elapsed_seconds: number };  // branch nodes only
};

type BranchState = "creating" | "running" | "done" | "failed";

type Verdict = { winner: number; reason: string; provider: string }
             | { reason: string; provider?: string; [k: string]: unknown };
```

A **branch node** is `node.branch === true`, or (fallback) a node whose `parent`
has more than one child — identical to Specification 006's rule.

---

## 2. Fixture endpoint  (`/api/fixture`)

One serverless function. Holds exactly one current fixture.

### GET /api/fixture

| | |
|---|---|
| Auth | none — the view is public (spec Out of Scope) |
| 200 body | the current `ConsoleFixture` as JSON |
| Source order | stored object → bundled `tree.json` (never 404 for a well-formed deploy) |
| Cache | `Cache-Control: no-store` — the console polls |

### POST /api/fixture

| | |
|---|---|
| Header | `x-rewind-token: <shared secret>` — compared to `REWIND_CONSOLE_TOKEN` server-side |
| Body | a `ConsoleFixture` JSON document |
| Max body | 512 KiB (NFR-009-04); larger → `413`, no state change |
| 200 | accepted; the posted document is now what GET returns |
| 401 | missing / wrong token; **no state change** (FR-009-05) |
| 422 | body is not a well-formed `ConsoleFixture`; **no state change** (FR-009-06) |
| 501 | server has no write store configured (`BLOB_READ_WRITE_TOKEN` unset) |
| 405 | any method other than GET / POST |

### Well-formed `ConsoleFixture` (the 422 gate)

Accept only if **all** hold:

1. body parses as a JSON object;
2. `head` is a string;
3. `nodes` is an array, every element an object with a string `id` and a number
   `index`;
4. if present, `live_sandboxes` and `session_elapsed` are numbers;
5. if present, `verdict` is `null` or an object.

Structural only and deliberately lenient — it rejects "not a run fixture", not
"imperfect fixture". Missing per-node fields (`stdout`, `rationale`, …) are
filled with defaults by the client renderer, matching Specification 006's
graceful degradation and the leaner shape `FAKE=1 demo.py` writes. The stored
bytes are never executed or evaluated (NFR-009-04).

---

## 3. Environment variables

| Name | Side | Purpose | In client bundle? |
|---|---|---|---|
| `REWIND_CONSOLE_TOKEN` | server (serverless fn) + push helper | the shared upload secret | **never** — not `VITE_`-prefixed (NFR-009-05) |
| `BLOB_READ_WRITE_TOKEN` | server (serverless fn) | credential for the single-object store | **never** |
| `REWIND_CONSOLE_ENDPOINT` | push helper only (`demo.py` / `tools/`) | full URL of the deployed `/api/fixture` | n/a — Python side |
| `VITE_POLL_MS` | client build (optional) | poll interval override; default 2000, clamped ≤ 2000 | yes — non-secret |

Vite only exposes `VITE_`-prefixed vars to client code. The two secrets are
deliberately un-prefixed so a build cannot leak them (SC-009-07).

---

## 4. Fallback state  (client — `useFixture`)

The hook tracks which source the on-screen fixture came from:

| `source` | Meaning | On-screen notice |
|---|---|---|
| `"live"` | last successful `GET /api/fixture` | none |
| `"shipped"` | endpoint failed; `GET /tree.json` (bundled) succeeded | "sample data — not a live push" |
| `"sample"` | both failed; in-code `SAMPLE` | "sample data — endpoint unreachable" |

Transitions on every poll. A failed or malformed poll **keeps the last good
fixture and its `source`** — a good view is never replaced by a broken one
(NFR-009-06, Edge Cases). `source` returns to `"live"` on the next good `GET`.

---

## 5. Action Request  (produced by the console — unchanged from Specification 006)

```jsonc
{ "kind": "restore" | "fan_out", "checkpoint_id": "<id>", "requested_at": "<ISO-8601>" }
```

Appended to an on-screen Requests list and `console.log`ged as JSON. **No network
call of any kind** (FR-009-08). Not persisted across reload.

---

## Type glossary

| Name | Definition |
|---|---|
| current fixture | the one `ConsoleFixture` the endpoint serves — the most recently accepted POST, or the bundled `tree.json` |
| shipped fixture | `web/public/tree.json`, a copy of the Specification 006 committed `fixtures/tree.json`, baked into the build |
| built-in sample | `web/src/sample.ts` — a minimal in-code `ConsoleFixture` for the endpoint-unreachable case |
| shared secret | `REWIND_CONSOLE_TOKEN` — carried in `x-rewind-token`, compared only server-side |
| runtime-issued value | came from the sandbox runtime or the reasoning agent → monospace (FR-009-10) |
| derived value | the console computed / counted / labelled it → interface face (FR-009-10) |
