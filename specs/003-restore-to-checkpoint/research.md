# Phase 0 Research: Restore to Checkpoint

Spec 003 carries no `[NEEDS CLARIFICATION]`. Technical decisions for design.
Evidence: `src/rewind/engine.py` (`Run`, `Engine`, `branch_from`, `promote`,
`shutdown`), `src/rewind/providers.py` (`branch(snapshot, n)`, `destroy`,
`FakeProvider`), `tests/unit/test_ports.py::test_restore_returns_prior_state`,
Constitution Articles X, XI, XII.

---

## R1. How a checkpoint is restored

**Decision**: `provider.branch(cp.snapshot, 1)[0]` — create exactly one sandbox
from the checkpoint's captured snapshot. This is the operation the offline test
`test_restore_returns_prior_state` already exercises (`p.branch(snap, 1)[0]`),
and `DaytonaProvider.branch` already does create-from-snapshot with the readiness
gate and ceiling accounting from Spec 000.

**Rationale**: FR-003-01 wants "a usable sandbox whose state matches that
checkpoint". The snapshot IS that state; creating one sandbox from it is the
minimal path and reuses every Spec 000 guarantee (bounded wait, intervals,
classified errors).

**Alternatives considered**:
- A dedicated `provider.restore()` op — rejected: it is not in the verified
  capability map (Article IV); create-from-snapshot already does the job.
- Re-running `path_to(cp)` step by step — rejected: slow, and it re-executes
  steps, which FR-003 explicitly does not do (spec Assumptions).

---

## R2. The before/after verification model (FR-003-02, NFR-003-01)

**Decision**: `restore(step_id, verify: RestoreCheck | None = None)`.
`RestoreCheck` holds two lists of `(command, marker)` pairs:
- `before` — each `command` run in the restored sandbox must have `marker`
  **present** in its output;
- `after` — each `command` must have `marker` **absent**.

`_verify_restore` runs them via `provider.run` and returns a `RestoreVerification`
with per-check detail (`command`, `marker`, `observed`, `passed`) and an overall
`status`:
- `not-checked` — no `before` and no `after` supplied;
- `verified` — at least one `before` AND at least one `after`, and every check
  passed;
- `not-verified` — checks ran but the set is incomplete or one failed.

**Rationale**: FR-003-02 / SC-009 — never report "verified" without both a
present-before and an absent-after check passing. The markers must come from the
caller (only it knows the run's writes — spec Assumptions). The structured result
satisfies NFR-003-01 (renderable, not just logged).

**Alternatives considered**:
- Auto-probe by writing engine sentinels after every step — rejected for the
  hackathon: extra writes into every run, and the caller's own markers
  (`log.txt`, `calc.py` in `demo.py`) are already there.
- Boolean-only result — rejected: NFR-003-01 wants the before/after detail on
  screen.

---

## R3. Moving the head and preserving the tail (FR-003-03, FR-003-04)

**Decision**: on success, `self.run.set_head(step_id)` (Spec 001 — already
refuses a non-live / snapshot-less target) and `self.live[step_id] = new_handle`.
Nothing is removed from `run.order` or `run.checkpoints`; no later checkpoint's
fields are touched. `check_integrity()` is expected to pass unchanged.

**Rationale**: FR-003-03 routes through the one head mechanism; FR-003-04 falls
out of restore being append-nothing/delete-nothing. The later checkpoints keep
their own `snapshot`s, so they stay restorable later (spec US3 §2).

---

## R4. Releasing the old head's sandbox (FR-003-07, SC-006)

**Decision**: after the head move, `old = self.live.pop(old_head, None)`; if
`old` and no remaining `self.live` value shares `old.id`, `provider.destroy(old)`.
The `old_head` **checkpoint** stays in the tree with its `snapshot` intact — only
the live working handle is released.

**Rationale**: FR-003-07 — release the previous head's sandbox once nothing live
refers to it, without touching any captured reference. SC-006 — net live count
grows by at most one (the restored sandbox). Failure path: no head move, so the
old handle stays; instead any partially created restored sandbox is destroyed
(Spec 000's `branch` already `_blind_destroy`s a half-born child, and `restore`
returns without registering it).

---

## R5. Failure path and refusals (FR-003-05, FR-003-06)

**Decision**: `restore` never raises for a business refusal — it returns a
`RestoreResult` with `sandbox_id = None`, an `elapsed_seconds`, a `not-checked`
verification, and an `error` string:
- unknown id → `error = "unknown"`;
- `state == "released"` → `error = "released"`;
- `state == "unreachable"` or `snapshot is None` → `error = "unreachable"`;
- runtime failure creating the sandbox → `error = <classified message>`.

On every one of these the head is unchanged and no sandbox is registered
(FR-003-05). `elapsed_seconds` is measured around the whole attempt and always
present (FR-003-06, SC-005).

**Rationale**: a returned result (not an exception) keeps the elapsed time and
the reason together and renderable; the caller/console shows the refusal the same
way it shows a success.

**Alternatives considered**:
- Raise `ValueError` on refusal — rejected: loses the elapsed time and forces the
  console to special-case exceptions vs results.

---

## R6. Live/fake parity observable (NFR-003-03)

**Decision**: the ordered `provider.calls` (`CallRecord.operation`) for a
successful restore with one before and one after check is
`["branch", "run", "run", "destroy"]` (create-from-snapshot, before probe, after
probe, release old head). A unit test asserts this against `FakeProvider`; the
live contract test asserts the same op sequence against `DaytonaProvider` and
that the elapsed time is within the budget.

---

## Open items carried to Phase 1

- Exact dataclass fields + state machine → [data-model.md](data-model.md)
- Verification rule table + refusal table + ordered calls → [contracts/restore.md](contracts/restore.md)
- FR→test matrix → [quickstart.md](quickstart.md)
