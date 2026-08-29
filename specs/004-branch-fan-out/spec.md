# Feature Specification: Branch Fan-Out

**Feature ID**: `004-branch-fan-out`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Parallel Exploration

**Business Actors**: Developer; Strategist agent; Sandbox runtime

**Input**: User description: "Explore several alternative continuations from one checkpoint at the same time, each in its own isolated machine, so that a choice between strategies is settled by running them rather than by predicting them."

## Business Context

### Business Goal

Explore several alternative continuations from one checkpoint at the same time,
each in its own isolated machine, so that a choice between strategies is settled
by running them rather than by predicting them.

### Business Value

This is the capability with no clean equivalent on other runtimes, and the one
the sponsor's platform is uniquely able to provide. It is also the moment of the
demonstration that carries the most visual weight.

### Dependencies

- **Specification 000 — Sandbox Capability Contract**: every branch sandbox is
  created and destroyed through the capability port, using only declared
  lifecycle operations; the concurrency ceiling and the error classification
  come from there.
- **Specification 001 — Run and Checkpoint Model**: each branch is recorded as a
  child checkpoint of a common parent; per-branch state and terminal outcome are
  set on those checkpoints.
- **Specification 002 — Step Execution and Evidence**: the strategist's
  continuations arrive through the reasoning port in the structured-instruction
  schema, and each branch's execution evidence is captured the same way a step's
  is.
- **Existing path**: `Engine.branch_from(step_id, strategies)` already creates
  N sandboxes from one checkpoint's snapshot and records child checkpoints —
  exercised by `tests/unit/test_ports.py` and `demo.py`. This feature governs
  and hardens it: strategies from the reasoning agent, concurrent execution,
  live progress reporting, per-branch failure isolation, and guaranteed cleanup.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Try three continuations at once, from the same starting point (Priority: P1)

A developer, or the orchestrator on their behalf, picks a checkpoint and asks for
a declared number of alternative continuations. The strategist agent returns that
many distinct strategies in structured form. The system creates one isolated
sandbox per strategy, all derived from that one checkpoint, runs them at the same
time, and records each as a child checkpoint of the common parent with its own
captured evidence.

**Why this priority**: This is the feature and the centrepiece of the demo. The
whole product premise — settle a choice by running it — lives here.

**Independent Test**: From a checkpoint with captured state, request three
strategies; confirm three isolated sandboxes are created from that checkpoint,
each runs its strategy, and three child checkpoints of that parent exist, each
with independent evidence.

**Acceptance Scenarios**:

1. **Given** a checkpoint with captured runtime state and a request for N
   strategies, **When** the fan-out runs, **Then** the strategist is asked for
   exactly N continuations in structured form and a non-conforming response is
   rejected.
2. **Given** N structured strategies, **When** the fan-out runs, **Then** N
   isolated sandboxes are created, each derived from that same checkpoint.
3. **Given** a completed fan-out, **When** the run tree is inspected, **Then**
   the common parent has N new child checkpoints, each carrying its own
   instruction and its own execution evidence.
4. **Given** a completed fan-out, **When** the head is queried, **Then** it is
   unchanged — still the common parent (choosing a winner is out of scope).

---

### User Story 2 - The branches run in parallel, not one after another (Priority: P1)

The branch executions overlap in time. The total wall-clock time for the declared
number of branches is close to the time for the slowest single branch, not the
sum of all of them, so the fan-out fits inside a two-minute live demonstration.

**Why this priority**: Sequential branching defeats the point — three slow
strategies run one at a time would blow the demo budget, and "parallel
exploration" would be a false claim to judges who built the runtime.

**Independent Test**: Run a fan-out of N branches whose individual durations are
known; confirm the total elapsed time is close to the longest single branch, not
the sum, and is within the demonstration budget.

**Acceptance Scenarios**:

1. **Given** N branches that each take roughly the same time, **When** the
   fan-out runs, **Then** the total elapsed time is materially less than N times
   one branch's time.
2. **Given** the declared number of branches, **When** the fan-out completes,
   **Then** its total wall-clock time leaves room for the rest of a two-minute
   script.

---

### User Story 3 - Each branch is derived by the fastest way available (Priority: P2)

The system derives each branch sandbox using the fastest derivation the
capability map declares. If the preferred derivation is not present on the
account, it uses the next available one. The choice is recorded so it can be
shown and so a drift in the map changes behaviour deliberately, not silently.

**Why this priority**: The sponsor integration is graded on cleverness. Using the
fastest primitive the platform offers — and degrading honestly when it is absent
— is exactly that. Hard-coding one derivation would waste the platform's
advantage or break when the tier changes.

**Independent Test**: With a capability map that declares only the snapshot-based
derivation, confirm the fan-out uses it and records that choice; with a map that
also declares a faster derivation, confirm the fan-out prefers the faster one.

**Acceptance Scenarios**:

1. **Given** a capability map that declares a snapshot-based derivation and no
   faster one, **When** a fan-out runs, **Then** it uses the snapshot-based
   derivation and records that it did.
2. **Given** a capability map that additionally declares a faster derivation,
   **When** a fan-out runs, **Then** it uses the faster derivation.
3. **Given** the preferred derivation is absent from the map, **When** a fan-out
   runs, **Then** it falls back to the next available derivation without failing.

---

### User Story 4 - A failing branch does not sink the others (Priority: P2)

If one branch's strategy fails, the fan-out records that branch as failed and
still returns the completed results of the other branches. A branch failure is a
result, not an error that aborts the operation.

**Why this priority**: The reason to run three strategies is that some will not
work. If the first failure aborted the fan-out, the developer would learn nothing
about the strategies that would have succeeded.

**Independent Test**: Run a fan-out where one branch's strategy exits non-zero;
confirm that branch's child checkpoint is marked failed, the other branches'
child checkpoints carry their successful evidence, and the fan-out returns all of
them.

**Acceptance Scenarios**:

1. **Given** a fan-out of N branches where one strategy fails, **When** it
   completes, **Then** the failing branch's child checkpoint records the failure
   as its evidence and its terminal outcome is "failed".
2. **Given** the same fan-out, **When** its results are returned, **Then** the
   other N−1 branches' child checkpoints are present with their own evidence.
3. **Given** a branch whose sandbox could not be created at all, **When** the
   fan-out completes, **Then** that branch is reported failed with the reason,
   and the others are unaffected.

---

### User Story 5 - Each branch's live machine is visible while it runs (Priority: P2)

While the branches execute, the system reports, for each one, the runtime's own
sandbox identifier and the branch's running state (creating, running, done,
failed). The identifiers are shown exactly as the runtime issued them.

**Why this priority**: Constitution Article XI — the demo runs live, and the
visible proof that three real machines are working at once is the fan-out's whole
visual payload. A displayed identifier that was reformatted is not proof of a
real sandbox.

**Independent Test**: During a fan-out, observe the per-branch report; confirm
each entry carries a sandbox identifier byte-for-byte as the runtime issued it
and a running state that advances from creating through running to done or
failed.

**Acceptance Scenarios**:

1. **Given** a fan-out in progress, **When** the per-branch report is read,
   **Then** each branch entry carries the runtime's sandbox identifier, unmodified.
2. **Given** a fan-out in progress, **When** a branch moves from creating to
   running to done or failed, **Then** the report reflects that transition.
3. **Given** a completed fan-out, **When** the final report is read, **Then**
   every branch's terminal state is done or failed.

---

### User Story 6 - No branch sandbox is left running (Priority: P1)

Every sandbox the fan-out created is destroyed by the time the fan-out returns —
whether it succeeded, failed, or the whole operation raised. The number of live
sandboxes never exceeds the declared ceiling at any point during the fan-out, and
returns to its pre-fan-out level afterwards.

**Why this priority**: Constitution Article XII — an exhausted concurrency quota
during the demonstration is the failure mode. A fan-out that leaks three
sandboxes blocks the next one.

**Independent Test**: Note the live sandbox count before a fan-out; run it,
including a variant where a branch fails and a variant where the operation is
interrupted; confirm every branch sandbox is destroyed and the live count returns
to its starting value.

**Acceptance Scenarios**:

1. **Given** a completed fan-out, **When** the live sandbox count is checked,
   **Then** it equals the count from before the fan-out — every branch sandbox
   was destroyed.
2. **Given** a fan-out where one branch fails, **When** it completes, **Then**
   all branch sandboxes — including the failed one — are destroyed.
3. **Given** a fan-out that raises partway, **When** control returns, **Then**
   every branch sandbox created up to that point is destroyed.
4. **Given** a fan-out in progress, **When** the live sandbox count is sampled at
   any moment, **Then** it does not exceed the declared ceiling.

---

### Edge Cases

- What happens when the requested number of strategies exceeds the declared
  branch maximum? The request is capped at the maximum and the fan-out proceeds
  with that many; the cap is reported.
- What happens when the strategist returns fewer distinct strategies than
  requested, or duplicates? The fan-out runs the distinct strategies it received;
  it does not fabricate strategies to reach the requested count, and it reports
  how many it actually ran.
- What happens when the parent checkpoint is marked released or unreachable, or
  has no captured runtime state? The fan-out is refused before any sandbox is
  created, stating the reason (consistent with Specification 003's restore
  refusal).
- What happens when the concurrency ceiling has no room for the full set of
  branches? Branches that fit are created and run; the surplus is held for a
  bounded wait and then reported as a capacity outcome for that branch, leaving
  the branches that did start intact (per Specification 000's ceiling behaviour).
- What happens when two branches finish at the same instant? Both child
  checkpoints are recorded; a shared completion time does not merge, reorder, or
  drop either.
- What happens when a branch's strategy never terminates? The port's own bounded
  execution applies; that branch is reported failed and its sandbox is destroyed
  with the others.
- What happens when the strategist agent is unreachable? No branch sandbox is
  created; the condition is surfaced; the run tree is unchanged.
- What happens when the child checkpoints are inspected after the fan-out and
  their branch sandboxes are already destroyed? Each child keeps its identifier,
  instruction, evidence, and its own captured runtime-state reference; its state
  reflects that its live sandbox is gone, and a later feature can still act on it
  from its captured reference.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-004-01**: The system MUST obtain a declared number of distinct
  continuation strategies from the reasoning agent in the Specification 002
  structured-instruction schema, and MUST reject a response that does not
  conform.
- **FR-004-02**: The system MUST create one isolated sandbox per strategy, each
  derived from the same parent checkpoint's captured runtime state, through the
  capability port.
- **FR-004-03**: The system MUST select the derivation for a branch sandbox as
  the fastest one the capability map declares available, MUST fall back to the
  next available derivation when the preferred one is absent, and MUST record
  which derivation was used.
- **FR-004-04**: The system MUST execute the branches concurrently — their
  executions overlapping in time — not one after another.
- **FR-004-05**: The system MUST record each branch as a child checkpoint of the
  common parent, leaving the parent's own fields unchanged and the run head
  unchanged.
- **FR-004-06**: The system MUST capture execution evidence — exit status,
  output, elapsed time — independently for every branch.
- **FR-004-07**: The system MUST report, for every branch while it executes, the
  runtime's own sandbox identifier (unmodified) and the branch's running state
  (creating, running, done, or failed).
- **FR-004-08**: The system MUST continue when a branch fails — marking that
  branch's child checkpoint failed with its terminal outcome — and MUST return
  the results of the other branches; a branch failure MUST NOT abort the fan-out.
- **FR-004-09**: The system MUST NOT allow the number of concurrently live
  sandboxes to exceed the declared ceiling at any point during the fan-out.
- **FR-004-10**: The system MUST destroy every branch sandbox it created, on the
  success path, the branch-failure path, and the operation-raised path, without
  altering any child checkpoint's captured runtime-state reference.

### Non-Functional Requirements

- **NFR-004-01**: The total wall-clock time for the declared number of branches
  MUST be close to the slowest single branch's time, not the sum, and MUST leave
  room for the rest of a two-minute live demonstration. The offline path MUST
  complete effectively instantly.
- **NFR-004-02**: Branch sandbox identifiers MUST be the runtime's own, carried
  and displayed byte-for-byte unmodified (Specification 000's identifier rule).
- **NFR-004-03**: The fan-out MUST behave identically in its ordered set of port
  operations against the live runtime and against the fake, and MUST run fully
  offline against the fake with no network and no credentials.
- **NFR-004-04**: The per-branch progress report of FR-004-07 MUST be available
  as structured data a viewer can render, not only as log lines.

### Key Entities

- **Fan-Out Request**: A parent checkpoint identifier and a requested number of
  strategies (capped at the declared branch maximum). Optionally carries the
  context passed to the strategist.
- **Strategy**: One structured continuation from the strategist — an instruction
  to run plus a stated rationale (the Specification 002 schema). Distinct
  strategies only; duplicates are collapsed.
- **Branch**: One strategy executed in its own isolated sandbox derived from the
  parent checkpoint. Produces one child checkpoint.
- **Branch Sandbox**: The isolated machine for one branch. Created and destroyed
  by the fan-out; its identifier is the runtime's own.
- **Derivation**: The method used to produce a branch sandbox from the parent's
  captured state — selected as the fastest the capability map declares, with
  fallback. The chosen derivation is recorded.
- **Branch Progress**: The live, structured per-branch report — for each branch,
  its child checkpoint identifier, its runtime sandbox identifier, and its
  running state (creating | running | done | failed).
- **Fan-Out Result**: What the operation returns — the list of child checkpoints
  (one per branch that ran), each with its evidence and terminal outcome; the
  number of branches actually run; the derivation used; and the total elapsed
  time.
- **Common Parent**: The checkpoint every branch is derived from. Unchanged by
  the fan-out; still the run head afterwards.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a request of N strategies (N within the declared maximum), the
  fan-out creates exactly N isolated sandboxes, all derived from the one parent
  checkpoint, and records N child checkpoints of that parent.
- **SC-002**: The run head is the common parent both before and after the
  fan-out — 100% of fan-outs leave the head unchanged.
- **SC-003**: The total elapsed time for N equal-length branches is no more than
  1.5× a single branch's time (materially less than N×), and within the
  demonstration budget.
- **SC-004**: 100% of branches record independent evidence — exit status,
  output, elapsed time — with no branch's evidence derived from another's.
- **SC-005**: When one branch fails, 100% of the other branches' child
  checkpoints are still returned with their own evidence, and the failing
  branch's terminal outcome is "failed".
- **SC-006**: The live sandbox count never exceeds the declared ceiling during a
  fan-out, and returns to its pre-fan-out value after every fan-out — success,
  branch-failure, and raised paths alike.
- **SC-007**: 100% of displayed branch sandbox identifiers match the runtime's
  issued identifier byte-for-byte.
- **SC-008**: The per-branch progress report is available as structured data
  showing each branch's checkpoint identifier, sandbox identifier, and running
  state, for 100% of fan-outs.
- **SC-009**: The fan-out records which derivation it used, and selects the
  fastest one the capability map declares available in 100% of runs.
- **SC-010**: The offline fan-out completes effectively instantly and runs with
  no network and no credentials.

## Assumptions

- **The declared branch maximum is three** (`MAX_BRANCHES`, from the verified
  capability map: total CPU 10, three branches plus the head). A request for more
  is capped at three.
- **A "strategy" is a Specification 002 structured instruction** — `{instruction,
  rationale}`. The strategist is the reasoning port with its live and
  fixture-replay implementations; a fan-out fixture run replays recorded
  strategies for determinism.
- **The fastest declared derivation today is the snapshot-based one** (create a
  sandbox from the parent checkpoint's captured snapshot). A live-VM fork
  derivation is faster but is not in the verified capability map, so the fan-out
  uses the snapshot derivation and records that. If a faster derivation is added
  to the map later, the fan-out prefers it with no other change.
- **"Concurrently" means the branch executions overlap in wall-clock time.** The
  exact concurrency mechanism is a planning concern; the observable is that total
  time approximates the slowest branch, not the sum.
- **The fan-out does not move the head or choose a winner.** It runs the branches
  and returns their child checkpoints; promotion and ranking are Specification
  005.
- **Each branch's child checkpoint carries its own captured runtime-state
  reference** so that, after the fan-out destroys the live branch sandboxes,
  Specification 005 can still promote a branch by re-deriving it (as Specification
  003's restore does).
- **The parent checkpoint must be restorable** (live, with captured runtime
  state) for a fan-out to start — the same precondition Specification 003 uses.
- **Progress reporting is pull-or-push structured data**, not a specific UI. The
  timeline console (out of scope) consumes it; the tests read it directly.
- **Elapsed time is wall-clock**, measured around the whole fan-out, reported in
  the result.

## Out of Scope

- Choosing a winner among the branches (Specification 005).
- Merging branches, or combining their results.
- Recursive branching — creating a fan-out from a branch's child checkpoint
  before it has been promoted.
- Moving the run head (Specification 005's promotion; Specification 003's
  restore).
- Defining the checkpoint structure, states, or head mechanism (Specification
  001).
- Producing or refreshing the capability map (Specification 000).
- Any user interface, including the timeline console that renders the progress
  report.
