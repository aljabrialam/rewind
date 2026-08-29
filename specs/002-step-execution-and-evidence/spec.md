# Feature Specification: Step Execution and Evidence

**Feature ID**: `002-step-execution-and-evidence`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Verified Execution

**Business Actors**: Developer; Actor agent; Sandbox runtime

**Input**: User description: "Execute each agent step inside an isolated sandbox and capture what actually happened, so that later decisions are made against observed results rather than against the model's account of them."

## Business Context

### Business Goal

Execute each agent step inside an isolated sandbox and capture what actually
happened, so that later decisions are made against observed results rather than
against the model's account of them.

### Business Value

The difference between an agent product and a prompt wrapper is whether anything
is verified. Capturing exit codes and output from a real machine is what makes
the critic in Specification 005 defensible, and what makes the demonstration
credible to judges who built the runtime.

### Dependencies

- **Specification 000 — Sandbox Capability Contract**: every sandbox interaction
  in this feature goes through the single capability port. This feature invokes
  only the declared lifecycle operations and reads only verified fields.
- **The run tree / checkpoint concept** (Specification 001): this feature attaches
  captured evidence to the checkpoint created for a step. The checkpoint
  structure, its identifiers, and its ordering are owned there; this feature
  populates the evidence and rationale that a checkpoint carries.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A step executes and its evidence is captured (Priority: P1)

The system takes one instruction, runs it inside a sandbox obtained through the
capability port, and records the exit status, the standard output, and the
elapsed time. That captured evidence is attached to the checkpoint created for
the step.

**Why this priority**: This is the feature. Without a real execution result
attached to a step, there is nothing for the critic in 005 to judge and nothing
truthful to show on stage.

**Independent Test**: Feed one well-formed instruction, let it run, and confirm
the resulting checkpoint carries an exit status, the command's output, and a
positive elapsed time — all sourced from the runtime, not from any text the
reasoning agent produced.

**Acceptance Scenarios**:

1. **Given** a well-formed instruction, **When** the step runs, **Then** the
   checkpoint for that step carries an exit status, the standard output, and an
   elapsed time greater than zero.
2. **Given** a step that produces no output, **When** it runs and exits zero,
   **Then** the checkpoint records exit status zero and an empty output, not a
   missing-evidence marker.
3. **Given** the sandbox is obtained through the capability port, **When** the
   step runs, **Then** no sandbox interaction bypasses that port.

---

### User Story 2 - A malformed reasoning response is rejected before execution (Priority: P1)

The system asks the reasoning agent for the next instruction in a structured
form. If the response does not conform to the declared schema, the system
rejects it and does not execute anything.

**Why this priority**: An unstructured or partial response is exactly the "prompt
wrapper" failure mode. Executing whatever text came back is how an agent runs an
arbitrary command it was never asked to run.

**Independent Test**: Return a response missing a required field, or with the
wrong shape, and confirm the system raises a rejection and performs no sandbox
execution for that step.

**Acceptance Scenarios**:

1. **Given** a reasoning response that conforms to the declared schema, **When**
   it is received, **Then** the instruction it carries is executed.
2. **Given** a reasoning response missing a required field or of the wrong
   shape, **When** it is received, **Then** it is rejected and no step is
   executed.
3. **Given** a rejected response, **When** the rejection is raised, **Then** the
   run tree gains no checkpoint for that step.

---

### User Story 3 - A failing step halts the branch without losing history (Priority: P2)

When a step's exit status indicates failure, the system stops advancing the
current branch and records the failure. Every checkpoint taken before the
failing step remains intact and reachable.

**Why this priority**: The whole product premise is that a run that fails at step
40 does not cost you steps 1–39. A failure that discarded prior checkpoints would
defeat the reason the feature exists.

**Independent Test**: Run a sequence where one step exits non-zero, and confirm
the branch stops there, the failure is recorded on that step's checkpoint, and
the earlier checkpoints are still present with their evidence.

**Acceptance Scenarios**:

1. **Given** a step whose exit status indicates failure, **When** it completes,
   **Then** the current branch does not advance to a further step.
2. **Given** a failing step, **When** the branch halts, **Then** the failure is
   recorded on that step's checkpoint as part of its evidence.
3. **Given** a branch that has halted on a failure, **When** the run tree is
   inspected, **Then** all checkpoints created before the failing step are
   present and carry their original evidence.

---

### User Story 4 - Evidence is the sole basis; rationale is recorded but kept distinct (Priority: P2)

The system treats the captured execution result as the only evidence of what
occurred. The reasoning agent's stated rationale for the step is recorded
alongside that evidence, clearly separated from it, and is never substituted for
it.

**Why this priority**: Constitution Article X. A verdict shown without the
evidence behind it is a defect, and the judges built the platform — an
agent's self-report presented as an outcome is the fastest way to lose them.

**Independent Test**: Run a step where the agent's rationale claims success but
the exit status indicates failure; confirm the recorded outcome follows the exit
status, and that the rationale is still stored, marked as rationale, not as
evidence.

**Acceptance Scenarios**:

1. **Given** a step with both a captured result and a stated rationale, **When**
   the checkpoint is written, **Then** the two are stored in distinct fields and
   are distinguishable without interpretation.
2. **Given** a rationale that disagrees with the captured exit status, **When**
   the outcome is determined, **Then** it follows the captured exit status.
3. **Given** any step, **When** its outcome is reported, **Then** the report
   carries the evidence, not only the rationale.

---

### User Story 5 - Branch step count is bounded (Priority: P3)

The system enforces a declared upper limit on how many steps a single branch may
contain. Reaching the limit stops the branch in the same controlled way a
failure does.

**Why this priority**: An unbounded step loop burns the wall-clock the
demonstration does not have and can exhaust the sandbox concurrency quota. The
bound is cheap to state and expensive to omit.

**Independent Test**: Drive a branch to one step below the declared limit, then
one more; confirm the branch stops at the limit, records why it stopped, and
does not execute a further step.

**Acceptance Scenarios**:

1. **Given** a branch at one step below the declared limit, **When** another step
   is requested, **Then** it runs and the branch is now at the limit.
2. **Given** a branch at the declared limit, **When** another step is requested,
   **Then** no step is executed and the branch is marked as having reached the
   limit.
3. **Given** the declared limit, **When** it is read, **Then** it is a single
   declared value, not scattered across the system.

---

### User Story 6 - Live and fake execution paths are identical; reasoning is replayable (Priority: P3)

The sequence of actions taken to execute a step — obtain sandbox, run
instruction, capture evidence, attach to checkpoint — is the same whether the
runtime is the live sandbox provider or the fake. Reasoning responses can be
served from recorded fixtures so that a rehearsed run produces the same steps
every time.

**Why this priority**: Constitution Seam Rule and Article XI. The team must be
able to run the whole step loop offline, and the on-stage run must be
deterministic enough to rehearse twice.

**Independent Test**: Run the same scripted task once against the fake provider
with fixture-backed reasoning and once against the live provider; confirm the
ordered list of steps, their instructions, and their outcome shapes match.

**Acceptance Scenarios**:

1. **Given** the fake provider and fixture-backed reasoning, **When** a scripted
   task runs, **Then** it completes with no network and no credentials.
2. **Given** the same scripted task run twice against fixture-backed reasoning,
   **When** the two runs are compared, **Then** they produce the same ordered
   steps and instructions.
3. **Given** a step executed against the live provider and the same step against
   the fake, **When** their execution paths are compared, **Then** the same
   ordered actions occur against the capability port.

---

### Edge Cases

- What happens when the reasoning agent is unreachable or returns nothing? The
  step is not executed; the condition is surfaced to the caller, and no
  checkpoint is created for the step.
- What happens when a step's output is very large? The full output is captured as
  evidence; any shortening for display is a concern of a later feature, not of
  the capture.
- What happens when a step writes to the error stream but exits zero? The outcome
  follows the exit status (success); the captured output is whatever the runtime
  returns as the command result.
- What happens when a step never terminates? The sandbox port's own bounded
  execution applies; if the runtime returns no result, the step is treated as a
  failure of that step and the branch halts.
- What happens when the reasoning response is well-formed but carries an empty
  instruction? It is treated as a schema violation and rejected.
- What happens when a rationale is absent from an otherwise valid response? The
  response is rejected; rationale is a required field of the declared schema.
- What happens when the step limit is reached at the same time a step fails? The
  branch halts once; the recorded stop reason is the failure, which is the more
  specific cause.
- What happens when captured evidence cannot be attached to a checkpoint (the
  checkpoint does not exist)? The step is treated as failed and the condition is
  surfaced; no evidence is silently dropped.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-002-01**: The system MUST obtain the next instruction from a reasoning
  agent in a structured form, and MUST reject any response that does not conform
  to the declared schema. The declared schema requires a non-empty instruction
  and a stated rationale.
- **FR-002-02**: The system MUST execute each instruction inside a sandbox
  obtained through the capability port (Specification 000), using only declared
  lifecycle operations.
- **FR-002-03**: The system MUST capture, for each executed step, the exit
  status, the standard output, and the elapsed time.
- **FR-002-04**: The system MUST treat captured execution results as the sole
  evidence of what occurred, and MUST NOT accept the reasoning agent's
  description of an outcome in their place.
- **FR-002-05**: The system MUST attach the captured evidence to the checkpoint
  created for that step.
- **FR-002-06**: The system MUST halt the current branch when a step's exit
  status indicates failure, and MUST record the failure on that step's
  checkpoint without discarding or altering any prior checkpoint.
- **FR-002-07**: The system MUST enforce a single declared upper bound on the
  number of steps in one branch, and MUST stop the branch in a controlled way
  when the bound is reached.
- **FR-002-08**: The system MUST record the reasoning agent's stated rationale
  alongside the evidence, in a distinct field, such that evidence and rationale
  are distinguishable without interpretation.

### Non-Functional Requirements

- **NFR-002-01**: A step's execution path — obtain sandbox, run instruction,
  capture evidence, attach to checkpoint — MUST be identical whether the runtime
  is the live sandbox provider or the fake.
- **NFR-002-02**: Reasoning responses MUST be replayable from recorded fixtures,
  so that a rehearsed run is deterministic — the same fixtures yield the same
  ordered steps and instructions.
- **NFR-002-03**: The full step loop MUST run with no network and no credentials
  when the fake provider and fixture-backed reasoning are selected.

### Key Entities

- **Instruction**: The structured unit of work returned by the reasoning agent.
  Carries a non-empty instruction to execute and a stated rationale. A response
  that does not match this shape is rejected.
- **Reasoning Agent (Actor)**: The source of instructions. Reached through a
  reasoning port that has both a live implementation and a fixture-replay
  implementation. This feature consumes its output; it does not evaluate or rank
  it.
- **Step**: One execution of one instruction inside a sandbox. Has an ordinal
  position within its branch.
- **Evidence**: The captured record of what the runtime did for a step — exit
  status, standard output, elapsed time. Sourced only from the runtime. The sole
  basis for any outcome determination.
- **Rationale**: The reasoning agent's stated reason for the step. Stored in a
  field distinct from Evidence. Never substituted for Evidence.
- **Checkpoint**: The run-tree node for a step (owned by Specification 001). This
  feature attaches Evidence and Rationale to it.
- **Branch Step Bound**: The single declared maximum number of steps permitted in
  one branch. Reaching it halts the branch.
- **Branch Halt Reason**: Why a branch stopped advancing — a step failure, or the
  step bound reached. Recorded when the branch halts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of executed steps produce a checkpoint carrying an exit
  status, a standard output value (possibly empty), and an elapsed time greater
  than zero.
- **SC-002**: 0% of malformed reasoning responses result in a sandbox execution;
  each is rejected and leaves no checkpoint.
- **SC-003**: When a step fails, 100% of checkpoints created before it remain
  present and unchanged, and the branch executes no further step.
- **SC-004**: In a run where a rationale claims an outcome that the exit status
  contradicts, 100% of recorded outcomes follow the exit status.
- **SC-005**: Evidence and rationale are retrievable as separate fields for 100%
  of steps; no step stores rationale in place of evidence.
- **SC-006**: No branch ever exceeds the declared step bound, verified by driving
  a branch past it.
- **SC-007**: The same scripted task run twice with fixture-backed reasoning
  produces an identical ordered list of step instructions.
- **SC-008**: The full step loop completes against the fake provider with network
  disabled and no credentials present.

## Assumptions

- **Failure is a non-zero exit status.** A step "indicates failure" when its
  captured exit status is non-zero. A zero exit status is success regardless of
  what was written to the error stream or what the rationale claims.
- **"Standard output" is the runtime's returned command result stream.** Whether
  the error stream is merged into it is a property of the sandbox runtime;
  capturing a separate error stream is not required by this feature.
- **The declared schema for an instruction is minimal**: a non-empty command
  string to run, plus a rationale string. Additional fields a reasoning agent
  includes are ignored, not rejected.
- **The step bound is a single configured value** with a sensible default in the
  tens of steps (the reference example is "step 40 of 50"), overridable by
  configuration. Its exact number is a planning decision, not a specification
  one.
- **The reasoning port mirrors the sandbox port's seam pattern** (Specification
  000): one interface, a live implementation and a fixture-replay implementation,
  and no feature code talks to a reasoning vendor directly.
- **Checkpoint creation and ordering belong to Specification 001.** This feature
  assumes a checkpoint exists for each step and only populates its evidence and
  rationale; if 001 is not yet built, a minimal stand-in checkpoint structure is
  acceptable for this feature's tests.
- **One branch, advancing forward.** This feature runs steps along a single
  branch. Creating alternative branches, and choosing between alternative
  instructions, are out of scope (Specifications 004 and 005).
- **Elapsed time is wall-clock**, measured around the execution call, and is
  always greater than zero for a step that ran.

## Out of Scope

- Choosing between alternative instructions (Specification 005).
- Branching — creating alternative continuations from a checkpoint (Specification
  004).
- Any user interface, including how evidence or rationale is displayed.
- Ranking, scoring, or promoting steps.
- Defining the checkpoint structure, its identifiers, or its ordering
  (Specification 001).
- Producing or refreshing the sandbox capability map (Specification 000).
