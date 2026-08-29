# Implementation Plan: Critic Evaluation and Promotion

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/005-critic-evaluation-and-promotion/`

**Input**: Feature specification from `specs/005-critic-evaluation-and-promotion/`

## Summary

Close the loop. After a fan-out (Spec 004), submit each branch's captured
**evidence** (exit / output / elapsed / id — no self-description) to a critic
reached through the shared reasoning port (Spec 002); require a structured
verdict (`chosen`, a `score` per branch, a `reason`); reject a verdict that names
a branch outside the set, names one with no snapshot, or omits a score, and on
any rejection — or a critic timeout / unreachable — fall back to a **total, pure
deterministic ranking** over exit status. Promote the chosen branch: re-derive
its sandbox from its own snapshot, move the head (Spec 001), release every loser
(idempotent, continue-on-failure, classified), and record the verdict against the
parent checkpoint so it stays inspectable and is never overwritten by a later
round. The promoted head is a valid fan-out origin, so the loop can turn again.

Technical approach: additive to `engine.py` and small additions to `ports.py`,
`reasoning.py`, `capabilities.py`. New: `Checkpoint.verdict` field;
`Run.record_verdict` / `get_verdict` (write-once); `reasoning.validate_verdict`;
`capabilities.CRITIC_WAIT`; `Engine.evaluate(branches, critic, …)` (evidence
bundle → bounded critic call → validate → fallback) returning a verdict result;
`Engine.judge_and_promote(branches, critic, …)` (evaluate + promote). `promote`
is formalised (verdict recording, continue-on-failure release, headless safety)
with a backward-compatible signature so `demo.py` keeps working. `rank_by_evidence`
is hardened (tie-break by index then id, a numeric `score` per branch, totality
for all-failed sets).

## Technical Context

**Language/Version**: Python 3.11+ (venv 3.14)

**Primary Dependencies**: none new — capability port (Spec 000, `destroy` +
`classify`), run tree (Spec 001), reasoning port (Spec 002), fan-out (Spec 004).
`concurrent.futures` (stdlib, already used) for the bounded critic wait. `pytest`.

**Storage**: none — in-memory run; the verdict record lives on the parent
`Checkpoint`

**Testing**: `pytest`; base layer offline against `FakeProvider` + a
canned/fixture critic; one live contract test (`@pytest.mark.live`) for
ordered-call parity and the bounded-wait budget

**Target Platform**: local dev + CI; releases + winner re-derivation run on
Daytona sandboxes live

**Project Type**: single project — internal library, `src/rewind/engine.py`

**Performance Goals**: critic call + any fallback within `CRITIC_WAIT` (a few
seconds live, instant offline — NFR-005-03); the fallback ranking is O(branches)

**Constraints**: evidence only to the critic, never self-description (FR-005-01);
fallback is pure + total (NFR-005-02); verdict record is write-once (FR-005-06 /
SC-007); release is idempotent + continue-on-failure (FR-005-05); never leave the
run headless (FR-005-04); identical ordered port ops live vs fake, fully offline
on the fake (NFR-005-04)

**Scale/Scope**: one round judges ≤ 3 branches; 10 FRs, 4 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work reaches the screen | The verdict + reason + fallback flag land on the parent checkpoint and flow through `console_fixture` to the console's Verdict block. **Pass** |
| II — Specification First | Tech names only in the plan | Spec 005 names no tech; this plan names the ports, `concurrent.futures`, `pytest`. **Pass** |
| IV — Nothing Is Invented | One port per dependency | The critic uses the **same** reasoning port as the strategist (Spec 002); releases use the declared `destroy`. No new SDK. **Pass** |
| V — Vertical Slices / no refactor | Additive | New methods + one dataclass field + a hardened pure function; `promote` keeps a backward-compatible signature; `start`/`step`/`restore`/`fan_out`/`branch_from` untouched. **Pass** |
| VI — Traceability & Pyramid + Seam Rule | FR → named test; fake for the dependency; offline; fixtures from live | Canned + fixture critic cover evaluate/reject/fallback/promote offline; the fallback ranking is the archetypal pure base-layer test. 1 live contract test. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| **IX — Multi-Agent Feedback Loop** | At least one closed loop where a verdict changes what happens next | **This is the closure.** The critic's verdict (or the fallback's) changes the head, releases branches, and enables the next round (FR-005-08). Stated in one sentence: *the critic judges the branches on their sandboxes' evidence and the winner becomes the run's next starting point.* **Pass** |
| X — Evidence Over Assertion | Decide on observed results; evidence and rationale distinct; a verdict shows its evidence | FR-005-01 forbids self-description to the critic; the verdict record carries the reason and the `reason_unsupported` flag; the fallback is exit-status only. **Pass** |
| XI — Proven In The Runtime, Live | Live sandbox lifecycle on stage | Loser releases and winner re-derivation are real port calls; offline path is rehearsal insurance. **Pass** |
| XII — Resource Hygiene | Every sandbox destroyed; ceiling respected | FR-005-05 releases every loser on every path, idempotent, continue-on-failure. **Pass** |

**Result**: No violations. Complexity Tracking empty. This feature completes the
Article IX obligation for the project.

## Project Structure

### Documentation (this feature)

```text
specs/005-critic-evaluation-and-promotion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── verdict.md          # the critic verdict schema, rejection rules, the evidence bundle
│   └── promotion.md        # promote/judge_and_promote: ordered calls, release semantics, verdict record
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/rewind/
├── ports.py           # EDIT (additive) — Checkpoint.verdict: dict | None = None
├── reasoning.py       # EDIT (additive) — Verdict dataclass; VerdictSchemaError(SchemaError);
│                      #   validate_verdict(payload, branch_ids) -> Verdict
├── capabilities.py    # EDIT (additive) — CRITIC_WAIT (bounded critic wall-clock, env-overridable)
├── engine.py          # EDIT (additive) — Run.record_verdict / get_verdict (write-once);
│                      #   Engine.evaluate(branches, critic, context="") -> dict;
│                      #   Engine.judge_and_promote(branches, critic, ...) -> dict;
│                      #   promote() formalised (record verdict, continue-on-failure release,
│                      #   headless safety); rank_by_evidence() hardened (tie-break + score + totality)
├── providers.py       # UNCHANGED
└── recording.py       # UNCHANGED (ReplayReasoner already serves a critic fixture)

tests/
├── unit/
│   └── test_critic.py          # NEW — evidence bundle, verdict reject, fallback, promote,
│                               #   write-once record, all-failed totality, second round, releases
└── contract/
    └── test_critic_contract.py     # NEW — @pytest.mark.live: ordered-call parity + CRITIC_WAIT budget

demo.py                # EDIT (additive) — judge_and_promote with a canned/fixture critic; show the
                       #   verdict reason + whether the fallback was used; keep every other beat

fixtures/
└── reasoning/critic-*.json   # NEW (live capture, spec 002 provenance) — recorded critic verdicts
```

**Structure Decision**: Single-project layout unchanged. All feature code is
additive; `promote` and `rank_by_evidence` are edited in place but keep their
signatures/return shapes so `demo.py` and any caller keep working.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 005 has no `[NEEDS CLARIFICATION]`. Phase 0
records: the verdict schema and its validator (distinct fields, same rejection
mechanism as Spec 002); the evidence bundle contents and how self-description is
kept out; the bounded critic wait via `concurrent.futures`; the write-once
verdict record on the parent checkpoint; the hardened fallback ranking
(tie-break, per-branch score, totality); how `promote` is formalised without a
breaking signature change; and the all-failed / single / empty / still-running
handling.

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `Evidence Bundle`, `Verdict`, `Verdict
  Record`, `Deterministic Ranking`, and the promotion state machine
- [contracts/verdict.md](contracts/verdict.md) — the critic verdict schema, the
  exact rejection table, the evidence-bundle shape, the `reason_unsupported`
  soft check, and the bounded wait
- [contracts/promotion.md](contracts/promotion.md) — `promote` /
  `judge_and_promote` inputs, the ordered port calls, release semantics
  (idempotent, continue-on-failure, classified), headless safety, and the
  write-once verdict record
- [quickstart.md](quickstart.md) — run guide + FR/NFR/SC → named-test matrix

Post-design Constitution re-check: unchanged — additive, no new dependency, and
it discharges Article IX for the project.
