# Phase 1 Data Model: Timeline Console

The console reads one file. This document is its shape. All of it is produced by
`Engine.console_fixture(...)` (new, pure) and written by `demo.py` to
`fixtures/tree.json`. The `ActionRequest` is produced by the console itself.

---

## 1. Console Fixture  (`fixtures/tree.json`)

`Engine.console_fixture(engine, *, verdict=None) -> dict` = `engine.run.as_tree()`
(Spec 001) plus the operational fields below.

| Field | Type | Source | Feeds |
|---|---|---|---|
| `head` | string | Spec 001 `as_tree` | FR-006-01 head marker |
| `nodes` | list[Node] | Spec 001 `as_tree`, enriched (below) | FR-006-01/02/06/08 |
| `live_sandboxes` | int ≥ 0 | `len(engine.p.live)` else `len(engine.live)` | FR-006-07 |
| `session_elapsed` | float ≥ 0 | seconds since `Engine.__init__` (`engine._t0`) | FR-006-07 |
| `runtime_version` | string | `capabilities.RUNTIME_VERSION` | footer chip (runtime-issued → mono) |
| `verdict` | Verdict \| null | the `rank_by_evidence(...)` dict the caller passes, or `null` | Verdict Block |

### Node  (one per checkpoint — Spec 001 `as_tree` node, unchanged fields)

`id`, `index`, `instruction`, `parent`, `children`, `sandbox`, `state`,
`snapshot`, `created_at`, `exit_code`, `stdout`, `outcome`, `terminal`,
`rationale`.

**Enrichment** — branch nodes only (a node whose parent has more than one child):

| Added | Type | Source | Feeds |
|---|---|---|---|
| `progress` | `{state, elapsed_seconds}` \| absent | merged from `engine._fan_progress` by `checkpoint_id` | FR-006-05 lane |
| `progress.state` | `"creating"` \| `"running"` \| `"done"` \| `"failed"` | Spec 004 `BranchProgress.state` | lane running-state word |
| `progress.elapsed_seconds` | float ≥ 0 | branch `evidence.elapsed` (or measured) | lane elapsed |

Non-branch nodes have no `progress` key.

### Verdict

| Field | Type | Source |
|---|---|---|
| `winner` | int | `rank_by_evidence` — index of the promoted branch |
| `reason` | string | `rank_by_evidence` — one line |
| `provider` | string | `rank_by_evidence` — `"deterministic-fallback"` or the critic id |

---

## 2. Rail Checkpoint  (rendered, derived from a Node)

| Shown | From | Face |
|---|---|---|
| status dot (ok / fail / head-ring) | `exit_code`, `id === head` | — |
| executed instruction (truncated, ellipsis) | `instruction` | **mono** (runtime-issued) |
| `#index · id · sandbox` | `index`, `id`, `sandbox` | index/`#` label = face; `id`, `sandbox` = **mono** |
| `exit N` on failure | `exit_code` | **mono** |

Order = `nodes` order, minus branch nodes (those go to lanes). FR-006-01.

---

## 3. Branch Lane  (rendered, from a branch Node)

| Shown | From | Face |
|---|---|---|
| `Branch i` heading + parent caption (`from <parent-id>`) | position, `parent` | "Branch"/"from" = face; `<parent-id>` = **mono** |
| state word: creating / running / done / failed | `progress.state` (fallback: `terminal`/`state`) | face |
| lane inset colour: running (`branch`) / promoted (`won`, `id === head`) / released (`killed`, `state === "released"`) | Design Reference | — |
| sandbox id | `sandbox` | **mono** |
| elapsed | `progress.elapsed_seconds` | number = face, unit `s` = face |
| `exit N` | `exit_code` | **mono** |
| strategy (truncated) | `instruction` | **mono** |

FR-006-02, FR-006-05.

---

## 4. Evidence Panel  (rendered, for the selected Node)

| Shown | From | Face |
|---|---|---|
| `exit code N` (green ok / red fail) | `exit_code` | label = face, `N` = **mono** |
| output (`<pre>`, scrolls, bounded height) | `stdout` (or "(no output)") | **mono** |
| rationale area — only if `rationale` present | `rationale` | face, prefixed "agent rationale — not evidence:", italic/muted, separate element |

FR-006-06, FR-006-08. Absent rationale → area not rendered (SC-003).

---

## 5. Session Counters  (rendered, persistent footer)

| Shown | From | Face |
|---|---|---|
| live sandboxes | `live_sandboxes` | count = **face** (derived) |
| checkpoints | `nodes.length` | **face** |
| branches | count of branch nodes | **face** |
| elapsed | `session_elapsed` | **face** |
| `daytona <runtime_version>` | `runtime_version` | version = **mono** (runtime-issued) |

Always visible (`position: fixed`). FR-006-07, SC-006. The footer's numeric
counters drop their current `.mono` class (they are derived — FR-006-09).

---

## 6. Action Request  (produced by the console, not the fixture)

Triggered from the selected checkpoint's controls.

| Field | Type | Rule |
|---|---|---|
| `kind` | `"restore"` \| `"fan_out"` | which button |
| `checkpoint_id` | string | the selected checkpoint's id (runtime-issued) |
| `requested_at` | ISO-8601 string | when the button fired |

Effect: appended to an on-screen **Requests** list and `console.log`ged as JSON.
**No `fetch` to any runtime** (NFR-006-01, FR-006-03/04). Not persisted across
reload (Out of Scope).

---

## Type glossary

| Name | Definition |
|---|---|
| branch node | a `nodes[i]` whose `parent` has more than one child |
| runtime-issued value | came from the sandbox runtime or the reasoning agent → monospace |
| derived value | the console computed/counted/labelled it → interface face |
| `Engine.console_fixture` | new pure function: `as_tree()` + `live_sandboxes` + `session_elapsed` + `runtime_version` + `verdict` + branch `progress` |
