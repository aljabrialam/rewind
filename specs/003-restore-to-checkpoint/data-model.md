# Phase 1 Data Model: Restore to Checkpoint

Concrete shapes for `spec.md` → Key Entities. All new members live in
`src/rewind/engine.py`. Existing `Run` / `Checkpoint` (Spec 001) and the port
(Spec 000) are reused unchanged.

---

## 1. RestoreCheck  *(input, optional)*

What the caller wants verified in the restored sandbox.

| Field | Type | Rule |
|---|---|---|
| `before` | list[tuple[str, str]] | `(command, marker)` pairs. Each `command`, run in the restored sandbox, MUST have `marker` present in its output for the check to pass. May be empty. |
| `after` | list[tuple[str, str]] | `(command, marker)` pairs. Each `command` MUST have `marker` **absent** for the check to pass. May be empty. |

`None` (no `RestoreCheck` at all) ⇒ verification `status = "not-checked"`.

---

## 2. RestoreVerification  *(output, always present)*

Structured so a viewer can render it (NFR-003-01).

| Field | Type | Rule |
|---|---|---|
| `status` | `"verified"` \| `"not-verified"` \| `"not-checked"` | `not-checked` when no checks supplied; `verified` only when there is ≥1 `before` **and** ≥1 `after` and every check passed; `not-verified` otherwise (FR-003-02, SC-009). |
| `before` | list[dict] | one per `before` check: `{command, marker, observed, passed}` |
| `after` | list[dict] | one per `after` check: `{command, marker, observed, passed}` |

`observed` is the (possibly truncated) command output the check saw.

---

## 3. RestoreResult  *(output of every restore attempt)*

| Field | Type | Rule |
|---|---|---|
| `checkpoint_id` | string | The target checkpoint id, echoed back. |
| `sandbox_id` | string \| None | The restored sandbox id on success; `None` on any refusal or failure. |
| `elapsed_seconds` | float ≥ 0 | Wall-clock around the whole attempt (produce + verify). Always present (FR-003-06, SC-005). |
| `verification` | RestoreVerification | Always present; `not-checked` on refusal/failure. |
| `error` | string \| None | `None` on success; otherwise `"unknown"` \| `"released"` \| `"unreachable"` \| a classified runtime message (FR-003-05, R5). |
| `head_moved` | bool | `True` iff the run head was moved to `checkpoint_id`. |

`as_dict()` — a plain-dict form of the whole result for the console / fixtures.

---

## 4. Restore state machine (one attempt)

| State | Entry | Exit |
|---|---|---|
| `checking` | `restore(id, verify)` called | → `refused` if id unknown, or checkpoint `state != "live"`, or `snapshot is None`; → `producing` otherwise |
| `producing` | target is restorable | → `failed` if `provider.branch(snapshot, 1)` raises (partial sandbox already destroyed by the port); → `verifying` on a sandbox |
| `verifying` | restored sandbox in hand | runs `RestoreCheck` probes via `provider.run`; always → `committing` (a failed check does not abort — it is reported) |
| `committing` | verification done | `set_head(id)`; `self.live[id] = new_handle`; release the old head's sandbox if unreferenced → `done` |
| `refused` / `failed` | — | head unchanged; no sandbox registered; `RestoreResult` carries `error` + `elapsed_seconds` |
| `done` | — | `RestoreResult` with `sandbox_id`, `head_moved = True`, `verification` |

---

## 5. Effect on the run tree (Spec 001)

| Thing | Effect of a successful restore |
|---|---|
| `run.order` | unchanged (nothing added or removed) |
| `run.checkpoints` | unchanged except `run.head` |
| `run.head` | now `checkpoint_id` |
| later checkpoints' `snapshot` / `state` / `instruction` | untouched (FR-003-04) — they stay restorable from their own snapshots |
| `run.check_integrity()` | still `[]` (SC-003) |
| `self.live` | `old_head` entry removed; `checkpoint_id` entry now the fresh handle; net size change ≤ 0 for the map, live sandbox count +1 at most (SC-006) |

---

## Type glossary

| Name | Definition |
|---|---|
| `RestoreCheck` | frozen dataclass `{before: list[(str,str)], after: list[(str,str)]}` |
| `RestoreVerification` | dataclass `{status, before: list[dict], after: list[dict]}` |
| `RestoreResult` | dataclass `{checkpoint_id, sandbox_id, elapsed_seconds, verification, error, head_moved}` + `as_dict()` |
| restorable | `Run.is_restorable(id)` from Spec 001 — `state == "live" and snapshot is not None` |
