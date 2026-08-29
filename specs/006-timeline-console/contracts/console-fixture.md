# Contract: Console Fixture

`Engine.console_fixture(engine, *, verdict=None) -> dict` — a pure function over
engine state (no runtime call). Written by `demo.py` to `fixtures/tree.json`. The
console reads this and nothing else (NFR-006-01).

Traces: FR-006-01 … FR-006-08, NFR-006-01, NFR-006-02.

---

## Output shape

```jsonc
{
  "head": "<checkpoint id>",
  "live_sandboxes": 3,
  "session_elapsed": 41.2,
  "runtime_version": "v0.207.0",
  "verdict": { "winner": 0, "reason": "branch 0 exited 0 fastest",
               "provider": "deterministic-fallback" } | null,
  "nodes": [
    {
      // Spec 001 as_tree node — unchanged
      "id", "index", "instruction", "parent", "children",
      "sandbox", "state", "snapshot", "created_at",
      "exit_code", "stdout", "outcome", "terminal", "rationale",

      // Spec 006 enrichment — present ONLY on branch nodes
      "progress": { "state": "running", "elapsed_seconds": 6.1 }
    }
  ]
}
```

---

## Field obligations

| # | Obligation | Trace |
|---|---|---|
| C1 | `head` and every `nodes[]` field of the Spec 001 `as_tree` form are passed through unchanged. | FR-006-01, FR-006-06, FR-006-08 |
| C2 | `live_sandboxes` = the count of sandboxes the provider currently holds live (`len(engine.p.live)`), not a node count. | FR-006-07 |
| C3 | `session_elapsed` = seconds since the `Engine` was constructed (`engine._t0`), monotonic, ≥ 0. | FR-006-07 |
| C4 | `runtime_version` = `capabilities.RUNTIME_VERSION`. | footer chip |
| C5 | `verdict` is the caller's `rank_by_evidence(...)` dict verbatim, or `null` when no ranking has run. | Verdict Block, Article X |
| C6 | A **branch node** (its `parent` has > 1 child) carries `progress` = `{state, elapsed_seconds}`; `state ∈ {creating, running, done, failed}` from Spec 004; `elapsed_seconds` ≥ 0. | FR-006-05 |
| C7 | A **non-branch node** has no `progress` key. | FR-006-05 |
| C8 | The function makes no network call and no `provider` lifecycle call — it only reads state. | NFR-006-01 |
| C9 | Output is JSON-serialisable with the standard library (no custom encoder). | NFR-006-04 |
| C10 | Re-calling it after the run advances reflects the new state (so the console's poll shows progress). | NFR-006-02 |

---

## Console read obligations (what the page depends on)

| The console MUST read | To satisfy |
|---|---|
| `head` | FR-006-01 head marker |
| `nodes[]` in array order, excluding branch nodes, for the rail | FR-006-01 |
| branch nodes (parent has > 1 child) for the lanes, captioned by `parent` | FR-006-02 |
| `nodes[i].sandbox`, `nodes[i].progress.state`, `nodes[i].progress.elapsed_seconds` per lane | FR-006-05 |
| `nodes[i].exit_code`, `nodes[i].stdout` for the selected node | FR-006-06 |
| `nodes[i].rationale` — render the labelled area only when truthy | FR-006-08 |
| `live_sandboxes`, `session_elapsed` — always in the footer | FR-006-07 |
| `verdict.reason`, `verdict.provider` when `verdict` is non-null | Verdict Block |
| `runtime_version` for the footer chip (mono) | FR-006-09 |

If `fixtures/tree.json` is unreachable, the console uses its built-in `SAMPLE`
and states it is a sample (NFR-006-01, SC-009). A malformed/partial fetch is
ignored in favour of the last good state (Edge Cases — never half-and-half).

---

## Action Request intent (produced by the console)

```jsonc
{ "kind": "restore" | "fan_out", "checkpoint_id": "<id>", "requested_at": "<ISO-8601>" }
```

| # | Obligation | Trace |
|---|---|---|
| A1 | Available only when a checkpoint is selected; disabled/inert otherwise. | FR-006-03/04, SC-004 |
| A2 | Firing appends the intent to an on-screen Requests list and `console.log`s it as JSON. | FR-006-03/04 |
| A3 | The console makes **no** `fetch`/XHR/WebSocket to any runtime as part of this. | NFR-006-01, SC-004 |
| A4 | Not persisted across a page reload. | Out of Scope |
