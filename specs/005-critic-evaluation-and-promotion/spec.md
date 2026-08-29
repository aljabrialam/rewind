# Feature Specification: Critic Evaluation and Promotion

**Feature ID**: `005-critic-evaluation-and-promotion`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Evidence-Based Selection

**Business Actors**: Strategist agent; Critic agent; Orchestrator

**Input**: User description: "Judge the competing branches against the evidence their own sandboxes produced, promote one as the new head of the run, and release the rest."

## Business Context

### Business Goal

Judge the competing branches against the evidence their own sandboxes produced,
promote one as the new head of the run, and release the rest.

### Business Value

This closes the loop. An agent that proposes, executes, is judged on observed
results, and continues from the winner is a feedback system rather than a text
generator — which is the distinction the Innovation criterion draws explicitly.

### Dependencies

- **Specification 000 — Sandbox Capability Contract**: losing branch sandboxes
  are released through the capability port's declared destroy; runtime failures
  during release carry the port's error classification.
- **Specification 001 — Run and Checkpoint Model**: promotion moves the run head
  through the model's head mechanism; losers are marked `released` while staying
  in the tree; the verdict is recorded against a checkpoint; the branch terminal
  outcome is set.
- **Specification 002 — Step Execution and Evidence**: the critic is reached
  through the same reasoning port as the strategist, and its response is subject
  to the same structured-schema rejection.
- **Specification 004 — Branch Fan-Out**: the fan-out produces the child
  checkpoints this feature judges — each with independent captured evidence and
  its own snapshot, and no live sandbox by the time the verdict is requested.
- **Existing path**: `Engine.promote(winner, losers)` and
  `rank_by_evidence(branches)` exist; `promote` carries a *provisional* change
  from Specification 004 (re-derive the winner from its own snapshot, since
  fan-out destroys branch sandboxes). This specification formalises promotion and
  adds the critic.
- **Specification 008 territory**: the critic is the reasoning role most suited
  to self-hosting; this feature routes it through the shared reasoning port so
  that later routing is a configuration change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The winner is chosen on evidence and becomes the head (Priority: P1)

After a fan-out, the orchestrator submits every branch's captured evidence — exit
status, output, elapsed time — to a reasoning agent acting as critic. The critic
returns a structured verdict: which branch it chose, a score for every branch,
and a stated reason that cites the evidence. The chosen branch becomes the new
head of the run; the others are released.

**Why this priority**: This is the loop closing. Without an evidence-based choice
that moves the head, the fan-out is three dead ends.

**Independent Test**: Run a fan-out where the branches produce clearly different
evidence; submit it for a verdict; confirm the verdict names a real branch with a
score for each and an evidence-citing reason, confirm that branch is the head
afterwards, and confirm the others are marked released.

**Acceptance Scenarios**:

1. **Given** a set of branch checkpoints with independent evidence, **When** the
   verdict is requested, **Then** what is submitted to the critic is the captured
   evidence of each branch, not any agent's description of what it did.
2. **Given** the critic returns a well-formed verdict naming a real branch with a
   score per branch and an evidence-citing reason, **When** the verdict is
   applied, **Then** the named branch is the run head and every other branch is
   marked released.
3. **Given** a completed promotion, **When** the run tree is inspected, **Then**
   every branch checkpoint — winner and losers — is still present with its
   identifier, instruction, and evidence.

---

### User Story 2 - A malformed verdict is rejected, and the run still moves (Priority: P1)

If the critic's response is not a well-formed verdict — it names a branch that
does not exist, or omits a score for any branch, or is otherwise not the required
structure — the system rejects it and falls back to a deterministic ranking over
exit status. Either way a winner is promoted; the run does not stall on a bad
verdict.

**Why this priority**: Constitution Article IX requires the loop to run without
depending on a model being reachable or correct. A demo that hangs because the
critic returned junk is a demo that fails.

**Independent Test**: Feed the system a verdict that names a non-existent branch,
and separately one that omits a score; confirm each is rejected, the deterministic
fallback runs, a winner is promoted, and the result records that the fallback was
used.

**Acceptance Scenarios**:

1. **Given** a verdict naming a branch identifier that is not among the branches,
   **When** it is validated, **Then** it is rejected and the deterministic
   fallback is used.
2. **Given** a verdict missing a score for one of the branches, **When** it is
   validated, **Then** it is rejected and the deterministic fallback is used.
3. **Given** the critic cannot be reached at all, **When** the verdict is
   requested, **Then** the deterministic fallback runs and a winner is promoted.
4. **Given** any fallback path was taken, **When** the result is read, **Then**
   it records that the fallback was used and why.

---

### User Story 3 - The reason for the choice stays inspectable (Priority: P2)

The verdict — the winner, the per-branch scores, the reason, and whether the
fallback was used — is recorded against the parent checkpoint the branches came
from. Anyone looking at the run later can see why that branch was chosen.

**Why this priority**: Constitution Article X — a verdict displayed without the
evidence and reasoning behind it is a defect. The console reads this; a judge
asking "why that one?" gets an answer from the record.

**Independent Test**: Apply a verdict; then read the parent checkpoint and
confirm it carries the winner, the scores, the reason, and the fallback flag.

**Acceptance Scenarios**:

1. **Given** a verdict has been applied, **When** the parent checkpoint is read,
   **Then** it carries the chosen branch, the per-branch scores, the stated
   reason, and whether the fallback was used.
2. **Given** a further fan-out and verdict from the new head, **When** the
   earlier parent checkpoint is read, **Then** its recorded verdict is unchanged.

---

### User Story 4 - The loop runs more than once (Priority: P2)

The promoted head can itself be the origin of a further fan-out. Propose → execute
→ judge → promote → fan out again is a cycle that can repeat within one run.

**Why this priority**: "Closes the loop" means the loop can turn again. A single
proposal-and-judge is a one-shot, not a feedback system.

**Independent Test**: Fan out from a checkpoint, promote a winner, then fan out
from that winner and promote again; confirm both promotions moved the head and
both verdicts are recorded against their respective parents.

**Acceptance Scenarios**:

1. **Given** a branch has been promoted to head, **When** a fan-out is requested
   from it, **Then** it proceeds — the promoted head is a valid fan-out origin.
2. **Given** two rounds of fan-out and promotion, **When** the run tree is
   inspected, **Then** each round's verdict is recorded against that round's
   parent and the head is the second round's winner.

---

### User Story 5 - Losing sandboxes are released, on every path (Priority: P1)

Every losing branch's sandbox is released after the verdict — on the critic path
and the fallback path alike. A release that fails at the runtime is surfaced with
its classification and does not stop the other releases or the promotion.

**Why this priority**: Constitution Article XII — an exhausted concurrency quota
during the demonstration is the failure mode. A promotion that leaves two loser
sandboxes running blocks the next round.

**Independent Test**: Apply a verdict with three branches; confirm the two losers'
sandboxes are released and the winner's is not; inject a failing release for one
loser and confirm the other loser and the winner are still handled and the
failure is reported.

**Acceptance Scenarios**:

1. **Given** a verdict promoting one of three branches, **When** it is applied,
   **Then** the two losing branches' sandboxes are released and their checkpoints
   are marked released.
2. **Given** releasing one loser's sandbox raises at the runtime, **When**
   promotion continues, **Then** the other loser is still released, the winner is
   still promoted, and the failed release is reported with its classification.
3. **Given** the fan-out already destroyed the branch sandboxes (Specification
   004), **When** promotion runs, **Then** it does not error on an
   already-absent sandbox — release is idempotent.

---

### Edge Cases

- **Every branch fails; there is no clear winner.** The system still produces a
  result: the deterministic fallback ranks the branches (all non-zero exits — it
  orders by exit status then elapsed time) and promotes the least-bad one, or, if
  configured to, promotes nothing and records "no viable branch" with the
  evidence. Either way the losers are released and a reason is recorded; the run
  does not hang waiting for a good outcome that will not come.
- **Two branches produce identical evidence.** The critic may choose either; the
  fallback breaks the tie deterministically (lowest branch index, then lowest
  identifier) so a rehearsed run is reproducible. The recorded reason notes the
  tie.
- **The critic names a branch that was destroyed after a capacity error.** That
  branch has a checkpoint (a fan-out records one even for a branch that could not
  run — Specification 004) but no usable snapshot. Naming it is treated as
  naming a non-existent viable branch: the verdict is rejected and the fallback
  runs, which will not pick a branch that has no snapshot to become head from.
- **The critic returns valid structure but a reason that cites no evidence.**
  The verdict is accepted as structurally valid but flagged: the recorded result
  marks the reason as "unsupported — no evidence cited", the promotion still
  proceeds on the chosen branch and scores, and the flag is visible in the
  record so the console and a reviewer can see the critic did not justify itself.
- **The reasoning endpoint times out mid-verdict during a live demonstration.**
  The timeout is a critic-unavailable condition: the deterministic fallback runs
  within a bounded time, a winner is promoted, and the result records
  "critic timed out — fallback used". The demonstration does not stall on the
  hung call.
- **A branch is still running when the verdict is requested.** Promotion refuses
  to judge an incomplete set — it either waits a bounded time for the branch to
  reach a terminal state, or excludes it from the verdict and records that it was
  excluded because it had not finished. It never scores a branch on partial
  evidence.
- **The promoted branch's sandbox is released before it becomes head.** The
  winner has no live sandbox at verdict time by design (Specification 004
  destroys branch sandboxes). Promotion re-derives the winner from its own
  snapshot and installs that as the head's working sandbox; if the re-derivation
  fails at the runtime, promotion reports it with its classification and does not
  leave the run headless — the head stays where it was and the failure is
  surfaced.
- What happens when the branch set passed to the verdict is empty? The request
  is refused — there is nothing to judge; the head is unchanged and the reason
  records "no branches".
- What happens when the branch set has exactly one branch? It is promoted
  directly if it has a snapshot; no critic call is made and the result records
  "single branch — promoted without a verdict".
- What happens when a further fan-out is requested from a *loser* checkpoint
  (marked released) rather than the promoted head? It is refused for the same
  reason a released checkpoint cannot be restored (Specification 001 / 003) —
  released checkpoints are not valid fan-out origins.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-005-01**: The system MUST submit every branch's captured execution
  evidence — exit status, output, elapsed time — to a reasoning agent acting as
  critic, and MUST NOT substitute any agent's self-description of an outcome for
  that evidence.
- **FR-005-02**: The system MUST require the critic's verdict in a structured
  form containing: a chosen branch identifier, a numeric score for **every**
  branch in the set, and a stated reason. The reason SHOULD cite the evidence;
  a reason that cites no evidence is accepted structurally but flagged in the
  recorded result (see Edge Cases).
- **FR-005-03**: The system MUST reject a verdict that (a) names a branch not in
  the submitted set, (b) names a branch that has no snapshot to become head from,
  (c) omits a score for any branch in the set, or (d) is not the required
  structure — and on any rejection MUST proceed to the fallback of FR-005-07.
- **FR-005-04**: The system MUST promote the chosen branch to be the head of the
  run through the Specification 001 head mechanism, re-deriving its working
  sandbox from its own snapshot; if that re-derivation fails at the runtime, the
  system MUST report the failure with its classification and MUST leave the head
  where it was rather than headless.
- **FR-005-05**: The system MUST release the sandboxes of every branch not
  chosen and MUST mark those branch checkpoints `released` with a terminal
  outcome of `abandoned`, while preserving them — identifier, instruction,
  evidence, snapshot — in the tree. Release MUST be idempotent (an
  already-absent sandbox is not an error) and MUST continue for the remaining
  losers when one release raises, reporting each failure with its classification.
- **FR-005-06**: The system MUST record the verdict — chosen branch, per-branch
  scores, stated reason, any reason-unsupported flag, and whether the fallback
  was used — against the parent checkpoint the branches descend from, such that
  it remains readable after further rounds and is not overwritten by a later
  round's verdict.
- **FR-005-07**: The system MUST fall back to a deterministic ranking — ordering
  branches by exit status ascending, then by elapsed time ascending, then by
  branch index, then by identifier — when the critic is unavailable, times out
  within a bounded wait, or returns a rejected verdict, and MUST record that the
  fallback was used and the triggering reason.
- **FR-005-08**: The system MUST permit the promoted head to be the origin of a
  further fan-out, so the propose-execute-judge-promote loop can run more than
  once within a run; a released (loser) checkpoint MUST NOT be a valid fan-out
  origin.
- **FR-005-09**: The system MUST require every branch in the set to have reached
  a terminal state before a verdict is produced; a branch still running MUST be
  waited on for a bounded time and then excluded from the verdict with that
  exclusion recorded — it MUST NOT be scored on partial evidence.
- **FR-005-10**: The system MUST refuse to produce a verdict for an empty branch
  set (head unchanged, reason "no branches"), and MUST promote a single-branch
  set directly without a critic call when that branch has a snapshot, recording
  "single branch — promoted without a verdict".

### Non-Functional Requirements

- **NFR-005-01**: The verdict MUST be reproducible from a recorded fixture for
  rehearsal — the same recorded critic response over the same branch set yields
  the same promotion and recorded result.
- **NFR-005-02**: The deterministic fallback ranking MUST be a pure function over
  the branches' evidence, testable with no reasoning agent, no network, and no
  credentials, and MUST be total — it returns an ordering for any non-empty
  branch set, including one where every branch failed.
- **NFR-005-03**: The critic call MUST complete or fall back within a bounded
  wall-clock time that leaves room for the rest of a two-minute live
  demonstration; a hung reasoning endpoint MUST NOT stall the promotion past that
  bound.
- **NFR-005-04**: Promotion MUST behave identically in its ordered set of port
  operations against the live runtime and against the fake, and MUST run fully
  offline against the fake with a fixture-backed critic.

### Key Entities

- **Branch Set**: The child checkpoints of one fan-out, each with its own
  evidence and snapshot and no live sandbox, submitted together for a verdict.
- **Evidence Bundle**: What is sent to the critic for each branch — its exit
  status, its output, its elapsed time, and its identifier. Contains no agent
  self-description.
- **Verdict**: The critic's structured response — `chosen` (a branch identifier),
  `scores` (a number for every branch in the set), `reason` (a string). Subject
  to the same schema rejection as any reasoning response (Specification 002).
- **Verdict Record**: What is stored against the parent checkpoint — the chosen
  branch, the per-branch scores, the reason, a `reason_unsupported` flag, a
  `fallback_used` flag with its trigger, and the timestamp. Immutable once
  written for that round.
- **Deterministic Ranking**: The pure fallback — an ordering of the branch set by
  exit status, then elapsed time, then branch index, then identifier — used when
  the critic path does not yield a valid verdict. Total over any non-empty set.
- **Promotion**: The act of making the chosen branch the head — re-deriving its
  sandbox from its snapshot, moving the head, releasing the losers, recording the
  verdict.
- **Critic**: The reasoning agent in the judging role, reached through the shared
  reasoning port (Specification 002); has a live implementation and a
  fixture-replay implementation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of what is submitted to the critic for a branch is that
  branch's captured evidence; 0% is any agent's self-description.
- **SC-002**: 100% of accepted verdicts contain a chosen branch that exists in
  the set and a score for every branch; verdicts missing either are rejected.
- **SC-003**: After a valid promotion, the chosen branch is the run head in 100%
  of cases, and every non-chosen branch is marked `released` with `abandoned` as
  its terminal outcome.
- **SC-004**: 100% of branch checkpoints — winner and losers — remain in the tree
  after promotion with their identifier, instruction, evidence, and snapshot
  intact; the structural-integrity check passes.
- **SC-005**: When the critic is unavailable, times out, or returns a rejected
  verdict, a winner is still promoted in 100% of cases and the result records the
  fallback and its trigger.
- **SC-006**: The deterministic ranking returns a total ordering for 100% of
  non-empty branch sets, including all-failed sets, with a reproducible tie-break.
- **SC-007**: The verdict record against a parent checkpoint is unchanged by any
  later round's verdict — 0% overwrite.
- **SC-008**: Two rounds of fan-out and promotion both move the head and both
  record a verdict against their own parent; the loop runs more than once.
- **SC-009**: On every path, every losing sandbox is released and the winner's is
  not; a failing release does not prevent the other releases or the promotion,
  and is reported with its classification.
- **SC-010**: The critic call plus any fallback completes within the declared
  bounded time in 100% of runs; a hung endpoint never stalls promotion past that
  bound.
- **SC-011**: The same recorded critic response over the same branch set produces
  an identical promotion and verdict record on repeated offline runs.

## Assumptions

- **A "branch identifier" in the verdict is the child checkpoint's identifier**
  from Specification 001 — opaque, runtime-adjacent, compared by equality. The
  critic is given the set of identifiers it must score.
- **"Score" is a single number per branch**, higher meaning better; the scale is
  the critic's to choose and is not interpreted beyond ranking. A missing or
  non-numeric score for any branch is a rejection.
- **"Cites evidence" is a soft check.** The system does not parse the reason for
  correctness; it checks whether the reason references any branch's evidence at
  all (an exit code, output text, an elapsed figure, a branch identifier). A
  reason with none of these is flagged `reason_unsupported`, not rejected.
- **The bounded wait for the critic** is a few seconds against the live endpoint;
  the exact number is a planning decision. On the fixture-replay path it is
  effectively instant.
- **The bounded wait for a still-running branch** (FR-005-09) is short — a branch
  that has not finished by then is excluded, not scored.
- **"No viable branch" behaviour for the all-failed case** defaults to promoting
  the least-bad branch (it still has a snapshot and can be continued or
  re-branched); promoting nothing is a configurable alternative. Either way the
  losers are released and a reason is recorded.
- **The verdict is recorded against the parent checkpoint** using Specification
  001's mechanism for attaching a verdict to a checkpoint; each round's parent is
  distinct, so records do not collide.
- **Promotion re-derives the winner from its snapshot** (the provisional
  Specification 004 behaviour, formalised here) because the fan-out destroys
  branch sandboxes; the winner had no live sandbox at verdict time.
- **The critic uses the same reasoning port as the strategist** (Specification
  002), so its response goes through the same structured-schema validation and
  its endpoint can later be routed independently (Specification 008) with no
  change here.
- **This feature does not choose *when* to stop the loop** — how many rounds to
  run is the orchestrator's or the developer's call; this feature makes each
  round's judge-and-promote correct and repeatable.

## Out of Scope

- Learning across runs — no memory of past verdicts influences a future one.
- Merging branch results — the winner is one branch, not a combination.
- Cost-weighted selection — token cost, wall-clock cost, or credit cost are not
  inputs to the choice (elapsed time is only a fallback tie-break, not a
  weighting).
- Deciding how many rounds of the loop to run, or when to stop.
- Self-hosting or independently routing the critic endpoint (Specification 008).
- Defining the checkpoint tree, the head mechanism, the `released` state, or how
  a verdict attaches to a checkpoint (Specification 001).
- Producing the branch set — that is the fan-out (Specification 004).
- Any user interface for showing the verdict (Specification 006).
