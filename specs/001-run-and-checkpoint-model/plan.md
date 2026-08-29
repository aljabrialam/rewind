# Implementation Plan: Run and Checkpoint Model

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/001-run-and-checkpoint-model/`

**Input**: Feature specification from `specs/001-run-and-checkpoint-model/spec.md`

## Summary

Formalise the run tree that already exists in `src/rewind/engine.py` (`Run`,
`Checkpoint`, `add`, `path_to`, `as_tree`) and close the three gaps this
specification requires: a per-checkpoint **creation time** (FR-001-06), an
explicit **restorability** predicate plus refusal of an invalid head target
(FR-001-08), and a **branch terminal outcome** of succeeded / failed / abandoned
(FR-001-09). Add the renderable form's missing fields (creation time, outcome,
snapshot reference) and a structural-integrity check used by the tests. Every
tree operation stays a pure function over in-memory state — no runtime, network,
or credentials.

Technical approach: additive edits only. `Checkpoint` gains `created_at` and
`terminal`. `Run` gains `is_restorable`, `restore_targets`, `set_head` (refuses a
non-restorable target), `mark_terminal`, `branch_outcome`, and `check_integrity`.
`as_tree` emits the new fields. `Engine.step` (Spec 002) sets `terminal="failed"`
on the failing checkpoint; `Engine.promote` (Spec 005, already present) sets
losers `terminal="abandoned"`. No structural rewrite.

## Technical Context

**Language/Version**: Python 3.11+ (venv 3.14)

**Primary Dependencies**: standard library only (`dataclasses`, `datetime`,
`uuid`) — this feature has **no** external dependency, live or otherwise

**Storage**: none — the tree is in-memory for the run's lifetime (persistence is
out of scope)

**Testing**: `pytest`, base layer only; every test runs with no network, no
credentials, no sandbox (NFR-001-01)

**Target Platform**: local dev + CI

**Project Type**: single project — internal library, `src/rewind/engine.py`

**Performance Goals**: tree operations are O(nodes) at worst; the offline test
file runs sub-second

**Constraints**: pure functions over in-memory state (NFR-001-01); structurally
correct under step failure, branch abandonment, and shared-parent branching
(NFR-001-02); identifiers independent of timestamp resolution (NFR-001-03)

**Scale/Scope**: one run, tens of checkpoints, `MAX_BRANCHES=3` per branch point;
9 FRs, 3 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| I — Demo Primacy | Work reaches the screen | `as_tree()` is exactly what the timeline console renders; the branch outcome and restorability drive what the demo can show as a rewind target. **Pass** |
| II — Specification First | Tech names only in the plan | Spec 001 names no tech; this plan names only the standard library. **Pass** |
| IV — Nothing Is Invented | One port per external dependency | This feature has **no** external dependency — pure in-memory model. N/A, trivially satisfied. |
| V — Vertical Slices / no refactor | Additive, no restructure after freeze | New dataclass fields + new `Run` methods; `add`, `path_to`, `as_tree` bodies extended, not reshaped; `branch_from`, `promote`, `shutdown`, `step` untouched except two one-line `terminal=` assignments. **Pass** |
| VI — Traceability & Pyramid | FR → named test; base layer pure logic | This is the canonical base-layer feature: ~10–14 pure-logic tests, sub-second. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| X — Evidence Over Assertion | Evidence and rationale distinct in the render | `as_tree` keeps `exit_code` / `stdout` (evidence) separate from `rationale`; adds `outcome` (derived from evidence) and `terminal` (branch fact). **Pass** |
| XI — Proven In The Runtime | Sandbox lifecycle genuinely live | This feature *stores* the sandbox id and snapshot reference; it creates and restores nothing. No conflict. **Pass** |

**Result**: No violations. Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-run-and-checkpoint-model/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── run-tree.md          # Run/Checkpoint fields + the pure operations + invariants
├── checklists/requirements.md
└── tasks.md                 # /speckit-tasks output
```

### Source Code (repository root)

```text
src/rewind/
├── ports.py           # EDIT — Checkpoint gains `created_at: str` and
│                      #   `terminal: str | None`; keep `state`, `outcome`
├── engine.py          # EDIT (additive) — Run.is_restorable / restore_targets /
│                      #   set_head / mark_terminal / branch_outcome /
│                      #   check_integrity; as_tree() emits created_at, outcome,
│                      #   terminal, snapshot. Engine.step sets terminal="failed";
│                      #   Engine.promote sets losers terminal="abandoned".
├── reasoning.py       # UNCHANGED
├── providers.py       # UNCHANGED
└── capabilities.py    # UNCHANGED

tests/
└── unit/
    └── test_run_tree.py     # NEW — the pure-logic base layer for this feature
```

**Structure Decision**: Single-project layout unchanged. All changes land in
`ports.py` (two dataclass fields) and `engine.py` (`Run` methods + `as_tree`
fields + two `terminal=` assignments). One new test file.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 001 has no `[NEEDS CLARIFICATION]`; Phase 0
records: how `terminal` is set and by whom, the `set_head` refusal contract,
`check_integrity`'s rule set, and the `as_tree` field additions (and their effect
on the existing `fixtures/tree.json` consumer / console).

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `Run`, `Checkpoint`, `Head`, `Checkpoint
  State`, `Branch Terminal Outcome`, `Renderable Tree` as concrete shapes with
  invariants and the checkpoint state machine
- [contracts/run-tree.md](contracts/run-tree.md) — every pure operation, its
  signature intent, pre/postconditions, and the tree invariants each must
  preserve
- [quickstart.md](quickstart.md) — run guide + FR/NFR/SC → named-test matrix

Post-design Constitution re-check: unchanged — additive, no new dependency.
