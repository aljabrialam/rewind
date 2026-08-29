# Implementation Plan: Sandbox Capability Contract

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/000-sandbox-capability-contract/`

**Input**: Feature specification from `specs/000-sandbox-capability-contract/spec.md`

## Summary

Turn the single sandbox seam that already exists in the repository
(`src/rewind/ports.py`, `src/rewind/providers.py`) into an **enforced capability
contract**. Every sandbox lifecycle operation the system may invoke is declared
in a machine-readable capability map generated from a live account run; anything
not in that map fails when the code is loaded, not during the demo. The live
port and an offline port implement the same declared operations, every runtime
call is timed and recorded, every created sandbox is bounded and cleaned up, and
runtime errors are classified `retryable` / `capacity` / `terminal`. A contract
test suite re-checks the map against the live runtime in under thirty seconds.

Technical approach: add a small `capabilities` module that loads the map and
validates, at import time, that the port only declares verified operations;
wrap both providers behind that contract; add a recording wrapper that captures
JSON fixtures from live runs for the offline unit tests; extend `spine_test.py`
to emit the machine-readable map alongside the existing prose notes.

## Technical Context

**Language/Version**: Python 3.11+ (repo targets `>=3.11`, venv is 3.14)

**Primary Dependencies**: `daytona` SDK (the single declared runtime exception,
per Constitution Article II); `pytest` for all three test layers; standard
library only for the contract logic (`dataclasses`, `concurrent.futures`,
`tomllib`/`json`, `time`, `threading`)

**Storage**: Files only — `.rewind/daytona-capability-map.md` (existing prose
record) plus a new machine-readable companion `.rewind/capability-map.toml`;
recorded fixtures under `fixtures/`

**Testing**: `pytest`; base layer runs offline against `FakeProvider`; one
contract test runs live against the account and must finish < 30s; one E2E test
is the demo path

**Target Platform**: Local developer machine and CI runner (Linux/macOS);
sandboxes run on the Daytona cloud runtime

**Project Type**: Single project — internal library seam consumed by
`src/rewind/engine.py` and `demo.py`

**Performance Goals**: Contract suite < 30s wall clock (NFR-000-02); offline unit
suite sub-second (Constitution Article VI base layer); no per-operation latency
target beyond "does not stall the demo"

**Constraints**: Offline-capable (no network, no credentials) for everything
except the one contract test and the fixture-capture run; import-time failure for
undeclared operations (NFR-000-01); bounded waits/retries only, no open-ended
loops (NFR-000-05); feature freeze 15:00, no refactor after (Constitution
Article V)

**Scale/Scope**: One account, concurrency ceiling ~10 sandboxes (total CPU 10),
`MAX_BRANCHES=3`; ~5 declared lifecycle operations (`spawn`, `run`,
`checkpoint`, `branch`, `destroy`); 2 sandbox classes (`container`, `vm`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work must reach the screen | The live sandbox count and the `retryable`/`capacity`/`terminal` verdicts are demo-visible; the import-time guard is what lets the demo run without an invented call. **Pass** |
| II — Specification First | What/why in spec; tech only in plan; sandbox runtime is the one exception | Spec carries no other tech name; this plan names `daytona`, `pytest`. **Pass** |
| III — Spine Rule | Riskiest assumption proven first | Spine already proven (snapshot-based branching, `de8347b`); this feature hardens the seam the spine exercised. **Pass** |
| IV — Nothing Is Invented | Capability observed + recorded; single port; no SDK import in feature code | This feature *is* the enforcement mechanism for Article IV. `providers.py` stays the only SDK importer. **Pass** |
| V — Vertical Slices | End-to-end thin path always runnable; no refactor after 15:00 | Enforcement added as a thin wrapper over the existing working port; no restructure of `engine.py`. **Pass** |
| VI — Traceability & Pyramid + Seam Rule | Every FR → named test; fake for every dependency; offline runnable; fixtures from live | `FakeProvider` already exists; plan adds the recording wrapper and the contract test. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| X — Evidence Over Assertion | Decisions on observed execution results | Post-condition assertions (FR-000-01a) and Call Records are the evidence; classification is derived from real error responses. **Pass** |
| XI — Proven In The Runtime, Live | Sandbox lifecycle genuinely live on stage | Contract test and fixture capture run live; offline path is insurance only. **Pass** |
| XII — Resource Hygiene | Stop + delete interval on every sandbox; destroy on both paths; live count visible | FR-000-08 / FR-000-08a / FR-000-09 encode exactly this; ceiling from verified quota (FR-000-11). **Pass** |
| XIII — Honest Framing | No overclaiming | `fork` stays undeclared because its post-condition was never asserted (spec Assumptions); the map records only what ran. **Pass** |

**Result**: No violations. Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/000-sandbox-capability-contract/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output — FR→test map + run guide
├── contracts/
│   ├── sandbox-port.md          # the port contract: operations, classes, post-conditions
│   ├── capability-map-schema.md # machine-readable map format
│   └── error-classification.md  # retryable / capacity / terminal rules
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
src/rewind/
├── ports.py           # EXISTING — Handle, ExecResult, Checkpoint, SandboxProvider Protocol
│                      #   + add: LifecycleOp registry, import-time contract guard call
├── capabilities.py    # NEW — load capability map, validate declared ops at import time,
│                      #   expose SandboxClass, ErrorClass, ConcurrencyCeiling, CapabilityError
├── providers.py       # EXISTING — DaytonaProvider (only SDK importer), FakeProvider
│                      #   + add: readiness gate, bounded ceiling wait, destroy retry + leak record,
│                      #     error classification, CallRecord list, latency/fail-rate already on Fake
├── recording.py       # NEW — RecordingProvider wrapper: run live, write fixtures/*.json
└── engine.py          # EXISTING — unchanged (consumes the port only)

tests/
├── unit/
│   ├── test_ports.py            # EXISTING — Fake behaviour
│   ├── test_capabilities.py     # NEW — import-time rejection, class mismatch, incomplete map
│   ├── test_lifecycle.py        # NEW — readiness gate, cleanup-on-raise, ceiling wait, destroy leak
│   └── test_error_classification.py  # NEW — retryable/capacity/terminal, capacity-or-terminal→capacity
├── contract/
│   └── test_daytona_contract.py # NEW — live, < 30s: every declared op + post-condition + experimental-name pin
└── e2e/
    └── test_demo_path.py        # EXISTING/owned elsewhere — the scripted demo path

tools/
└── spine_test.py      # EXISTING — extend to emit .rewind/capability-map.toml

.rewind/
├── daytona-capability-map.md    # EXISTING prose record (human notes)
└── capability-map.toml          # NEW machine-readable declaration (generated)

fixtures/
├── tree.json                    # EXISTING
└── daytona/*.json               # NEW — one file per recorded live operation
```

**Structure Decision**: Single-project layout already in place. The contract is
added as two new small modules (`capabilities.py`, `recording.py`) plus additive
methods on the existing providers. `engine.py` is not touched — it already
depends only on the `SandboxProvider` Protocol, which is the single port. No
directory restructure, consistent with Constitution Article V.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). All spec `[NEEDS CLARIFICATION]` were resolved in
the `/speckit.clarify` session (2026-08-29); Phase 0 records the remaining
technical decisions:

1. Machine-readable capability-map format and how `spine_test.py` emits it
2. Import-time enforcement mechanism in Python
3. Sandbox class model (`container` vs `vm`) and per-operation class binding
4. Error classification: mapping SDK exceptions / HTTP status to the three classes
5. Bounded-wait and retry values, sourced from recorded timings
6. Fixture capture and replay strategy
7. Concurrency ceiling enforcement primitive

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — the nine entities from the spec as concrete
  record shapes with fields, validation rules, and state transitions
- [contracts/sandbox-port.md](contracts/sandbox-port.md) — the five declared
  operations, their required sandbox class, and the observable post-condition
  each contract test must assert
- [contracts/capability-map-schema.md](contracts/capability-map-schema.md) — the
  `capability-map.toml` schema the import-time guard reads
- [contracts/error-classification.md](contracts/error-classification.md) — the
  decision table from runtime failure to `retryable` / `capacity` / `terminal`
- [quickstart.md](quickstart.md) — run guide plus the FR → named-test matrix
  required by Constitution Article VI

Post-design Constitution re-check: unchanged — the design adds two leaf modules
and additive provider methods, imports no new third-party dependency, and keeps
`providers.py` as the sole SDK boundary.
