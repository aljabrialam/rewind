# Phase 1 Data Model: Sandbox Capability Contract

Concrete record shapes for the nine entities in `spec.md` → Key Entities. These
are contract shapes, not implementation classes — field names are indicative,
types are the constraint. Existing shapes in `src/rewind/ports.py` (`Handle`,
`ExecResult`, `Checkpoint`) are reused where noted.

---

## 1. Verified Capability Map

The authoritative machine-readable declaration. One file, generated from a live
run, never hand-edited.

| Field | Type | Rule |
|---|---|---|
| `runtime_version` | string | The SDK / API version observed during generation (e.g. `v0.207.0`). Contract test fails if the live version differs. |
| `generated_at` | ISO-8601 timestamp | When the live run produced this map. |
| `account_cpu_total` | int > 0 | Verified account quota; becomes the Concurrency Ceiling. |
| `max_branches` | int > 0, ≤ `account_cpu_total` | Working ceiling for one fan-out (verified: 3). |
| `operations` | list of Capability Declaration (≥ 1) | Every operation the port may invoke. |
| `classes` | set of SandboxClass | Every class named by any operation must appear here. |

**Validation**: file present, parseable, `operations` non-empty, every operation
complete (see below). Any failure → `CapabilityError` at import time
(FR-000-03, NFR-000-01). Missing / empty / unreadable file → import failure whose
message points at the map, not the caller (Edge Cases).

---

## 2. Capability Declaration (one `operations[]` entry)

| Field | Type | Rule |
|---|---|---|
| `name` | string, non-empty | The exact runtime operation name. Verbatim; the guard compares by equality. |
| `required_class` | SandboxClass | Must be one of `classes`. Absent → incomplete → rejected at import. |
| `post_condition` | string, non-empty | Human-readable description of the observable effect the live run asserted (FR-000-01a). Absent → incomplete → rejected. |
| `experimental` | bool | `true` if the runtime flags this name experimental. |
| `experimental_marker` | string, required iff `experimental = true` | The runtime's own stability tag for the name. Missing when `experimental = true` → incomplete → rejected (FR-000-01b). |

**Verified set at generation time** (from `.rewind/daytona-capability-map.md`):
`spawn`, `run`, `checkpoint`, `branch`, `destroy`. `fork` is **absent** — it
returned 422 on the container class and its post-condition was never asserted.

---

## 3. Sandbox Port

Not a data record — the single interface. Existing `SandboxProvider` Protocol in
`ports.py`. Two implementations only: live (`DaytonaProvider`) and offline
(`FakeProvider`). Constraint: exactly the operations in the capability map are
exposed; the offline implementation rejects undeclared operations identically
(spec Edge Cases, FR-000-05).

Declared operations and signatures (unchanged from `ports.py`):

| Operation | Signature | Required class |
|---|---|---|
| `spawn` | `() -> Handle` | container |
| `run` | `(Handle, cmd: str) -> ExecResult` | container |
| `checkpoint` | `(Handle) -> str` (snapshot name) | container |
| `branch` | `(snapshot: str, n: int) -> list[Handle]` | container |
| `destroy` | `(Handle) -> None` | container |

---

## 4. Sandbox Identifier

Reuses `Handle.id: str` from `ports.py`.

| Field | Type | Rule |
|---|---|---|
| `id` | string, opaque | Byte-for-byte as issued by the runtime. No parsing, no formatting, no construction. The system exposes no function that takes an id apart or builds one (FR-000-06). |
| `parent_id` | string \| None | Present only when set by the runtime for a child; never derived from `id` string math. |
| `snapshot` | string \| None | The checkpoint name a branch was created from; issued by the runtime. |
| `sandbox_class` | SandboxClass | Recorded at creation so `assert_class` can run before each call. |

**Transitions**: none — an identifier is immutable from issue to use.

---

## 5. Call Record

One entry per runtime call. Extends the existing `DaytonaProvider.calls`
list-of-tuples into a structured record.

| Field | Type | Rule |
|---|---|---|
| `operation` | string | The declared operation name. |
| `outcome` | `"ok"` \| `"error"` | Terminal state of the call. |
| `elapsed_seconds` | float ≥ 0 | Wall-clock duration. |
| `error_class` | ErrorClass \| None | Set iff `outcome = "error"` (FR-000-10). |
| `waited_seconds` | float ≥ 0 | Time spent in a bounded wait (readiness or ceiling slot), 0 if none (NFR-000-05). |
| `retries` | int ≥ 0 | Bounded-retry attempts consumed (destroy path), 0 if none (NFR-000-05). |

**Retention**: kept in memory for the life of the session so records can be
inspected after a failure (FR-000-07). Not persisted by this feature.

---

## 6. Error Classification

Enum, exactly one value per failed call.

| Value | Meaning | Caller expectation |
|---|---|---|
| `retryable` | Transient; the same call may succeed immediately | Retry with backoff |
| `capacity` | Account/quota/concurrency limit, or an undecidable capacity-or-terminal failure | Back off; may not clear this session |
| `terminal` | Cannot succeed on retry (bad request, unsupported, auth) | Do not retry; surface |

Decision table: [contracts/error-classification.md](contracts/error-classification.md).
Rule: account-quota and transient-capacity both → `capacity`; ambiguous
capacity-or-terminal → `capacity` (FR-000-10).

---

## 7. Concurrency Ceiling

| Field | Type | Rule |
|---|---|---|
| `limit` | int > 0 | From `capability_map.account_cpu_total` (10). Not configurable below the verified value; may be lowered by env for a constrained venue but never raised past the map. |
| `live_count` | int ≥ 0 | Sandboxes currently counted alive, **including** unconfirmed-destroy leaks. |
| `slot_wait_seconds` | float > 0 | Bounded wait for a slot (default 20s, R5). |

**Invariant**: `live_count` never exceeds `limit`. A creation that would breach
it blocks up to `slot_wait_seconds`, then fails `capacity`, leaving siblings
untouched (FR-000-11, clarification Q1).

---

## 8. Sandbox Lifecycle

State of a created sandbox. Extends `Checkpoint.state` in `ports.py`
(`live | released | unreachable`).

| State | Entry condition | Exit |
|---|---|---|
| `creating` | `spawn` / `branch` call issued | → `ready` on command-readiness confirmed; → `failed` on readiness wait elapsed |
| `ready` | Accepted a trivial command within the readiness wait; auto-stop + auto-delete intervals attached (FR-000-08, FR-000-08a) | → `released` on successful destroy; → `leaked` on destroy unconfirmed after retries |
| `failed` | Never became command-ready | Half-created sandbox destroyed; not handed to caller |
| `released` | `destroy` confirmed | Permit returned to the ceiling |
| `leaked` | `destroy` unconfirmed after bounded retries | Recorded as Unconfirmed-destroy Leak; still counts against ceiling |

**Guarantee**: a sandbox is never handed to a caller before `ready`
(FR-000-08a); every sandbox that reached existence has a `destroy` attempted on
both the success and the raise path (FR-000-09).

---

## 9. Unconfirmed-destroy Leak

| Field | Type | Rule |
|---|---|---|
| `sandbox_id` | string | The runtime identifier, verbatim. |
| `first_seen` | ISO-8601 timestamp | When the destroy retries were exhausted. |
| `retries_attempted` | int | Bounded count consumed (default 3, R5). |
| `still_counts` | bool, always `true` while unresolved | Keeps a ceiling permit held (FR-000-09). |

**Transitions**: `leaked` → cleared only when a later sweep confirms the runtime
no longer lists the sandbox. The sweep's schedule is out of scope (spec
Assumptions); this feature records the leak and defines the clear condition.

---

## Type glossary

| Name | Definition |
|---|---|
| `SandboxClass` | `Literal["container", "vm"]` — only classes present in the capability map |
| `ErrorClass` | `Literal["retryable", "capacity", "terminal"]` |
| `Handle` | Existing `ports.Handle` — `id`, `parent_id`, `snapshot` (+ `sandbox_class`) |
| `ExecResult` | Existing `ports.ExecResult` — `exit_code`, `stdout`, `elapsed`, `.ok` |
