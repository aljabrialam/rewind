# Contract: Error Classification

Every failed runtime call is labelled with exactly one `ErrorClass`. The label
is attached to the raised error and to the Call Record, and is exposed to the
caller through the port.

Traces: FR-000-10, FR-000-07, clarification Q (capacity-vs-quota,
2026-08-29), User Story 4.

---

## Values

| Value | Definition | Caller expectation |
|---|---|---|
| `retryable` | Transient condition; the identical call may succeed if repeated shortly. | Retry with backoff. |
| `capacity` | An account / quota / concurrency / CPU limit — **or** a failure that cannot be told apart between capacity and terminal. | Back off; the condition may not clear within this session. Not a bug. |
| `terminal` | The call cannot succeed on retry: malformed request, unsupported operation or class, authentication/authorization failure. | Do not retry; surface the failure. |

Exactly one value per failed call (FR-000-10). There is no separate `quota`
class — account-quota failures classify as `capacity`.

---

## Decision table

Evaluated top to bottom; first match wins.

| # | Signal (SDK exception type / HTTP status / message substring, case-insensitive) | Class |
|---|---|---|
| 1 | Local timeout, connection reset/refused, DNS failure, `RemoteDisconnected` | `retryable` |
| 2 | HTTP `502`, `503`, `504` | `retryable` |
| 3 | Message contains `not ready`, `still starting`, `initializing`, `warming up` | `retryable` |
| 4 | HTTP `429`; message contains `rate limit` **and not** `quota` | `retryable` |
| 5 | HTTP `402`; message contains `quota`, `concurrenc`, `cpu limit`, `capacity`, `no capacity`, `insufficient resources`, `too many sandboxes` | `capacity` |
| 6 | HTTP `401`, `403`; message contains `unauthorized`, `forbidden`, `invalid api key`, `expired` | `terminal` |
| 7 | HTTP `400`, `404`, `409`, `422`; message contains `not supported`, `unknown`, `invalid`, `no such` | `terminal` |
| 8 | Any other `4xx` | `terminal` |
| 9 | Any other `5xx` | `retryable` |
| 10 | Unrecognized / ambiguous — cannot decide between capacity and terminal | `capacity` (FR-000-10 default) |

---

## Special cases

| Situation | Class | Note |
|---|---|---|
| Ceiling-slot wait elapsed (local, no runtime call made) | `capacity` | Raised by C6 in `sandbox-port.md`; siblings untouched. |
| Command-readiness wait elapsed | `retryable` at the operation boundary, but the creation is failed and the half-created sandbox destroyed (FR-000-08a) — the caller sees a creation failure, not a usable sandbox. |
| `destroy` unconfirmed after bounded retries | `terminal` | Plus an `UnconfirmedDestroyLeak` record; the permit stays held (FR-000-09). |
| Runtime returns a body that could be transient capacity *or* a hard account quota, indistinguishable | `capacity` | Never `terminal` — clarification Q, spec Edge Cases. |
| `fork` invoked despite being undeclared | Does not reach classification — blocked at import time (`CapabilityError`). |

---

## Test obligations

| Test | Asserts | Trace |
|---|---|---|
| `test_error_classification.py::test_transient_is_retryable` | rows 1–3, 9 → `retryable` | FR-000-10, US4 §2 |
| `test_error_classification.py::test_quota_is_capacity` | rows 5 → `capacity` | FR-000-10, US4 §3 |
| `test_error_classification.py::test_bad_request_is_terminal` | rows 6–8 → `terminal` | FR-000-10, US4 §4 |
| `test_error_classification.py::test_ambiguous_defaults_to_capacity` | row 10 → `capacity`, never `terminal` | FR-000-10, US4 §5 |
| `test_error_classification.py::test_classification_on_record` | every failed Call Record carries exactly one `error_class` | FR-000-07, SC-006 |
