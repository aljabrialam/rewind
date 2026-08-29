# Feature Specification: Run and Checkpoint Model

**Feature ID**: `001-run-and-checkpoint-model`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Execution State Management

**Business Actors**: Developer; Orchestrator

**Input**: User description: "Represent an agent run as a durable tree of checkpoints rather than a transcript, so that any earlier moment in the run remains addressable after the run has moved past it."

## Business Context

### Business Goal

Represent an agent run as a durable tree of checkpoints rather than a transcript,
so that any earlier moment in the run remains addressable after the run has moved
past it.

### Business Value

An agent run today leaves only a log. When it fails at step forty, there is
nothing to return to. Modelling the run as a tree is what makes rewind and
branching possible at all; every other feature depends on this one.

### Dependencies

- **Downstream**: Specifications 002 (step execution attaches evidence to a
  checkpoint), 004 (branching creates children of a checkpoint), and 005
  (promotion moves the head and releases losers) all build on the structure this
  feature defines.
- **Existing implementation**: `src/rewind/engine.py` already contains a working
  `Run` and `Checkpoint` with `add`, `path_to`, and `as_tree`. This
  specification governs that structure and names the gaps it must still close
  (creation time per checkpoint, an explicit "restorable" predicate, a branch
  terminal outcome).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An earlier moment stays addressable after the run moves on (Priority: P1)

The orchestrator records a checkpoint as each step completes. Every checkpoint
keeps a stable identifier for the life of the run. After the run has advanced
many steps past a given checkpoint, that checkpoint can still be named and its
lineage back to the start read off without recomputation.

**Why this priority**: This is the whole feature. If an identifier can churn or a
checkpoint can be dropped once the head passes it, rewind and branching have
nothing to stand on.

**Independent Test**: Build a run of several steps, note the identifier of an
early checkpoint, advance the run past it, then confirm that identifier still
resolves to the same checkpoint and that the path from the root to it is
returned in order.

**Acceptance Scenarios**:

1. **Given** a run with several completed steps, **When** an early checkpoint's
   identifier is recorded and the run advances further, **Then** that identifier
   still resolves to the same checkpoint with the same instruction and index.
2. **Given** any checkpoint, **When** its lineage is requested, **Then** the
   ordered list of checkpoints from the root to it is returned without further
   computation by the caller.
3. **Given** a run, **When** it is inspected, **Then** its steps form an ordered
   sequence, each carrying an index, an instruction, and a completion state.

---

### User Story 2 - The run is a tree, not a list (Priority: P1)

A checkpoint may have more than one child. Two children can be created from the
same parent, and both are recorded as children of that parent while the parent
is unchanged. Exactly one checkpoint is the head at any moment.

**Why this priority**: Branching (Specification 004) needs a parent to hold
multiple children. A structure that only appends to a single line cannot
represent the choice the product is built around.

**Independent Test**: Create two children from one parent, then confirm the
parent lists both as children, each child names that parent, and the head is
exactly one identified checkpoint.

**Acceptance Scenarios**:

1. **Given** a checkpoint, **When** two children are created from it, **Then**
   the parent records both identifiers as children and neither creation alters
   the parent's own fields.
2. **Given** a run at any moment, **When** the head is queried, **Then** exactly
   one checkpoint is returned as head.
3. **Given** a child checkpoint, **When** it is inspected, **Then** it names its
   parent, the sandbox identifier associated with it, and the time it was
   created.

---

### User Story 3 - A released checkpoint is never offered as restorable (Priority: P2)

Each checkpoint is marked live, released, or unreachable. A checkpoint whose
runtime state has been released, or that was never reachable, is never presented
as something the run can return to.

**Why this priority**: Promotion (Specification 005) releases the losing
branches' sandboxes. Offering one of those as a restore target would send the run
to a state that no longer exists.

**Independent Test**: Mark a checkpoint released, then ask the model whether it is
restorable and confirm the answer is no; confirm a live checkpoint with runtime
state is restorable.

**Acceptance Scenarios**:

1. **Given** a checkpoint marked released, **When** its restorability is checked,
   **Then** it is reported as not restorable.
2. **Given** a checkpoint marked unreachable, **When** its restorability is
   checked, **Then** it is reported as not restorable.
3. **Given** a checkpoint marked live that has associated runtime state, **When**
   its restorability is checked, **Then** it is reported as restorable.
4. **Given** any listing of restore targets, **When** it is produced, **Then** it
   contains no released or unreachable checkpoint.

---

### User Story 4 - Every branch has a terminal outcome (Priority: P2)

When a branch of the run stops advancing, its terminal outcome is recorded as
succeeded, failed, or abandoned. The outcome is a property of the branch, read
off without inspecting individual steps.

**Why this priority**: The critic in Specification 005 and any summary view need
to know how a branch ended without walking every step and re-deriving it.

**Independent Test**: Drive one branch to a successful stop, one to a failing
step, and one that is abandoned in favour of another; confirm each branch's
recorded terminal outcome matches.

**Acceptance Scenarios**:

1. **Given** a branch whose last step completed successfully and which advances
   no further, **When** its terminal outcome is read, **Then** it is
   "succeeded".
2. **Given** a branch whose last step failed, **When** its terminal outcome is
   read, **Then** it is "failed".
3. **Given** a branch that was set aside in favour of another, **When** its
   terminal outcome is read, **Then** it is "abandoned".
4. **Given** a branch still advancing, **When** its terminal outcome is read,
   **Then** no terminal outcome is reported yet.

---

### User Story 5 - The whole tree renders without extra work (Priority: P3)

The full tree is available in a single form that a viewer can render directly —
every node with its identifier, index, instruction, parent, children, state,
associated sandbox, creation time, captured outcome, and rationale — with no
join, walk, or recomputation required of the consumer.

**Why this priority**: The timeline console (out of scope here) and the
rehearsal fixtures both read this one form. If rendering it needs a second pass,
every consumer reimplements that pass.

**Independent Test**: Produce the renderable form for a multi-branch run and
confirm each node carries all listed fields and that children are referenced by
identifier.

**Acceptance Scenarios**:

1. **Given** a run with at least one branch, **When** the renderable form is
   produced, **Then** every checkpoint appears once with its identifier, index,
   instruction, parent, children, state, sandbox identifier, and creation time.
2. **Given** the renderable form, **When** a consumer reads it, **Then** no
   further traversal of the run is needed to draw the tree.

---

### Edge Cases

- **Two branches created from one parent within the same second.** Both children
  receive distinct stable identifiers regardless of timestamp resolution; the
  parent lists both, in creation order; a shared or equal creation time is
  permitted and does not merge, reorder, or drop either child.
- **The head is moved to a checkpoint whose sandbox has since been released.**
  The move is refused, or the checkpoint is first re-derived to a live state by a
  later feature; the model never leaves the head pointing at a checkpoint that
  reports itself not restorable. A released checkpoint is not a valid head
  target.
- **A step completes but its sandbox is destroyed before the checkpoint is
  written.** The checkpoint is still recorded for that step with its index,
  instruction, and completion state, but with no associated runtime state; it is
  marked unreachable and is not restorable. No step is lost from the ordered
  sequence.
- **A run has a single step and it fails.** The tree holds the root plus one
  checkpoint whose completion state is a failure; that branch's terminal outcome
  is "failed"; the root checkpoint remains present and, if it has runtime state,
  restorable.
- What happens when a checkpoint identifier is requested that was never issued?
  The lookup returns nothing; it does not fabricate a checkpoint.
- What happens when the renderable form is produced for a run with only the root?
  It contains exactly one node, the root, with an empty children list and the
  head pointing at it.
- What happens when a branch is abandoned and then inspected much later? Its
  checkpoints remain in the tree with their recorded states; only the branch
  terminal outcome reads "abandoned"; nothing is deleted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001-01**: The system MUST represent a run as an ordered sequence of steps,
  each with an index, an instruction, and a completion state.
- **FR-001-02**: The system MUST record a checkpoint on completion of each step,
  associating that step with the runtime state that produced it (a reference to
  the captured sandbox state, when one exists).
- **FR-001-03**: The system MUST assign every checkpoint a stable identifier that
  remains valid and unchanged for the lifetime of the run.
- **FR-001-04**: The system MUST permit a checkpoint to have multiple children,
  forming a tree rather than a list; creating a child MUST NOT alter the parent's
  own fields other than appending to its child list.
- **FR-001-05**: The system MUST designate exactly one checkpoint as the current
  head of the run at any time.
- **FR-001-06**: The system MUST record, for every checkpoint, its parent
  identifier (null only for the root), the sandbox identifier associated with it,
  and the time it was created.
- **FR-001-07**: The system MUST expose the full tree in a single form renderable
  without further computation — each node carrying its identifier, index,
  instruction, parent, children, state, sandbox identifier, creation time,
  captured outcome, and rationale.
- **FR-001-08**: The system MUST mark each checkpoint as live, released, or
  unreachable, MUST expose a restorability check, and MUST NEVER present a
  released or unreachable checkpoint as restorable or as a valid head target.
- **FR-001-09**: The system MUST record the terminal outcome of a run branch as
  succeeded, failed, or abandoned, readable as a property of the branch without
  inspecting individual steps; a still-advancing branch has no terminal outcome.

### Non-Functional Requirements

- **NFR-001-01**: Every tree operation — add, lineage, renderable form, head
  designation, state marking, restorability, terminal outcome — MUST be a pure
  function over in-memory state, testable with no runtime, network, or credential
  dependency.
- **NFR-001-02**: The tree MUST remain structurally correct — every non-root
  checkpoint reachable from the root, every parent link resolving, exactly one
  head, no orphan — when a step fails, when a branch is abandoned, and when two
  branches are created from the same parent.
- **NFR-001-03**: Identifier assignment MUST NOT depend on timestamp resolution;
  two checkpoints created in the same clock tick MUST still receive distinct
  identifiers.

### Key Entities

- **Run**: The whole tree for one agent execution. Holds all checkpoints, their
  creation order, and the single head. Owns the pure operations over the tree.
- **Step**: One unit of work within the run, identified by its ordinal index,
  carrying an instruction and a completion state. Realised as a checkpoint.
- **Checkpoint**: A node in the run tree. Carries: a stable identifier; the step
  index and instruction; a parent identifier (null for the root); a list of child
  identifiers; a state (live | released | unreachable); the associated sandbox
  identifier; a reference to the captured runtime state, when one exists; a
  creation time; a captured outcome (from Specification 002); and a stated
  rationale (from Specification 002).
- **Head**: The single checkpoint the run currently sits at. Exactly one at all
  times.
- **Checkpoint State**: `live` (present and usable), `released` (its runtime
  state has been deliberately freed), `unreachable` (its runtime state was lost
  or never existed). Only `live` with runtime state is restorable.
- **Branch**: A path of checkpoints from the root (or a branch point) forward
  along a single line of children. Carries a terminal outcome once it stops
  advancing.
- **Branch Terminal Outcome**: `succeeded` | `failed` | `abandoned`, or absent
  while the branch still advances.
- **Renderable Tree**: The single self-contained form of the whole tree that a
  viewer consumes directly — nodes with all their fields, children referenced by
  identifier, and the head named.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A checkpoint's identifier, recorded at creation, still resolves to
  the same checkpoint after the run has advanced an arbitrary number of further
  steps — 100% stable across a run's lifetime.
- **SC-002**: For any checkpoint, its root-to-node lineage is returned in correct
  order in a single call, with no traversal required of the caller.
- **SC-003**: A parent with two children created from it lists both, in creation
  order, and its own index, instruction, and state are unchanged by either
  creation.
- **SC-004**: Exactly one checkpoint is the head at every observable moment of a
  run — never zero, never two.
- **SC-005**: 0% of restore-target listings contain a released or unreachable
  checkpoint; 100% of live checkpoints with runtime state are offered.
- **SC-006**: Every branch that has stopped advancing reports exactly one
  terminal outcome of succeeded, failed, or abandoned; every still-advancing
  branch reports none.
- **SC-007**: The renderable form of a multi-branch run contains every checkpoint
  exactly once with all required fields, and a viewer can draw the tree from it
  with no additional queries.
- **SC-008**: All tree operations pass their tests with no network, no
  credentials, and no sandbox runtime present.
- **SC-009**: Two checkpoints created within the same clock second have distinct
  identifiers in 100% of trials.
- **SC-010**: After a run where a step fails, a branch is abandoned, and two
  branches share a parent, the tree passes a structural-integrity check (all
  nodes reachable, all parent links resolve, one head, no orphan).

## Assumptions

- **The run is single-process and in-memory.** Persisting the tree across process
  restarts is out of scope; the tree lives for the lifetime of the run.
- **"Completion state" of a step is distinct from "checkpoint state".** A step's
  completion state describes how the step ended (e.g. succeeded / failed, as
  produced by Specification 002); a checkpoint's state (live / released /
  unreachable) describes whether its runtime state can still be returned to.
- **The root checkpoint is synthetic** — it represents the run's starting point,
  has no instruction of its own, a null parent, and index zero.
- **Identifiers are opaque and locally generated** — short, unique within the
  run, not derived from time, not meaningful to parse. They do not need to be
  globally unique or survive the process.
- **"The runtime state that produced a step"** is the captured sandbox snapshot
  reference from Specification 000's port; this feature stores the reference, it
  does not create or restore snapshots.
- **A "branch" for the terminal-outcome requirement** is the forward path from a
  branch point (or the root) along one line of children — the same notion
  Specifications 004 and 005 use. This feature records the outcome; deciding
  "abandoned" is driven by Specification 005's promotion.
- **Head movement is performed by other features** (rewind in a later
  specification, promotion in 005). This feature defines what a valid head is and
  refuses an invalid one; it does not itself script head moves.
- **Creation time is wall-clock**, recorded when the checkpoint is added, stored
  for display and ordering tie-breaks only — never as an identifier or a
  correctness input.

## Out of Scope

- Persistence beyond process lifetime (no database, no file store for the tree).
- Concurrent editing of one run by multiple users.
- Branch merging — combining two branches into one.
- Creating, capturing, or restoring sandbox snapshots (Specification 000 / a
  later rewind specification).
- Executing steps or capturing their evidence (Specification 002).
- Creating branches or choosing between them (Specifications 004 and 005).
- Any user interface, including the timeline console that consumes the renderable
  form.
