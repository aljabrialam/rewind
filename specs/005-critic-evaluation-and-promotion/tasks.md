---
description: "Task list for Critic Evaluation and Promotion implementation"
---

# Tasks: Critic Evaluation and Promotion

**Feature**: `005-critic-evaluation-and-promotion`

**Input**: Design documents from `specs/005-critic-evaluation-and-promotion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/verdict.md](contracts/verdict.md), [contracts/promotion.md](contracts/promotion.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED (Constitution Article VI). Test names are the source of truth in [quickstart.md](quickstart.md).

**Depends on**: Spec 000 (`provider.branch`/`destroy`, `classify`, `CallRecord`), Spec 001 (`Run`, `Checkpoint.snapshot`/`state`/`terminal`, `check_integrity`, `is_restorable`), Spec 002 (`ReasoningPort`, `SchemaError`), Spec 004 (`fan_out` child checkpoints w/ own snapshots + independent evidence) — all done. **Closes Constitution Article IX.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US5, on user-story tasks only

## Path Conventions

`src/rewind/ports.py` (1 field), `src/rewind/reasoning.py` (verdict schema), `src/rewind/capabilities.py` (1 const), `src/rewind/engine.py` (the feature), `tests/unit/test_critic.py` (new), `tests/contract/test_critic_contract.py` (new), `demo.py`.

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_critic.py` and `tests/contract/test_critic_contract.py` (docstrings + imports; a `_canned_critic(payload_or_exc)` helper — a `ReasoningPort` whose `next_instruction` returns a given verdict dict, or raises, or sleeps then returns)

**Checkpoint**: `pytest -q` still green (162 passed from specs 000–004 + 006).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the verdict schema, the write-once record field, the bounded-wait constant. Blocks Phases 3–7.

- [X] T002 In `src/rewind/ports.py` add `Checkpoint.verdict: dict | None = None` (at the end of the dataclass, keyword-safe)
- [X] T003 In `src/rewind/capabilities.py` add `CRITIC_WAIT = _f("REWIND_CRITIC_WAIT", 8.0)` (bounded critic wall-clock)
- [X] T004 In `src/rewind/reasoning.py` add `Verdict` frozen dataclass `{chosen: str, scores: dict, reason: str}`, `VerdictSchemaError(SchemaError)`, and `validate_verdict(payload, branch_ids) -> Verdict` per [contracts/verdict.md](contracts/verdict.md): reject non-mapping; `chosen` present ∧ str ∧ ∈ `branch_ids`; `scores` present ∧ covers every id ∧ each value `float`-coercible (normalise a `list[{branch,score}]`); `reason` present ∧ non-empty. Also compute and return a `reason_unsupported: bool` soft flag (no rejection).
- [X] T005 In `src/rewind/engine.py` add `Run.record_verdict(parent_id, record) -> dict` (set `checkpoints[parent_id].verdict` only if `None`; return the effective record) and `Run.get_verdict(parent_id) -> dict | None`

**Checkpoint**: `from rewind.reasoning import validate_verdict`; `validate_verdict({"chosen":"a","scores":{"a":1,"b":0},"reason":"exit 0"}, ["a","b"])` returns a `Verdict`.

---

## Phase 3: User Story flows — the fallback ranking (Priority: P1, US2 core / NFR-005-02)

**Goal**: `rank_by_evidence` is pure and total, with a deterministic tie-break and a per-branch numeric score.

### Tests

- [X] T006 [P] `tests/unit/test_critic.py`: `test_rank_is_total_over_all_failed` (3 branches all exit≠0 → strict ordering, a `winner`), `test_rank_is_pure` (same input twice → identical output; no attribute mutation), `test_rank_tie_break_is_deterministic` (two identical `(exit, elapsed)` → ordered by index then step_id; `reason` notes the tie — SC-006)
- [X] T007 [P] `tests/unit/test_critic.py`: `test_rank_scores_are_numeric` (each `scores[i]` has a numeric `score`, higher = better)

### Implementation

- [X] T008 In `src/rewind/engine.py` harden `rank_by_evidence`: sort key `(exit_code or 99, elapsed or 1e9, index, step_id)`; add `score = -(exit_code*1e6) - elapsed` to each `scores[i]`; `reason` notes a tie / "no branch exited 0"; keep the return shape (`winner` = index) so `demo.py` is unaffected

**Checkpoint**: the fallback is a total, pure, reproducible ranking.

---

## Phase 4: User Story 1 — winner chosen on evidence, becomes head (Priority: P1) 🎯 MVP

**Goal**: evidence bundle → critic → structured verdict → chosen branch is head, losers released.

### Tests

- [X] T009 [P] [US1] `tests/unit/test_critic.py`: `test_bundle_is_evidence_only` (`Engine._evidence_bundle` contains each branch's exit code + a slice of stdout, and **none** of the branches' `rationale` strings — SC-001), `test_valid_verdict_accepted`, `test_reason_required`
- [X] T010 [P] [US1] `tests/unit/test_critic.py`: `test_winner_becomes_head` (SC-003), `test_losers_released_and_marked` (losers `state=="released"`, `terminal=="abandoned"`), `test_tree_intact_after_promotion` (`check_integrity()==[]`, loser id/instruction/evidence/snapshot intact — SC-004)

### Implementation

- [X] T011 [US1] In `src/rewind/engine.py` add `Engine._evidence_bundle(branches) -> str` — one text section per branch from `step_id` + `evidence` only (exit, elapsed, truncated stdout); never `rationale`
- [X] T012 [US1] In `src/rewind/engine.py` add `Engine.evaluate(branches, critic, context="") -> dict`: build the bundle; run `critic.next_instruction(bundle or context)` under `ThreadPoolExecutor` + `future.result(timeout=capabilities.CRITIC_WAIT)`; `validate_verdict(result, ids)`; on success return `{chosen, scores, reason, reason_unsupported, fallback_used: False, fallback_trigger: None, excluded: []}` (Phase 5 adds the fallback + edge branches)
- [X] T013 [US1] In `src/rewind/engine.py` formalise `promote(winner_step_id, losers, *, verdict=None, parent_id=None) -> dict` per [contracts/promotion.md](contracts/promotion.md) C1–C9: re-derive winner from `snapshot`; **headless-safe** on failure (`error` set, head unchanged); move head on success; per-loser release loop — pop handle, `destroy` in try/except, mark `released`/`abandoned`, append `{sid, released, error}`; idempotent; continue-on-failure; if `verdict`+`parent_id` → `run.record_verdict`; return `{head, winner, losers, verdict_recorded, error}`; keep the positional call working
- [X] T014 [US1] In `src/rewind/engine.py` add `Engine.judge_and_promote(branches, critic, context="", parent_id=None) -> dict`: resolve `parent_id` from the branches' common parent; `evaluate(...)`; build the write-once Verdict Record; `promote(chosen, <other ids>, verdict=record, parent_id=parent_id)`; return `{**promote_result, verdict: record, evaluate: <result>}`

**Checkpoint**: MVP — a canned critic verdict promotes a branch and releases the others.

---

## Phase 5: User Story 2 — malformed verdict rejected, run still moves (Priority: P1)

**Goal**: reject bad verdicts, fall back deterministically, record the fallback.

### Tests

- [X] T015 [P] [US2] `tests/unit/test_critic.py`: `test_reject_unknown_branch`, `test_reject_missing_score`, `test_reject_bad_structure`, `test_reject_no_snapshot_branch` — each → fallback, a winner promoted (SC-002)
- [X] T016 [P] [US2] `tests/unit/test_critic.py`: `test_fallback_on_unreachable_critic` (critic raises), `test_fallback_on_timeout` (critic sleeps > `CRITIC_WAIT` — set a tiny `REWIND_CRITIC_WAIT`), `test_fallback_on_rejected_verdict`, `test_fallback_flag_recorded` (`fallback_used` + `fallback_trigger` in the Verdict Record — SC-005), `test_timeout_returns_within_bound` (SC-010)

### Implementation

- [X] T017 [US2] In `Engine.evaluate` wrap the critic call: `FuturesTimeoutError` → fallback `"critic-timeout"`; any other exception → `"critic-unreachable: <msg>"`; `VerdictSchemaError` → `"verdict-rejected: <why>"`. Fallback = `rank_by_evidence` over the snapshot-bearing branches → `chosen` = top branch `step_id`, `scores` from the ranking, `reason` generated, `fallback_used=True`

**Checkpoint**: US1 + US2 — no verdict path leaves the run without a promotion.

---

## Phase 6: User Story 3 + 4 — inspectable record; the loop repeats (Priority: P2)

### Tests

- [X] T018 [P] [US3] `tests/unit/test_critic.py`: `test_verdict_recorded_on_parent` (parent `.verdict` has chosen/scores/reason/flags — SC), `test_verdict_record_is_write_once` (a second `record_verdict` on the same parent is a no-op — SC-007)
- [X] T019 [P] [US4] `tests/unit/test_critic.py`: `test_second_round_from_promoted_head` (fan_out → judge_and_promote → fan_out from the new head → judge_and_promote again; each verdict on its own parent; head is round-2 winner — SC-008), `test_fanout_from_loser_refused` (`fan_out` from a `released` checkpoint → `FanOutResult.error`)
- [X] T020 [P] [NFR-005-01] `tests/unit/test_critic.py`: `test_replayed_verdict_is_reproducible` (same recorded critic dict over the same branch set → identical Verdict Record twice — SC-011)

### Implementation

- [X] T021 [US3] Confirm `judge_and_promote` writes the record via `run.record_verdict` (write-once) and that `console_fixture` picks up the promoted parent's `.verdict` (extend `console_fixture` to prefer `run.get_verdict(head-lineage parent)` over the passed-in `verdict` arg when present)

**Checkpoint**: the reason is inspectable and the loop turns twice.

---

## Phase 7: User Story 5 + edge FRs — releases on every path; still-running; empty/single (Priority: P1/P2)

### Tests

- [X] T022 [P] [US5] `tests/unit/test_critic.py`: `test_release_is_idempotent` (loser already gone → `released: True`, no error), `test_release_continues_after_one_failure` (one loser's `destroy` raises → other loser still released, winner still head, failure in `losers[].error` with a class — SC-009), `test_headless_safe_on_rederive_failure` (winner re-derive raises → head unchanged, `error` set, losers still released — FR-005-04)
- [X] T023 [P] `tests/unit/test_critic.py`: `test_still_running_branch_excluded` (a branch with `evidence is None` → excluded, recorded in `excluded`, never scored — FR-005-09), `test_empty_set_refused` (`{error: "no branches"}`, head unchanged), `test_single_branch_promoted_no_verdict` (1 branch w/ snapshot → promoted, `fallback_trigger == "single-branch"`, no critic call — FR-005-10)
- [X] T024 [P] `tests/unit/test_critic.py`: `test_provider_call_counts` (`judge_and_promote` over 3 branches, canned verdict → `Counter(provider.calls ops) == {"branch":1, "destroy":2}` — NFR-005-04)

### Implementation

- [X] T025 In `Engine.evaluate` add the guards from [contracts/verdict.md](contracts/verdict.md): empty set → `{error:"no branches"}`; single-with-snapshot → direct promote result (`fallback_trigger="single-branch"`, no critic call); any branch not terminal (`evidence is None`) → wait ≤ `CRITIC_WAIT/4`, then `excluded += [id]` and judge the rest

**Checkpoint**: every path releases losers; partial/empty/single sets handled.

---

## Phase 8: Live contract + demo + polish

- [X] T026 `tests/contract/test_critic_contract.py` (`@pytest.mark.live`): `test_call_counts_match_live` (a 3-branch round against `DaytonaProvider` + a live critic → `{"branch":1,"destroy":2}` provider ops, same as the fake), `test_round_within_budget` (`elapsed < CRITIC_WAIT + margin`)
- [X] T027 [P] `demo.py` (additive): replace the `rank_by_evidence` + `promote` beat with `res = e.judge_and_promote(branches, _CannedCritic(...))`; print `res["verdict"]["reason"]` and `fallback_used`; keep the restore beat (it now restores from the promoted head's lineage)
- [X] T028 [P] Add `docs/critic-and-promotion.md` linking the two contracts and the FR→test matrix; note this feature closes Article IX
- [X] T029 Verify the FR/NFR/SC → named-test matrix in [quickstart.md](quickstart.md): every row resolves to a passing (or live-skipped) test (Article VI gate)
- [X] T030 `pytest -q` full offline suite green (000–006); `FAKE=1 python demo.py` runs the full loop (steps → fail → fan-out → judge+promote → restore); restore `fixtures/tree.json`; in `docs/gates.md` record spec 005 done **and Constitution Article IX satisfied**

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T005)** blocks everything.
- **Phase 3 (T006–T008)**: fallback ranking — independent, can land right after Foundational.
- **Phase 4 (T009–T014)**: MVP. `_evidence_bundle` → `evaluate` (happy path) → `promote` formalised → `judge_and_promote`.
- **Phase 5 (T015–T017)**: extends `evaluate` with the fallback branches — sequential on `evaluate` after Phase 4.
- **Phase 6 (T018–T021)**: record + loop; T021 also touches `console_fixture`.
- **Phase 7 (T022–T025)**: extends `evaluate`/`promote` with edge guards — sequential on those methods.
- **Phase 8**: last. T027 (`demo.py`) after `judge_and_promote` is complete.

### Parallel opportunities

- Test-writing tasks within each phase (T006/T007, T009/T010, T015/T016, T018/T019/T020, T022/T023/T024)
- T027 / T028 in Phase 8
- `engine.py` `evaluate` / `promote` / `judge_and_promote` bodies — edited by T012, T013, T014, T017, T021, T025 — **sequential**

---

## Parallel Example: User Story 2

```bash
Task: "T015 test_critic.py — reject unknown branch / missing score / bad structure / no-snapshot"
Task: "T016 test_critic.py — fallback on unreachable / timeout / rejected; flag recorded; within bound"
```

---

## Implementation Strategy

### MVP (fallback + US1)

1. Setup + Foundational (T001–T005) + fallback ranking (T006–T008)
2. US1 (T009–T014) — evidence bundle, evaluate happy path, formalised promote, judge_and_promote
3. **STOP and VALIDATE**: a canned verdict promotes a branch to head and releases the other two.

### Incremental

fallback ranking → US1 (evidence→verdict→promote) → US2 (reject → fallback, recorded) → US3/US4 (write-once record, loop repeats) → US5 + edges (releases everywhere, still-running/empty/single) → live contract + demo + gates (Article IX).

---

## Notes

- `promote` keeps its positional `(winner, losers)` call for `demo.py`; the new
  behaviour is opt-in via keywords. `rank_by_evidence` keeps its return shape.
  `start`/`step`/`restore`/`fan_out`/`branch_from` are untouched (Article V).
- The critic uses the **same** `ReasoningPort` as the strategist (Article IV) —
  `validate_verdict` is a second validator, not a second port.
- The fallback ranking is pure + total (no `self`, no I/O) — the archetypal
  base-layer test (Article VI).
- This feature **closes the Constitution Article IX loop** — record it at G3.
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
