# Feature Specification: Demo Harness

**Feature ID**: `007-demo-harness`

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Business Capability**: Demonstration Assurance

**Business Actors**: Presenter; Continuous integration pipeline

**Input**: User description: "Execute the demonstration path end to end, unattended and repeatably, with the sandbox runtime live and the reasoning layer replayed."

## Business Context

### Business Goal

Execute the demonstration path end to end, unattended and repeatably, with the
sandbox runtime live and the reasoning layer replayed.

### Business Value

The demonstration is the deliverable. A path that has run identically twice is
the only evidence that it will run a third time in front of judges, on a network
nobody controls.

### Dependencies

This feature is the top of the testing pyramid — the scripted end-to-end
demonstration path. It composes, in order, every capability below it:

- **Specification 000 — Sandbox Capability Contract**: all sandbox interaction
  goes through the single port; resource hygiene (stop/delete intervals, destroy
  on every path) is inherited.
- **Specification 001 — Run and Checkpoint Model**: the path builds a run tree.
- **Specification 002 — Step Execution and Evidence**: steps execute in live
  sandboxes and capture evidence; the reasoning port's fixture-replay
  implementation serves the path.
- **Specification 003 — Restore to Checkpoint**: the path rewinds to an earlier
  checkpoint.
- **Specification 004 — Branch Fan-Out**: the path fans out competing branches.
- **Specification 005 — Critic Evaluation and Promotion**: the path judges the
  branches on their evidence and promotes a winner (the critic is also served
  from a fixture).
- **Specification 006 — Timeline Console**: the path writes `fixtures/tree.json`,
  which the console renders; the harness does not drive the console.
- **Existing version**: `demo.py` already runs an approximation of this path.
  This feature governs and hardens it into an unattended, budgeted,
  leak-checked harness.

Per the constitution this path is run twice before the freeze and the sandbox
lifecycle must be genuinely live (Article XI).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command runs the whole path, unattended (Priority: P1)

The presenter, or a CI job, runs one command with no arguments and no prompts.
It seeds a starting workspace, executes the full path — steps, a failure, a
rewind, a fan-out, a critic verdict, a promotion — against the live sandbox
runtime, writes the console fixture, tears everything down, and exits. Nothing is
typed during the run.

**Why this priority**: This is the feature. If the path needs a human at the
keyboard, it is not rehearsal evidence and it is not CI-runnable.

**Independent Test**: Run the single command in a non-interactive shell with
credentials present; confirm it completes the full path and exits, with no
prompt and no manual step.

**Acceptance Scenarios**:

1. **Given** credentials are present and the reasoning fixtures exist, **When**
   the command is run with no arguments in a non-interactive shell, **Then** it
   executes the complete path and exits without any prompt for input.
2. **Given** the command completes, **When** its output is read, **Then** it
   shows each stage of the path — seed, steps, failure, rewind, fan-out, verdict,
   promotion, teardown — in order.
3. **Given** the command is run again immediately, **When** it completes,
   **Then** it produces the same sequence of stages and the same verdict.

---

### User Story 2 - The sandbox runtime is genuinely live (Priority: P1)

Every sandbox operation on the path — create, run, snapshot, branch, destroy —
happens against the real runtime. Nothing about the sandbox lifecycle is
simulated or stubbed on the demonstration path.

**Why this priority**: Constitution Article XI — Completeness is judged on what
is proven live. A path that quietly used the in-memory fake would be a false
demonstration.

**Independent Test**: Run the command; confirm from the run's own records that
every sandbox operation was a live-runtime call and that no in-memory substitute
was used for any sandbox step.

**Acceptance Scenarios**:

1. **Given** the harness runs, **When** its provider is inspected, **Then** it is
   the live sandbox provider, not the fake.
2. **Given** a run has completed, **When** its recorded runtime calls are
   inspected, **Then** every sandbox lifecycle operation on the path was a live
   call.
3. **Given** the harness is asked to run without sandbox credentials, **When** it
   starts, **Then** it fails immediately with a named error rather than falling
   back to a simulated runtime.

---

### User Story 3 - Reasoning is replayed, so runs are identical (Priority: P1)

Every reasoning response on the path — the strategist's continuations and the
critic's verdict — is served from a recorded fixture. Two runs produce the same
instructions, the same branches, and the same promotion. If the fixtures are
missing, the harness says so and stops.

**Why this priority**: A live reasoning call makes the path non-deterministic —
different branches, a different winner, a different wall-clock each run. Rehearsal
evidence requires the path to be repeatable.

**Independent Test**: Run the command twice; diff the two runs' stage sequences,
branch instructions, and verdicts — they match. Remove a reasoning fixture and
run again; the harness exits non-zero with a message naming the missing fixture.

**Acceptance Scenarios**:

1. **Given** the reasoning fixtures are present, **When** the path runs, **Then**
   every strategist and critic response comes from a fixture, not a live
   reasoning call.
2. **Given** two consecutive runs, **When** their branch instructions and
   verdicts are compared, **Then** they are identical.
3. **Given** a required reasoning fixture is absent, **When** the command is run,
   **Then** it exits non-zero with a message naming the missing fixture and does
   not fall back to a live reasoning call.

---

### User Story 4 - The path fits the demonstration budget (Priority: P1)

The harness reports the total wall-clock time of the path. If that time exceeds
the declared demonstration budget, the run fails — a path that took too long in
rehearsal is a failed rehearsal, reported as such.

**Why this priority**: The demonstration is two minutes. A path that reports 105
seconds passed CI but will overrun on stage. The budget check is what turns
"it worked" into "it worked in time".

**Independent Test**: Run the command; confirm it prints a total elapsed time.
Set the budget below the observed time and run again; confirm the run fails and
the failure names the budget and the actual time.

**Acceptance Scenarios**:

1. **Given** any completed run, **When** its output is read, **Then** it reports
   the total wall-clock time of the path.
2. **Given** the path completes within the budget, **When** the command exits,
   **Then** it exits zero.
3. **Given** the path exceeds the budget, **When** the command exits, **Then**
   it exits non-zero and the message names both the budget and the actual
   elapsed time.

---

### User Story 5 - First-call latency is outside the demonstrated time (Priority: P2)

Before the timer starts, the harness prepares the runtime — it creates and warms
at least one sandbox — so that the cold-start cost of the first runtime call is
paid before the demonstrated path begins and does not count against the budget.

**Why this priority**: A cold first `create` can take seconds. Paying that inside
the two minutes wastes budget the presenter needs for narration.

**Independent Test**: Run the command; confirm a preparation stage runs and
completes before the timed path starts, and that the reported elapsed time
excludes it.

**Acceptance Scenarios**:

1. **Given** the harness starts, **When** it reaches the timed path, **Then** at
   least one sandbox has already been created and exercised in a preparation
   stage.
2. **Given** the run reports its elapsed time, **When** that time is compared to
   the whole command's duration, **Then** the preparation stage is not included
   in the reported path time.
3. **Given** preparation fails at the runtime, **When** the harness reacts,
   **Then** it exits non-zero before the timed path begins, naming the failure.

---

### User Story 6 - Nothing is left running (Priority: P1)

At the end of the path — success or failure — the harness verifies that no
sandbox it created is still live. Any that remain are named in the output and the
run is treated as failed.

**Why this priority**: Constitution Article XII — an exhausted concurrency quota
during the real demonstration is the failure mode. A rehearsal that leaks a
sandbox has to be caught in rehearsal.

**Independent Test**: Run the command to completion and, separately, force a
mid-path failure; in both cases confirm the harness reports the live sandbox
count as zero at the end, and that a deliberately leaked sandbox is named and
fails the run.

**Acceptance Scenarios**:

1. **Given** a successful run, **When** the end-of-path check runs, **Then** it
   reports that the harness's provider holds zero live sandboxes.
2. **Given** a run that failed partway, **When** the harness exits, **Then** it
   still runs the leak check and still tears down every sandbox it created.
3. **Given** a sandbox the harness created is still live at the end, **When** the
   leak check runs, **Then** it names that sandbox and the run exits non-zero.

---

### Edge Cases

- What happens when the seeded workspace's failure does not reproduce — the
  "broken" step unexpectedly passes? The harness fails with a named error: the
  demonstration depends on a known failure to rewind from, and a seed that does
  not fail is a broken seed.
- What happens when the reasoning fixtures exist but have fewer entries than the
  path consumes? The harness fails when the replay is exhausted, naming which
  reasoning step ran out, rather than falling back to a live call.
- What happens when a live sandbox operation fails mid-path (the runtime returns
  a capacity or transient error)? The harness does not silently retry forever —
  it surfaces the classified error, tears down what it created, runs the leak
  check, and exits non-zero.
- What happens when the budget check passes but the leak check fails? The run is
  failed — both checks must pass for a zero exit.
- What happens when the command is run with no credentials at all? It exits
  non-zero immediately with a named error and creates nothing.
- What happens when two runs happen back to back and the first left the console
  fixture from its run? The second run overwrites `fixtures/tree.json` with its
  own output; the file always reflects the most recent run.
- What happens when the path is interrupted (the process is killed)? Teardown may
  not complete; the harness's own leak check cannot run. This is out of the
  harness's control, but a normal failure — an exception on the path — always
  reaches teardown and the leak check.
- What happens when preparation warms a sandbox but the path then needs more
  concurrent sandboxes than the account quota allows? The path's fan-out obeys
  the declared concurrency ceiling (Specification 000/004); the harness does not
  raise the ceiling to fit the demo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-007-01**: The system MUST provide a single command, taking no arguments,
  that executes the complete demonstration path end to end without any manual
  intervention or interactive prompt.
- **FR-007-02**: The system MUST execute the demonstration path against the live
  sandbox runtime through the capability port, and MUST NOT simulate, stub, or
  substitute an in-memory implementation for any sandbox operation on the path.
- **FR-007-03**: The system MUST serve every reasoning response on the
  demonstration path — strategist and critic — from recorded fixtures via the
  fixture-replay reasoning port, MUST NOT make a live reasoning call on the path,
  and MUST exit non-zero with a named error if a required fixture is missing or
  exhausted.
- **FR-007-04**: The system MUST seed a deterministic starting workspace that
  contains a reproducible failure — a passing check followed by an edit that
  breaks it — and MUST fail with a named error if that seeded failure does not
  reproduce.
- **FR-007-05**: The system MUST report the total wall-clock time of the
  demonstration path and MUST exit non-zero, naming both the budget and the
  actual time, if the path time exceeds the declared demonstration budget.
- **FR-007-06**: The system MUST prepare the runtime before the timed path begins
  — creating and exercising at least one sandbox — so that first-call latency is
  not inside the reported path time, and MUST exit non-zero before the timed path
  if preparation fails.
- **FR-007-07**: The system MUST verify, at the end of the path on both the
  success and the failure route, that the harness's provider holds zero live
  sandboxes, MUST name any that remain, and MUST treat a non-zero live count as a
  failed run.
- **FR-007-08**: The system MUST tear down every sandbox it created on both the
  success and the failure route, before it runs the leak check.
- **FR-007-09**: The system MUST require both the budget check and the leak check
  to pass for a zero exit; failing either fails the run.
- **FR-007-10**: The system MUST write the console fixture (`fixtures/tree.json`,
  Specification 006) reflecting the completed path, overwriting any prior run's
  file.

### Non-Functional Requirements

- **NFR-007-01**: The command MUST exit non-zero on any failure — a seed that
  does not fail, a missing/exhausted fixture, a runtime error, a budget overrun,
  a sandbox leak — so a rehearsal failure is unambiguous to a human and to CI.
- **NFR-007-02**: The path MUST be runnable with no interactive input — no
  prompts, no confirmations, no TTY requirement.
- **NFR-007-03**: The demonstration budget MUST be a single declared value with a
  sensible default (about ninety seconds) and MUST be overridable by
  configuration without changing the command.
- **NFR-007-04**: The harness's own logic — the budget check, the leak check, the
  seed-failure check, the stage ordering — MUST be verifiable without the live
  runtime (a pure-logic layer), separately from the live end-to-end run.

### Key Entities

- **Demonstration Path**: The ordered sequence the harness executes — seed →
  steps → observed failure → rewind → fan-out → critic verdict → promotion →
  console fixture write → teardown → leak check. The scripted E2E of the whole
  system.
- **Single Command**: The no-argument entry point. Reads only credentials and
  optional overrides from the environment. Exit code is the verdict.
- **Reasoning Fixture Set**: The recorded strategist and critic responses the
  path replays. Its presence and sufficiency are preconditions the harness
  checks.
- **Seeded Workspace**: The deterministic starting state — a small project with a
  passing test and a scripted edit that breaks it — the reproducible failure the
  path rewinds from.
- **Preparation Stage**: The pre-timer work — create and exercise at least one
  sandbox — that moves cold-start cost outside the reported path time.
- **Path Timer**: The wall-clock measurement of the demonstration path only,
  excluding preparation, compared against the demonstration budget.
- **Demonstration Budget**: The declared maximum path time (default ~90s,
  configurable). Exceeding it fails the run.
- **Leak Check**: The end-of-path verification that the harness's provider holds
  zero live sandboxes, run on every route.
- **Run Verdict**: The overall pass/fail — zero exit only if the path completed,
  the budget check passed, and the leak check passed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The single command completes the full demonstration path with zero
  manual interventions and zero interactive prompts.
- **SC-002**: Two consecutive runs produce an identical sequence of stages,
  identical branch instructions, and an identical verdict.
- **SC-003**: 100% of sandbox operations on the demonstration path are live
  runtime calls; 0% are served by an in-memory substitute.
- **SC-004**: 100% of reasoning responses on the path are served from fixtures;
  0% are live reasoning calls.
- **SC-005**: A missing or exhausted reasoning fixture causes a non-zero exit
  naming the fixture, in 100% of such cases, with no live reasoning fallback.
- **SC-006**: Every completed run reports a total path wall-clock time; a run
  whose path time exceeds the budget exits non-zero naming the budget and the
  actual time, in 100% of such cases.
- **SC-007**: The reported path time excludes the preparation stage; the
  preparation stage creates and exercises at least one sandbox before the timer
  starts.
- **SC-008**: On both the success route and a forced mid-path failure, the
  end-of-path leak check runs and every sandbox the harness created is torn down;
  a non-zero live count exits the run non-zero and names the offending sandbox.
- **SC-009**: A zero exit occurs only when the path completed, the budget check
  passed, and the leak check passed — failing any one produces a non-zero exit.
- **SC-010**: After a run, `fixtures/tree.json` reflects that run's completed
  path and can be rendered by the console.
- **SC-011**: The harness's budget/leak/seed/stage-order logic passes its tests
  with no live runtime, no network, and no credentials.
- **SC-012**: Run with no credentials, the command exits non-zero immediately
  with a named error and creates nothing.

## Assumptions

- **The single command is the existing `demo.py` entry point**, hardened — run
  with no arguments (e.g. `python demo.py`). It reads `DAYTONA_API_KEY` and
  optional overrides (`REWIND_DEMO_BUDGET`, fixture directory) from the
  environment; nothing is passed on the command line.
- **The demonstration budget defaults to about ninety seconds**, overridable by
  an environment variable, leaving roughly thirty seconds of the two minutes for
  narration and slack.
- **The seeded reproducible failure is the scripted calculator regression** the
  existing `demo.py` uses: a step writes a correct `add`, a step writes and
  passes a test, then a step "optimises" `add` into a subtraction and the test
  fails. That failing step is the rewind point.
- **"Replayed reasoning" is the Specification 002 fixture-replay reasoning port**
  serving both roles: the strategist from the recorded strategy fixtures and the
  critic from a recorded verdict fixture. Capturing those fixtures from a live
  run is a one-time prerequisite (Specifications 002 and 005); the harness only
  consumes them and fails clearly if they are absent.
- **"Prepare the runtime" means pre-creating and exercising at least one
  sandbox** — a `create` plus a trivial command — before the path timer starts,
  so the cold-start cost is outside the reported time. The warmed sandbox is
  torn down or reused; either way it is covered by the leak check.
- **The leak check is scoped to the harness's own provider** — it asserts the
  provider instance the harness used reports zero live sandboxes and surfaces any
  it still holds. It does not audit the whole account for unrelated sandboxes.
- **"No sandbox it created remains live"** is verified through the provider's own
  live-sandbox accounting (Specification 000), after teardown has run.
- **The console is not driven by the harness.** The harness writes
  `fixtures/tree.json`; whether a console is open is the presenter's choice and
  outside this feature.
- **A fully offline path already exists** (the `FAKE=1` mode of `demo.py`) and is
  retained for development, but it is explicitly **not** the demonstration path —
  the demonstration path is live-sandbox + replayed-reasoning, and the harness's
  default behaviour is that path.
- **CI runs the harness where credentials and fixtures are available**; where
  they are not, CI runs the offline pure-logic layer (NFR-007-04) instead, and
  the live harness is a manual pre-freeze step.

## Out of Scope

- Recording or presentation tooling — screen capture, slides, a teleprompter,
  the backup video.
- Any capability not already specified in 000–006 — the harness composes what
  exists; it adds no sandbox, reasoning, or tree behaviour.
- Driving or opening the timeline console (Specification 006) — the harness only
  writes the fixture the console reads.
- Retrying or self-healing a failed path — a rehearsal failure is meant to be
  seen and fixed, not papered over.
- Raising the concurrency ceiling or any account quota to make the demo fit.
- Choosing the demonstration script's content beyond the seeded calculator
  regression and the composed 003/004/005 beats.
- A graphical or interactive runner — the command is non-interactive by
  requirement.
