# Feature Specification: Restore to Checkpoint

**Feature ID**: `003-restore-to-checkpoint`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Execution State Recovery

**Business Actors**: Developer; Orchestrator

**Input**: User description: "Return the run to the exact runtime state of any earlier checkpoint, so that a developer can resume from before a mistake instead of restarting the run."

## Business Context

### Business Goal

Return the run to the exact runtime state of any earlier checkpoint, so that a
developer can resume from before a mistake instead of restarting the run.

### Business Value

This is the capability the product is named for. It converts a failed forty-step
run from a total loss into a thirty-nine step head start.

### Dependencies

- **Specification 000 — Sandbox Capability Contract**: restoration produces a
  sandbox through the single capability port, using only declared lifecycle
  operations (create-one-from-snapshot, destroy).
- **Specification 001 — Run and Checkpoint Model**: restoration reads a
  checkpoint's state (`live` / `released` / `unreachable`) and its restorability,
  and moves the run head through the model's head designation. The checkpoint's
  captured runtime-state reference is what restoration re-materialises.
- **Existing path**: create-one-from-snapshot already restores prior state in the
  offline model — exercised by
  `tests/unit/test_ports.py::test_restore_returns_prior_state`. This feature
  wraps that into a verified, head-moving, resource-cleaning operation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume from before the mistake (Priority: P1)

A developer's run has failed several steps deep. They name an earlier checkpoint,
and the system produces a usable sandbox whose state matches that checkpoint
exactly — the files, the working directory, everything as it was when that step
completed. The run head is now at that checkpoint, ready to continue.

**Why this priority**: This is the feature and the product's name. Everything
else here supports making this one action trustworthy.

**Independent Test**: Build a run of several steps, restore to an early one,
confirm the produced sandbox reflects that checkpoint's state, and confirm the
run head is now that checkpoint.

**Acceptance Scenarios**:

1. **Given** a run with several completed checkpoints, **When** an earlier
   checkpoint identifier is passed to restore, **Then** a usable sandbox is
   produced whose state matches that checkpoint.
2. **Given** a completed restoration, **When** the run head is queried, **Then**
   it is the restored checkpoint.
3. **Given** a completed restoration, **When** the next step is run, **Then** it
   executes against the restored sandbox and its checkpoint's parent is the
   restored checkpoint.

---

### User Story 2 - The restoration is verified, on screen (Priority: P1)

The system does not merely assert that state was restored — it checks. It reads
something the run wrote before the target checkpoint and confirms it is present,
and it checks that something the run wrote after the target checkpoint is absent.
Both results are returned in a form that can be shown on screen during the
demonstration, not only written to a log.

**Why this priority**: Constitution Article X — a claim of restoration without
the evidence behind it is a defect, and the judges built the runtime. A visible
before/after check is what makes the demo credible.

**Independent Test**: Restore to a checkpoint that sits between a known earlier
write and a known later write; confirm the returned verification shows the
earlier write present and the later write absent, and that the verification is
available as structured data a viewer can render.

**Acceptance Scenarios**:

1. **Given** a run that wrote marker A before checkpoint X and marker B after it,
   **When** the run is restored to X, **Then** the verification reports marker A
   present and marker B absent.
2. **Given** a restoration whose before-check fails or whose after-check finds
   the later state still present, **When** the result is returned, **Then** the
   restoration is reported as not verified, with which check failed.
3. **Given** any restoration, **When** its result is produced, **Then** the
   verification detail is structured data suitable for on-screen rendering, not
   only a log line.

---

### User Story 3 - Restoring does not destroy the road not taken (Priority: P2)

After restoring to an earlier checkpoint, every checkpoint that followed the
restored point is still in the run tree, with its recorded state and its captured
runtime-state reference. The developer can still inspect them, and a later
feature can still branch from them.

**Why this priority**: The product's premise is that no work is lost. If restore
pruned the tree, it would be a fancier "start over".

**Independent Test**: Restore to an early checkpoint, then confirm every later
checkpoint is still present in the tree with the same identifier, instruction,
and captured state reference.

**Acceptance Scenarios**:

1. **Given** a run restored to checkpoint X, **When** the run tree is inspected,
   **Then** every checkpoint created after X is still present with its original
   identifier and instruction.
2. **Given** a run restored to checkpoint X, **When** a later checkpoint's
   captured runtime-state reference is read, **Then** it is unchanged.
3. **Given** a run restored to checkpoint X, **When** the structural-integrity
   check runs, **Then** it passes.

---

### User Story 4 - A gone checkpoint cannot be restored, and says why (Priority: P2)

If the named checkpoint is marked released or unreachable, the system refuses the
restoration and states which of the two conditions applies. It does not produce a
sandbox and does not move the head.

**Why this priority**: Restoring to a state that no longer exists sends the run
somewhere undefined. The refusal has to name the reason so the developer knows
whether it was a deliberate release or a lost sandbox.

**Independent Test**: Attempt to restore a released checkpoint and an unreachable
checkpoint; confirm each is refused with the specific reason, no sandbox is
produced, and the head is unchanged.

**Acceptance Scenarios**:

1. **Given** a checkpoint marked released, **When** restore is attempted,
   **Then** it is refused and the reason names "released".
2. **Given** a checkpoint marked unreachable, **When** restore is attempted,
   **Then** it is refused and the reason names "unreachable".
3. **Given** a refused restoration, **When** the run is inspected, **Then** no
   new sandbox exists for it and the head is where it was.

---

### User Story 5 - Restoration is fast enough for the stage and reports its cost (Priority: P3)

Every restoration reports how long it took. A restoration completes quickly
enough that it can be performed live inside a two-minute demonstration without
stalling it.

**Why this priority**: Constitution Article XI — the demo runs live. A
restoration that takes thirty seconds cannot be shown; one that reports its own
elapsed time lets the presenter narrate it.

**Independent Test**: Perform a restoration and confirm the result carries an
elapsed time; confirm across repeated restorations that the elapsed time stays
within the budget that leaves room for the rest of a two-minute script.

**Acceptance Scenarios**:

1. **Given** any restoration, **When** its result is produced, **Then** it
   carries the elapsed wall-clock time of the restoration.
2. **Given** a restoration performed live, **When** it completes, **Then** its
   elapsed time is within the demonstration budget.

---

### User Story 6 - The old working sandbox is released (Priority: P3)

When the run moves off the checkpoint it was at, the sandbox that was serving
that old head is released once no live checkpoint still refers to it. The restore
never leaves an idle sandbox counting against the concurrency quota.

**Why this priority**: Constitution Article XII — an exhausted concurrency quota
during the demonstration is the failure mode. A restore that leaks the old
sandbox is one restore away from blocking the next branch.

**Independent Test**: Note the sandbox at the head, restore to an earlier
checkpoint, and confirm the old head's sandbox is released and the live sandbox
count did not grow by more than the one new restored sandbox.

**Acceptance Scenarios**:

1. **Given** the run at a head with an associated sandbox, **When** the run is
   restored to an earlier checkpoint, **Then** the old head's sandbox is released
   once nothing live refers to it.
2. **Given** a completed restoration, **When** the live sandbox count is
   compared to before, **Then** it increased by at most one (the restored
   sandbox) and any released sandbox was destroyed on both the success and the
   failure path.
3. **Given** a checkpoint whose captured runtime-state reference is still held,
   **When** the old sandbox is released, **Then** that checkpoint's reference is
   untouched and it remains restorable later.

---

### Edge Cases

- What happens when restore is asked for a checkpoint identifier that was never
  issued? It is refused as unknown; no sandbox is produced and the head is
  unchanged. (Treated the same class as released/unreachable — a refusal that
  names the reason.)
- What happens when restore is asked for the checkpoint that is already the head?
  It still produces a fresh sandbox for that checkpoint and reports elapsed time;
  the head does not change; the previous sandbox for that head is released if
  unreferenced.
- What happens when the before-check and after-check are not supplied by the
  caller? The restoration still produces the sandbox and reports elapsed time,
  but reports its verification status as "not checked" rather than "verified" —
  it never reports "verified" without having run the checks.
- What happens when producing the restored sandbox fails partway (the runtime
  refuses)? No head move occurs, any partially created sandbox is destroyed, the
  failure is surfaced with its elapsed time, and the old head remains intact.
- What happens when the after-check target legitimately also existed before the
  checkpoint (a marker that is not unique to the later state)? The verification
  is only as strong as the markers the caller supplies; the system reports
  exactly what it observed and does not infer success.
- What happens when two restorations are requested one after another to different
  checkpoints? Each is a complete operation — produce, verify, move head, release
  the prior sandbox — performed in sequence. Parallel restoration is out of
  scope.
- What happens when the restored checkpoint is the synthetic root? It is
  restorable if it still has a captured runtime-state reference; restoring to it
  returns the run to its starting state with all later checkpoints preserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-003-01**: The system MUST accept a checkpoint identifier and produce a
  usable sandbox whose state matches that checkpoint, using only the capability
  port (Specification 000).
- **FR-003-02**: The system MUST verify the restoration by reading state written
  before the checkpoint and confirming it is present, and by checking that state
  written after the checkpoint is absent. The system MUST NOT report a
  restoration as "verified" unless both checks ran and passed.
- **FR-003-03**: The system MUST move the head of the run to the restored
  checkpoint on success, through the head-designation mechanism of Specification
  001.
- **FR-003-04**: The system MUST preserve — not delete or alter — every
  checkpoint that followed the restored point, including its identifier,
  instruction, recorded state, and captured runtime-state reference.
- **FR-003-05**: The system MUST refuse to restore a checkpoint marked released
  or unreachable (or unknown), MUST state which condition applies, MUST NOT
  produce a sandbox, and MUST NOT move the head.
- **FR-003-06**: The system MUST report the elapsed wall-clock time of every
  restoration attempt, on both the success and the failure path.
- **FR-003-07**: The system MUST release the sandbox that was serving the
  previous head once no live checkpoint still references it, on both the success
  and the failure path, without touching any checkpoint's captured
  runtime-state reference.

### Non-Functional Requirements

- **NFR-003-01**: The verification of FR-003-02 MUST be returned as structured
  data that a viewer can render on screen — the before result, the after result,
  and the overall verified/not-verified/not-checked status — not only a log
  line.
- **NFR-003-02**: A restoration MUST complete within a duration that leaves room
  for the rest of a two-minute live demonstration; the offline path (fake
  runtime) MUST complete effectively instantly.
- **NFR-003-03**: The restore operation MUST behave identically in ordered
  actions against the live runtime and against the fake, and MUST run fully
  offline against the fake with no network and no credentials.

### Key Entities

- **Restore Request**: A checkpoint identifier, plus an optional verification
  specification (what to read as the before-marker and what to check as absent
  for the after-marker).
- **Restored Sandbox**: The usable sandbox produced from a checkpoint's captured
  runtime-state reference. A new sandbox; it does not reuse the old head's.
- **Restore Verification**: The structured result of the before/after checks —
  each check's target, whether it passed, and what was observed — plus an overall
  status of `verified`, `not-verified`, or `not-checked`.
- **Restore Result**: The outcome of a restoration attempt — the restored
  checkpoint identifier, the restored sandbox identifier (on success), the
  elapsed wall-clock time, the Restore Verification, and, on failure, the reason.
- **Released Sandbox**: The sandbox that had been serving the previous head,
  destroyed once unreferenced.
- **Preserved Tail**: The set of checkpoints that followed the restored point,
  untouched by the restoration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of successful restorations produce a sandbox whose observable
  state matches the target checkpoint (the before-marker present, the
  after-marker absent).
- **SC-002**: 100% of successful restorations leave the run head at the restored
  checkpoint.
- **SC-003**: 0% of restorations delete or alter a checkpoint that followed the
  restored point; the structural-integrity check passes after every restoration.
- **SC-004**: 100% of restorations of a released or unreachable (or unknown)
  checkpoint are refused with the specific reason named, produce no sandbox, and
  leave the head unchanged.
- **SC-005**: 100% of restoration attempts — success or failure — report an
  elapsed wall-clock time.
- **SC-006**: After a restoration, the live sandbox count increases by at most
  one; the previous head's sandbox is released when unreferenced, on both paths.
- **SC-007**: The verification result is available as structured data with a
  renderable before result, after result, and overall status, for 100% of
  restorations.
- **SC-008**: The offline restore path completes effectively instantly and runs
  with no network and no credentials.
- **SC-009**: The restore never reports "verified" when the before/after checks
  were not supplied or did not both pass.

## Assumptions

- **The before/after markers are supplied by the caller.** Only the caller knows
  what the run wrote and when; the restore mechanism runs the checks it is given
  in the restored sandbox and reports what it observed. The demonstration and the
  tests supply markers consistent with the scripted run (e.g. a file written
  early, a file written after the target step).
- **A checkpoint's captured runtime-state reference outlives the live sandbox.**
  Releasing the old head's sandbox does not invalidate any checkpoint's ability
  to be restored later from its own captured reference.
- **"Matches that checkpoint" means the filesystem state as of that checkpoint's
  completion**, as re-materialised from its captured reference — not a
  bit-for-bit machine image guarantee beyond what the runtime's create-from-state
  operation provides.
- **The demonstration budget** for a single restoration is a few seconds against
  the live runtime; the exact number is a planning concern. The offline path is
  sub-second.
- **Restoration is a single-branch, sequential operation.** One checkpoint at a
  time; the head moves once per successful restoration.
- **Restoring to a checkpoint does not re-run its step.** It re-materialises the
  state; continuing the run is a separate action (Specification 002's stepping).
- **"Released" and "unreachable" are the Specification 001 checkpoint states.**
  This feature reads them and refuses accordingly; it does not set them (that is
  promotion in 005 and the lost-sandbox edge case in 001).
- **Elapsed time is wall-clock**, measured around the whole restoration
  (produce + verify), reported in the result.

## Out of Scope

- Parallel restoration of multiple checkpoints in one operation.
- Persistence of the run or its sandboxes across a process restart.
- Creating alternative branches from the restored point (Specification 004).
- Choosing which checkpoint to restore to (a developer or a later feature
  decides; this feature executes the decision).
- Defining checkpoint states or the head mechanism (Specification 001).
- Capturing runtime state / creating snapshots (Specification 000 and the
  stepping in 002).
- Any user interface; this feature returns renderable data, it does not render
  it.
