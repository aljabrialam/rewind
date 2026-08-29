# Implementation Plan: Restore to Checkpoint

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/003-restore-to-checkpoint/`

**Input**: Feature specification from `specs/003-restore-to-checkpoint/spec.md`

## Summary

Add one operation, `Engine.restore(checkpoint_id, verify=None) -> RestoreResult`,
that re-materialises a sandbox from a checkpoint's captured state through the Spec
000 port (create-one-from-snapshot), runs a caller-supplied before/after check to
prove the restoration, moves the run head to that checkpoint through Spec 001's
`set_head`, preserves every later checkpoint untouched, releases the old head's
working sandbox, and reports elapsed wall-clock time. The verification comes back
as structured data a viewer can render.

Technical approach: additive to `engine.py`. Three small result dataclasses
(`RestoreCheck`, `RestoreVerification`, `RestoreResult`) and one method plus a
private `_verify_restore` helper. Restore reuses `provider.branch(snapshot, 1)`
(the proven restore path from `test_ports.py::test_restore_returns_prior_state`),
`Run.get` / `Run.is_restorable` / `Run.set_head` / `Run.check_integrity` from Spec
001, and `provider.destroy` from Spec 000. No new module, no new dependency.

## Technical Context

**Language/Version**: Python 3.11+ (venv 3.14)

**Primary Dependencies**: none new — the capability port (Spec 000, `daytona`
isolated in `providers.py`) and the run tree (Spec 001). `pytest`.

**Storage**: none — in-memory run only (persistence out of scope)

**Testing**: `pytest`; base layer offline against `FakeProvider`; one live
contract test (`@pytest.mark.live`) for the ordered-call parity and the elapsed
budget

**Target Platform**: local dev + CI; restore executes on a Daytona sandbox live

**Project Type**: single project — internal library, `src/rewind/engine.py`

**Performance Goals**: offline restore sub-second (NFR-003-02); live restore a
few seconds (fits a 2-minute script alongside the rest)

**Constraints**: identical ordered actions live vs fake, fully offline on the
fake (NFR-003-03); never report "verified" without both checks passing
(FR-003-02 / SC-009); live sandbox count grows by at most one (FR-003-07 /
SC-006); later checkpoints never deleted or altered (FR-003-04)

**Scale/Scope**: one restore at a time, sequential; 7 FRs, 3 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work reaches the screen | The restore + its before/after verification + elapsed time are the centrepiece demo beat ("rewind to step 3"). **Pass** |
| II — Specification First | Tech names only in plan | Spec 003 names no tech; this plan names the port and `pytest`. **Pass** |
| IV — Nothing Is Invented | One port per external dependency | Restore calls only declared port operations (`branch`/create-from-snapshot, `run`, `destroy`); no SDK import added. **Pass** |
| V — Vertical Slices / no refactor | Additive | One new method + three result dataclasses in `engine.py`; `start`, `step`, `branch_from`, `promote`, `shutdown` untouched. **Pass** |
| VI — Traceability & Pyramid + Seam Rule | FR → named test; fake for the dependency; offline; fixtures from live | `FakeProvider` restore path already exists; ~12 offline tests + 1 live parity test. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| X — Evidence Over Assertion | Decide on observed results; render the evidence | FR-003-02 verification is exactly this — read the restored sandbox, report what was observed, never infer. `RestoreVerification` is structured for the screen (NFR-003-01). **Pass** |
| XI — Proven In The Runtime, Live | Live sandbox lifecycle on stage | Restore creates a real sandbox from a real snapshot; offline path is rehearsal insurance. **Pass** |
| XII — Resource Hygiene | Every sandbox bounded + destroyed; live count visible | FR-003-07 releases the old head's sandbox; SC-006 caps the net growth at one; failure path destroys any partial. **Pass** |

**Result**: No violations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-restore-to-checkpoint/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── restore.md          # restore() contract: inputs, verification rules, ordered calls, refusals
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/rewind/
├── engine.py          # EDIT (additive) — RestoreCheck / RestoreVerification /
│                      #   RestoreResult dataclasses; Engine.restore(); Engine._verify_restore()
├── ports.py           # UNCHANGED
├── providers.py       # UNCHANGED
├── capabilities.py    # UNCHANGED
└── reasoning.py       # UNCHANGED

tests/
├── unit/
│   └── test_restore.py         # NEW — offline: restore, verify, head move, preserve tail,
│                               #   refuse released/unreachable/unknown, elapsed, release old sandbox
└── contract/
    └── test_restore_contract.py   # NEW — @pytest.mark.live: ordered-call parity + elapsed budget

demo.py                # EDIT (additive, optional) — a "rewind to checkpoint N" beat that
                       #   prints the RestoreVerification; keep the existing branch beat
```

**Structure Decision**: Single-project layout unchanged. All feature code lands
in `engine.py` as additive members. One new unit test file, one new live contract
test.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 003 has no `[NEEDS CLARIFICATION]`. Phase 0
records: the restore-from-snapshot choice and its ordered calls; the
before/after verification model and the "verified" bar; how the old head's
sandbox is released without touching any snapshot; the failure-path contract; and
the live/fake parity observable.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `RestoreCheck`, `RestoreVerification`,
  `RestoreResult`, and the restore state machine as concrete shapes
- [contracts/restore.md](contracts/restore.md) — `restore()` inputs, the exact
  verification rules, the ordered port calls, the refusal table, and the
  resource-hygiene obligations
- [quickstart.md](quickstart.md) — run guide + FR/NFR/SC → named-test matrix

Post-design Constitution re-check: unchanged — additive, no new dependency.
