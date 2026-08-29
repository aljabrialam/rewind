---
description: "Task list for Alternate Inference Endpoint implementation"
---

# Tasks: Alternate Inference Endpoint

**Feature**: `008-alternate-inference-endpoint`

**Input**: Design documents from `specs/008-alternate-inference-endpoint/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/routed-reasoner.md](contracts/routed-reasoner.md), [quickstart.md](quickstart.md)

**Tests**: INCLUDED. Routing + fallback are a pure-logic offline layer with stub endpoints (NFR-008-04). One `@pytest.mark.live` availability contract test (NFR-008-02 / FR-008-08).

**Depends on**: 002 (`ReasoningPort`), 005 (`Engine.evaluate` / `judge_and_promote` / `rank_by_evidence` / `validate_verdict` / `CRITIC_WAIT`), 006 (console verdict block), 007 (demo budget). **Article VIII additive — deletable with zero impact; nothing in 000–007 changes when `CRITIC_BASE_URL` is unset.**

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US6, on user-story tasks only

## Path Conventions

`src/rewind/reasoning.py` (the routing), `src/rewind/capabilities.py` (1 const), `src/rewind/engine.py` (~4 lines), `ui/console.html` (1 block), `.env.example`, `tests/unit/test_alternate_endpoint.py` (new), `tests/contract/test_alternate_endpoint_contract.py` (new).

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_alternate_endpoint.py` and `tests/contract/test_alternate_endpoint_contract.py` (docstrings + imports; stub-endpoint helpers: `_ok(payload)`, `_raises(exc)`, `_slow(delay, payload)` — each a `ReasoningPort` object)

**Checkpoint**: `pytest -q` still green (213 passed from specs 000–007).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the wait bound + the parameterised `LiveReasoner`. Blocks Phases 3–6.

- [X] T002 In `src/rewind/capabilities.py` add `ALT_WAIT = min(_f("REWIND_ALT_WAIT", CRITIC_WAIT), CRITIC_WAIT)` (float, never > `CRITIC_WAIT`)
- [X] T003 In `src/rewind/reasoning.py` make `LiveReasoner.__init__` keyword-only `base_url: str | None = None`, `model: str | None = None`, `api_key: str | None = None` — each defaulting to `os.environ.get("LLM_BASE_URL")` / `os.environ.get("LLM_MODEL", "gpt-4o-mini")` / `os.environ["LLM_API_KEY"]`. Existing no-arg construction MUST be unchanged.

**Checkpoint**: `from rewind.capabilities import ALT_WAIT`; `LiveReasoner()` still constructs as before.

---

## Phase 3: User Story 2 + 3 — `RoutedReasoner` (Priority: P1) 🎯 MVP

**Goal**: alternate-first, then primary; same-schema validation of the alternate; `last_served_by`.

### Tests

- [X] T004 [P] [US2] `tests/unit/test_alternate_endpoint.py`: `test_routed_reasoner_is_a_reasoning_port` (`hasattr(rr, "next_instruction")`), `test_alternate_ok_served_by_alternate` (stub alt returns a good payload → returned as-is, `rr.last_served_by == "alternate"` — SC-001)
- [X] T005 [P] [US3] `tests/unit/test_alternate_endpoint.py`: `test_alternate_raise_falls_back_to_primary` (alt raises → primary's payload returned, `last_served_by == "primary"`), `test_slow_alternate_falls_back_within_bound` (alt sleeps > bound, tiny `bound` → primary within ~bound — SC-005), `test_alt_wait_le_critic_wait` (`ALT_WAIT <= capabilities.CRITIC_WAIT` — SC-004)
- [X] T006 [P] [US2] `tests/unit/test_alternate_endpoint.py`: `test_alternate_bad_schema_rejected_like_primary` (a `validate` that raises `VerdictSchemaError` on the alt payload → falls to primary; the same payload from the primary is what `Engine.evaluate` would then reject identically — SC-002)

### Implementation

- [X] T007 [US2/US3] In `src/rewind/reasoning.py` add `RoutedReasoner(alternate, primary, *, bound, validate=None)` per [contracts/routed-reasoner.md](contracts/routed-reasoner.md) C1–C8: `next_instruction(context)` runs `alternate.next_instruction` in a `ThreadPoolExecutor` with `future.result(timeout=bound)`; on return, if `validate` given call `validate(raw, context)` (may raise); success → `self.last_served_by = "alternate"`, return `raw`; any `TimeoutError` / exception / validate failure → `shutdown(wait=False, cancel_futures=True)`, `self.last_served_by = "primary"`, return `primary.next_instruction(context)`
- [X] T008 [US2] In `src/rewind/reasoning.py` add `verdict_ids_from_bundle(context) -> list[str]` = `re.findall(r"branch (\S+) \|", context)`

**Checkpoint**: MVP — `RoutedReasoner` routes to the alternate and falls back cleanly, tracking `last_served_by`.

---

## Phase 4: User Story 1 + 6 — the factory + `served_by` on the record (Priority: P1)

**Goal**: config selects routing; the producing provider is on the verdict record; unset = unchanged.

### Tests

- [X] T009 [P] [US1] `tests/unit/test_alternate_endpoint.py`: `test_factory_plain_when_config_absent` (no `CRITIC_BASE_URL` → `critic_reasoner()` returns a `LiveReasoner`-shaped object, not a `RoutedReasoner`), `test_factory_routes_when_config_complete` (monkeypatch env `CRITIC_BASE_URL`+`CRITIC_MODEL` + stub the two `LiveReasoner` constructions → a `RoutedReasoner`), `test_partial_config_is_absent` (only `CRITIC_BASE_URL` set → plain)
- [X] T010 [P] [US3] `tests/unit/test_alternate_endpoint.py`: `test_served_by_on_verdict_record` (a full `judge_and_promote` with `critic = RoutedReasoner(stub_ok, stub_primary, ...)` → `e.run.get_verdict(parent)["served_by"] == "alternate"`), `test_alternate_bad_falls_back_to_primary` (routed critic whose alt returns junk → record `served_by == "primary"`), `test_both_fail_deterministic` (alt raises, primary raises → `judge_and_promote` → record `served_by == "deterministic-fallback"` — SC-003)
- [X] T011 [P] [US6] `tests/unit/test_alternate_endpoint.py`: `test_unset_config_runs_unchanged` (`judge_and_promote` with a plain canned critic → record `served_by == "primary"`, everything else identical to spec 005's expectations — SC-007), `test_no_spec_00x_imports_routed` (AST scan: no `src/rewind/*.py` except `reasoning.py` references `RoutedReasoner` / `critic_reasoner`)

### Implementation

- [X] T012 [US1] In `src/rewind/reasoning.py` add `critic_reasoner() -> ReasoningPort`: `primary = LiveReasoner()`; if `os.environ.get("CRITIC_BASE_URL")` and `os.environ.get("CRITIC_MODEL")` → `alternate = LiveReasoner(base_url=..., model=..., api_key=os.environ.get("CRITIC_API_KEY") or os.environ["LLM_API_KEY"])`, return `RoutedReasoner(alternate, primary, bound=capabilities.ALT_WAIT, validate=lambda raw, ctx: validate_verdict(raw, verdict_ids_from_bundle(ctx)))`; else return `primary`
- [X] T013 [US3] In `src/rewind/engine.py` `Engine.evaluate`: add `served_by` to the `_r(...)` default (`"primary"`); on the accepted-verdict return set `served_by=getattr(critic, "last_served_by", "primary")`; in `_fallback(...)` set `served_by="deterministic-fallback"`
- [X] T014 [US3] In `src/rewind/engine.py` `Engine.judge_and_promote`: add `"served_by": ev["served_by"]` to the verdict `record` dict (write-once with the rest)

**Checkpoint**: the config switches routing on/off; every verdict record names its provider; unset changes nothing.

---

## Phase 5: User Story 5 — the console shows the provider (Priority: P2)

### Implementation

- [X] T015 [US5] In `ui/console.html` verdict block: render `${T.verdict.served_by || T.verdict.provider || ''}` in the interface face next to "judged on execution evidence"; e.g. `served by <span>alternate</span>`. No change when the key is absent (old fixtures)

**Manual check**: the spec 006 visual-acceptance pass gains one line — the verdict shows a provider label (`alternate` / `primary` / `deterministic-fallback`).

---

## Phase 6: Availability check + polish

- [X] T016 `tests/contract/test_alternate_endpoint_contract.py` (`@pytest.mark.live`, `skipif(not os.environ.get("CRITIC_BASE_URL"))`): `test_alternate_reachable_and_conforming` — build the alternate `LiveReasoner(base_url=CRITIC_BASE_URL, model=CRITIC_MODEL, ...)`, send one evidence-bundle-shaped prompt with two branch ids, assert `validate_verdict(response, [id1, id2])` accepts it (FR-008-08 / NFR-008-02)
- [X] T017 [P] In `.env.example` document `CRITIC_BASE_URL` / `CRITIC_MODEL` / `CRITIC_API_KEY` / `REWIND_ALT_WAIT` (both critic vars unset = no alternate)
- [X] T018 [P] In `tools/capture_demo_fixtures.py` (if present) swap the critic `RecordingReasoner(LiveReasoner(), …)` for `RecordingReasoner(critic_reasoner(), …)` so a captured verdict carries `served_by` — guarded, unchanged when `CRITIC_BASE_URL` unset
- [X] T019 [P] Add `docs/alternate-inference-endpoint.md` linking [contracts/routed-reasoner.md](contracts/routed-reasoner.md); note Article VIII — additive, assessed once, deletable
- [X] T020 Verify the FR/NFR/SC → test map in [quickstart.md](quickstart.md): every row resolves to a unit test, the live contract test, or the console visual-acceptance line
- [X] T021 `pytest -q` — full offline suite green (000–007 **unchanged** + `test_alternate_endpoint.py`) with `CRITIC_BASE_URL` unset; confirm **zero** outcome change in any 000–007 test (SC-008); note spec 008 + the Article VIII assessment status in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T003)** blocks everything.
- **Phase 3 (T004–T008)**: `RoutedReasoner` — MVP.
- **Phase 4 (T009–T014)**: factory + `served_by` — T012 needs T007/T008; T013/T014 (`engine.py`) are independent of `reasoning.py` and can be done in parallel with T012.
- **Phase 5 (T015)**: console — after T014 (record carries `served_by`).
- **Phase 6**: availability test + polish — last.

### Parallel opportunities

- Test-writing tasks within each phase (T004/T005/T006, T009/T010/T011)
- T013 + T014 (`engine.py`) parallel to T012 (`reasoning.py`)
- T017 / T018 / T019 in Phase 6
- `src/rewind/reasoning.py` — edited by T003, T007, T008, T012 — **sequential**

---

## Implementation Strategy

### MVP (`RoutedReasoner`)

1. Setup + Foundational (T001–T003)
2. Phase 3 (T004–T008) — `RoutedReasoner` routes + falls back, `last_served_by`
3. **STOP and VALIDATE**: a stub alternate is served (`"alternate"`); a raising alternate falls to the stub primary (`"primary"`).

### Incremental

`RoutedReasoner` → factory + `served_by` on the record → console label → live availability check + polish. Verify the full 000–007 suite is byte-for-byte unchanged with the config unset.

---

## Notes

- Routing lives in `reasoning.py`; `engine.py` gains only a `served_by`
  pass-through (~4 lines). `evaluate` / `promote` / `rank_by_evidence` / the demo
  path are otherwise untouched (Article V).
- `LiveReasoner` stays the only reasoning-vendor importer; `RoutedReasoner`
  composes two of them (Article IV).
- **Deletable**: remove `RoutedReasoner` + `critic_reasoner()` + the two
  `served_by` lines and the system is exactly spec 007. That is the Article VIII
  contract, made structural.
- Every task traces to an FR/NFR/SC via [quickstart.md](quickstart.md).
