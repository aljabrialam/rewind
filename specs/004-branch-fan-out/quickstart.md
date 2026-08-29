# Quickstart: Branch Fan-Out

Run / validation guide + the FR/NFR/SC → named-test matrix (Article VI gate).

---

## Prerequisites

Python 3.11+, `pip install -e .`, `pytest`. Specs 000 + 001 + 002 in place. Live
contract test needs `DAYTONA_API_KEY`.

---

## 1. Fan-out, offline

```bash
pytest tests/unit/test_fan_out.py -q
```

Expected: green, ~a second (a couple of tests use a small `FakeProvider(latency=…)`
to prove concurrency). Three sandboxes from one parent, concurrent execution,
derivation choice, failure isolation, live progress, cleanup, ceiling.

## 2. See three branches run at once

```python
from rewind.engine import Engine
from rewind.providers import FakeProvider
from rewind.reasoning import ReplayReasoner   # or a canned reasoner in tests

e = Engine(FakeProvider(latency=0.1)); e.start()
e.step("echo base > f", "base"); parent = e.run.head
seen = []
res = e.fan_out(parent, _canned_strategist(3), 3, observer=seen.append)
print(res.as_dict()["progress"])       # 3 entries, sandbox ids + states creating→running→done
print(res.derivation, res.ran, f"{res.elapsed_seconds:.2f}s")   # "branch" 3  ~0.1s (not 0.3)
assert e.run.head == parent            # head unchanged
```

## 3. Live contract (needs DAYTONA_API_KEY)

```bash
pytest tests/contract/test_fan_out_contract.py -m live -q
```

Expected: op counts `branch×3, run×3, checkpoint×3, destroy×3` match the fake;
total wall-clock ≈ one branch, within budget.

## 4. E2E

```bash
FAKE=1 python demo.py       # the branch beat now uses fan_out + prints per-branch progress
```

---

## FR / NFR / SC → named-test matrix

All unit tests in `tests/unit/test_fan_out.py` (`fo`); live in
`tests/contract/test_fan_out_contract.py` (`live`).

| Requirement | Named test |
|---|---|
| FR-004-01 N structured strategies; reject non-conforming | `fo::test_asks_reasoner_n_times`, `fo::test_rejects_bad_strategy_schema`, `fo::test_dedupes_and_reports_ran` |
| FR-004-02 one isolated sandbox per strategy from the same checkpoint | `fo::test_one_sandbox_per_strategy_from_parent` (SC-001) |
| FR-004-03 fastest declared derivation + fallback + record | `fo::test_derivation_is_branch_by_default`, `fo::test_prefers_faster_derivation_when_declared`, `fo::test_derivation_recorded` (SC-009) |
| FR-004-04 concurrent, not sequential | `fo::test_branches_run_concurrently` (latency 0.1 ×3 → total < 0.2s — SC-003) |
| FR-004-05 child checkpoint of common parent; head unchanged | `fo::test_children_are_parent_children`, `fo::test_head_unchanged` (SC-002) |
| FR-004-06 independent evidence per branch | `fo::test_each_branch_has_independent_evidence` (SC-004) |
| FR-004-07 live sandbox id + running state per branch | `fo::test_progress_reports_id_and_state`, `fo::test_progress_advances_creating_running_done` (SC-008) |
| FR-004-08 failing branch does not abort; others returned | `fo::test_failing_branch_isolated`, `fo::test_failed_branch_terminal_is_failed` (SC-005) |
| FR-004-09 ceiling never exceeded | `fo::test_ceiling_not_exceeded_during_fan_out` |
| FR-004-10 destroy every branch sandbox on all paths | `fo::test_all_branch_sandboxes_destroyed_on_success`, `fo::test_all_destroyed_when_a_branch_fails`, `fo::test_all_destroyed_when_operation_raises` (SC-006) |
| NFR-004-01 total ≈ slowest branch; offline instant | `fo::test_branches_run_concurrently`, `fo::test_offline_fan_out_is_fast` (SC-010) |
| NFR-004-02 identifiers verbatim | `fo::test_progress_sandbox_ids_are_verbatim` (SC-007) |
| NFR-004-03 identical op counts live vs fake; offline no creds | `fo::test_op_counts_are_fixed` + `live::test_op_counts_match_live` |
| NFR-004-04 progress is renderable structured data | `fo::test_as_dict_progress_is_structured` |

| Success criterion | Verified by |
|---|---|
| SC-001 | `fo::test_one_sandbox_per_strategy_from_parent` |
| SC-002 | `fo::test_head_unchanged` |
| SC-003 | `fo::test_branches_run_concurrently` |
| SC-004 | `fo::test_each_branch_has_independent_evidence` |
| SC-005 | `fo::test_failing_branch_isolated`, `fo::test_failed_branch_terminal_is_failed` |
| SC-006 | `fo::test_all_branch_sandboxes_destroyed_on_success`, `fo::test_all_destroyed_when_a_branch_fails`, `fo::test_all_destroyed_when_operation_raises` |
| SC-007 | `fo::test_progress_sandbox_ids_are_verbatim` |
| SC-008 | `fo::test_progress_reports_id_and_state` |
| SC-009 | `fo::test_derivation_recorded`, `fo::test_derivation_is_branch_by_default` |
| SC-010 | `fo::test_offline_fan_out_is_fast` |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_fan_out.py -q` green; live contract green within budget.
- **G3**: re-run the live contract; no further edits to `Engine.fan_out` / `branch_from`.
