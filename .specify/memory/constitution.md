# Constitution — Rewind

**Version:** 1.0.0
**Ratified:** [TIME, on the day, by the whole team out loud]
**Scope:** One project, one day. **Hard stop 16:30 SGT. Freeze 15:00.**
**Status:** Amendments after ratification require the team to stop and agree. That friction is intentional.

> Paste this entire file into `/speckit.constitution` before the first
> `/speckit.specify`. Everything specified afterwards inherits it.

---

## Preamble

This is a hackathon constitution, not a product one. It inherits the portable governance core used on Bantáy and ALJ — specification first, requirement traceability, scope discipline, living documentation — and deliberately suspends the parts that only pay off over months. Where the standing methodology and the clock conflict, this document says which wins, so nobody relitigates it at 14:00 under pressure.

The failure mode being governed against is not bad code. It is **a beautiful architecture with nothing to show at 16:30.**

---

## Article I — Demo Primacy

The deliverable is a **two-minute live demonstration**, not a repository. Every task is judged by one question: does this change what the judges see? Work that does not reach the screen is out of scope, however correct it is.

The demo script is written **before** the code, at G1. If the 120 seconds cannot be written, there is not yet a project.

## Article II — Specification First, Time-Boxed

No implementation before the specification is written and the scope has been said out loud. **Specification is capped at 30 minutes.** The cap is part of the rule — an unfinished spec at the cap is closed with explicit assumptions rather than extended.

Specifications state **what and why**. Technology names belong in the plan. The single declared exception is the sandbox runtime, which the event makes a genuine constraint.

## Article III — The Spine Rule

Identify the single riskiest technical assumption and prove it with the ugliest possible script **before any feature work begins**. No UI, no abstraction, no error handling. The spine for this project is: *does a live sandbox fork and does the child carry the parent's state on this account.*

If the spine does not hold, Article VII applies immediately — not after an hour of trying to make it hold.

## Article IV — Nothing Is Invented

No capability of an external runtime may be used unless it has been observed on this account, in this session, and recorded in the capability map. Documentation and recollection are both insufficient evidence.

All runtime access passes through a single port. No feature code imports a vendor SDK directly.

## Article V — Vertical Slices Only

Build end-to-end thin, then thicken. From 13:00 there must always exist a runnable path from input to visible output. A component that cannot be demonstrated in isolation is not started until the spine is complete.

**No refactoring after 15:00. None.**

## Article VI — Traceability and the Testing Pyramid

Every demo beat traces to a requirement, every requirement to a task and a **named test**, every task to an owner. **Traceability is the sufficiency gate, not a coverage percentage** — coverage floors are suspended for the day; the mapping is not. An unmapped requirement is not done, regardless of whether code exists.

The pyramid is preserved in shape, compressed in volume:

| Layer | What | Count | When |
|---|---|---|---|
| Base — pure logic | Anything transforming data with no network: schema validation, tree math, ranking, aggregation, cleanup guarantees | ~6–12 tests, sub-second | Alongside the code |
| Middle — contract | One per external dependency, proving it still behaves as assumed | 2–3 tests | At G2, re-run at 15:00 |
| Top — E2E | The demonstration path itself, scripted | 1 | Twice before 15:45 |

### The Seam Rule (non-negotiable)

Every external dependency sits behind an interface with a **fake**: a sandbox port with an in-memory implementation, a reasoning port with recorded fixtures. This is not testing ceremony — it is how the team keeps working when the venue network fails, how the base layer stays fast enough to run, and how the fallback project becomes a configuration change instead of a rewrite. Any teammate must be able to run the whole orchestrator offline. **If the seam does not exist by 13:00, the project is one network failure from having nothing to show.**

### What the contract tests are for

Not correctness — **drift and credentials.** SDK names change, tokens expire, tiers throttle. They are a twenty-second answer to "is it us or is it them", and running them at 15:00 catches an expired key before the judges do rather than during.

### What is not tested

UI rendering, error paths outside the demo script, and anything already declared out of scope. A test that prevents a bug more cheaply than it costs is discipline; any other test is theatre.

## Article VII — Scope Discipline and the Kill Switch

Declared scope is a ceiling, never a floor. Cutting is the default response to trouble; extending requires an explicit gate.

| Time | Checkpoint | If not met |
|---|---|---|
| 11:50 | Spine proven | Switch to the declared fallback project. No debate |
| 13:00 | Ports and fakes exist | Stop feature work until they do |
| 14:00 | Vertical slice runs end to end | Collapse the critic to a deterministic ranking; keep the loop |
| **15:00** | **Feature freeze** | Stop building. Unfinished work becomes roadmap |
| 15:45 | Rehearsed twice, backup recorded | Simplify the path until it survives two clean runs |

## Article VIII — Sponsor Integration Is Load-Bearing

The criterion as stated is *"Sponsor Usage: clever integration with Daytona."* The sandbox runtime is the graded integration; the reasoning provider is additive. No hour is spent on additive integrations until the graded one is demo-complete.

*Clever* is the operative word: a primitive most teams ignore beats generic code execution. If an integration is reduced to decoration by time pressure, say so plainly in the demo. Overclaiming to judges who built the platform is a losing move.

**Additive integrations carry a stop line.** The event requires the sponsored products to be integrated, so a second sponsor is delivered through Specification 008 — one reasoning role routed to a self-hosted endpoint on independent GPU infrastructure, behind the same port, with automatic fallback. It is provisioned as a background task from 12:00 and assessed once, at 14:30. If it is not serving by then it is deleted from the configuration and stated honestly in the demonstration. **No additive integration may be on the critical path of the demonstration, and none may consume an hour that the graded integration needs.**

## Article IX — Multi-Agent Feedback Loop

The Innovation criterion as stated: *stepping past traditional prompt-based text wrappers; executing smart multi-agent feedback loops.* This is a design requirement.

The system must contain **at least one closed loop** in which an agent's output is judged — by another agent, or by execution evidence from a sandbox — and that verdict changes what happens next. A single reasoning call whose output is displayed scores zero here regardless of polish.

The loop is stated in one sentence in the specification. If it cannot be written, the system is a wrapper.

## Article X — Evidence Over Assertion

Decisions are made against observed execution results — exit status, output, elapsed time — never against a model's account of what it did. Wherever both appear, evidence and rationale are visually distinguished. A verdict displayed without the evidence behind it is a defect.

## Article XI — Proven In The Runtime, Live

The Completeness criterion as stated: *functional MVP execution, built and proven within the sandbox runtime during live demos.* The demonstration therefore runs **live against real sandboxes on stage**.

The backup recording is insurance against catastrophe, not the plan; presenting it forfeits this criterion. Design the path to survive a hostile network instead: pre-warmed sandboxes, seeded workspace, short wall-clock, reasoning responses replayed from fixtures. The sandbox lifecycle is the one thing that must be genuinely live.

## Article XII — Resource Hygiene

Every sandbox is created with an inactivity stop interval and a deletion interval, and every operation that creates one destroys it on both the success and failure path. Live sandbox count is visible on screen at all times. Credits are not the constraint; an exhausted concurrency quota during the demonstration is.

## Article XIII — Honest Framing

Describe what the system does, not what it would do given a week. Roadmap is labelled roadmap, in the README and out loud. This is the Truth-Calibrated Claims principle carried over unchanged, and it matters more here: the judges wrote the platform and will recognise a hand-wave instantly.

## Article XIV — Living Evidence

The repository is public from the first commit. Each gate is recorded as a git tag at the moment it passes. `docs/gates.md` holds one line per gate with its time. A methodology with no evidence of having been followed is a blog post.

---

## Gates

| Gate | When | Passes when | Recorded as |
|---|---|---|---|
| **G1 — Scope** | by 12:05 | Specifications written, delivery order fixed, demo script readable aloud in 120 seconds | tag `g1` |
| **G2 — Spine** | by 13:00 | Riskiest assumption proven by running code; ports and fakes pass their tests | tag `g2` |
| **G3 — Freeze** | 15:00 | Demo path ran clean twice; backup recorded; contract tests re-run | tag `g3` |

A gate passes by saying it out loud to the team. Thirty seconds each.

---

## Amendments

Record inline with a timestamp and one line of reasoning. This file becomes the retrospective.

- `[HH:MM]` —
