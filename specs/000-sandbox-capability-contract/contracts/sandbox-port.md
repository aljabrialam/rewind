# Contract: Sandbox Port

The single interface every consumer uses to reach the sandbox runtime
(`src/rewind/ports.py` → `SandboxProvider`). Two implementations:
`DaytonaProvider` (live, sole SDK importer) and `FakeProvider` (offline). Both
MUST satisfy this contract for every declared operation, and both MUST reject
any operation not in `.rewind/capability-map.toml` identically.

Traces: FR-000-01, FR-000-01a, FR-000-01b, FR-000-02, FR-000-03, FR-000-04,
FR-000-05, FR-000-06, FR-000-08, FR-000-08a, FR-000-09, FR-000-11.

---

## Declared operations

| Operation | Signature | Required class | Observable post-condition the contract test MUST assert |
|---|---|---|---|
| `spawn` | `() -> Handle` | `container` | Returned `Handle.id` is non-empty; a trivial command (`echo ok`) run on it exits 0 **before** the handle is returned (FR-000-08a); auto-stop and auto-delete intervals are set on the sandbox (FR-000-08). |
| `run` | `(Handle, cmd: str) -> ExecResult` | `container` | `ExecResult.exit_code` reflects the real command status; `stdout` carries the real output; `elapsed` > 0. Working dir is `/home/daytona/work` (verified: `/work` not writable). |
| `checkpoint` | `(Handle) -> str` | `container` | Returns a non-empty snapshot name; a subsequent `branch` from that name yields children carrying the filesystem state as of the checkpoint. |
| `branch` | `(snapshot: str, n: int) -> list[Handle]` | `container` | Returns exactly `n` handles (n ≤ `max_branches` = 3); **each** child, on `run(child, "cat <file>")`, shows the parent's state written before the snapshot (FR-000-01a post-condition); writes in one child are not visible in another (independent state). |
| `destroy` | `(Handle) -> None` | `container` | After a confirmed return, the sandbox is no longer listed by the runtime; the ceiling permit is released. On failure: retried up to the bound, then an `UnconfirmedDestroyLeak` is recorded and a `terminal`-class error surfaced (FR-000-09). |

`fork` is **not** a declared operation: it returned HTTP 422 "not supported for
this sandbox" on the container class, so its post-condition was never asserted
(spec Assumptions, Constitution Article XIII).

---

## Cross-cutting obligations

| # | Obligation | Trace |
|---|---|---|
| C1 | Every call is wrapped in a timing record capturing `operation`, `outcome`, `elapsed_seconds`, and (on error) `error_class` (see `error-classification.md`), plus `waited_seconds` and `retries` where a bound applied. Records are retained for the session. | FR-000-07, NFR-000-05 |
| C2 | Before any operation runs, the port asserts the target `Handle.sandbox_class` matches the operation's `required_class`; on mismatch it raises **without** making a runtime call and names both classes. | FR-000-04 |
| C3 | Every sandbox created by `spawn` or `branch` gets an inactivity stop interval and a deletion interval attached at creation. | FR-000-08 |
| C4 | A created sandbox is not returned to the caller until it accepts a trivial command; the port blocks at most `READINESS_WAIT` (default 30s), then fails the creation and destroys the half-created sandbox. | FR-000-08a |
| C5 | Whatever the using operation does — return or raise — a `destroy` is attempted for every sandbox that came into existence, including when creation itself failed mid-way. If cleanup fails after the using op already raised, the original error is preserved and the cleanup failure is also surfaced. | FR-000-09 |
| C6 | `spawn` / `branch` acquire a ceiling permit before creating. If none is free within `SLOT_WAIT` (default 20s) the request fails `capacity` and siblings already created in the same fan-out are left running. `live_count` (leaks included) never exceeds `account_cpu_total`. | FR-000-11, clarification Q1 |
| C7 | Sandbox identifiers are passed verbatim. The port exposes no function that constructs, parses, mutates, or validates the *format* of an id. | FR-000-06 |
| C8 | The offline implementation produces, for each declared operation, an observable result equal to the recorded live result (`fixtures/daytona/*.json`), and rejects undeclared operations exactly as the live one does. | FR-000-05 |

---

## Import-time guard

At import of `rewind.ports`:

1. Load `.rewind/capability-map.toml` (missing/empty/unreadable → `CapabilityError`, message names the map).
2. For each entry: `name`, `required_class`, `post_condition` present; if `experimental` then `experimental_marker` present — else `CapabilityError("<name>: incomplete declaration")`.
3. `required_class` ∈ `classes` — else `CapabilityError`.
4. `PORT_OPERATIONS` (the tuple `ports.py` declares) ⊆ verified names — else `CapabilityError("<name> not in verified capability map")`.
5. No verified name is silently unused by the port is **not** an error (the map may be broader than the port), but it is logged.

Failure raises before any consumer `main()` executes (FR-000-03, NFR-000-01).
