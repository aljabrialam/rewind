# Quickstart: Run and Checkpoint Model

Run / validation guide + the FR/NFR/SC → named-test matrix (Constitution Article
VI traceability gate).

---

## Prerequisites

Python 3.11+, `pip install -e .`, `pytest`. **Nothing else** — this feature has
no network, credential, or sandbox dependency.

---

## 1. The whole feature, offline

```bash
pytest tests/unit/test_run_tree.py -q
```

Expected: green, sub-second. Pure-logic base layer — tree building, lineage,
renderable form, restorability, branch outcome, structural integrity.

## 2. Structural integrity after a messy run

```bash
pytest tests/unit/test_run_tree.py::test_integrity_after_failure_abandon_and_shared_parent -q
```

A run with a failed step, an abandoned branch, and two branches from one parent →
`Run.check_integrity()` returns `[]`.

## 3. See it render

```bash
FAKE=1 python demo.py            # writes fixtures/tree.json from Run.as_tree()
python -m http.server 8000       # open ui/console.html — reads tree.json
```

The new fields (`created_at`, `outcome`, `terminal`, `snapshot`) flow through
`as_tree()` automatically.

---

## FR / NFR / SC → named-test matrix

All tests in `tests/unit/test_run_tree.py` (`rt`).

| Requirement | Named test |
|---|---|
| FR-001-01 ordered steps: index, instruction, completion state | `rt::test_run_is_ordered_steps`, `rt::test_step_carries_index_instruction_state` |
| FR-001-02 checkpoint on step completion, tied to runtime state | `rt::test_checkpoint_records_snapshot_reference` |
| FR-001-03 stable identifier for run lifetime | `rt::test_identifier_stable_after_run_advances` |
| FR-001-04 multiple children → tree | `rt::test_parent_can_have_two_children`, `rt::test_child_creation_does_not_mutate_parent` |
| FR-001-05 exactly one head | `rt::test_exactly_one_head` |
| FR-001-06 parent + sandbox id + created_at per checkpoint | `rt::test_checkpoint_has_parent_sandbox_and_created_at` |
| FR-001-07 renderable without further computation | `rt::test_as_tree_has_all_fields`, `rt::test_as_tree_root_only` |
| FR-001-08 live/released/unreachable; released never restorable | `rt::test_released_not_restorable`, `rt::test_unreachable_not_restorable`, `rt::test_live_with_snapshot_is_restorable`, `rt::test_restore_targets_excludes_released`, `rt::test_set_head_refuses_released` |
| FR-001-09 branch terminal outcome succeeded/failed/abandoned | `rt::test_branch_outcome_succeeded`, `rt::test_branch_outcome_failed_via_engine_step`, `rt::test_branch_outcome_abandoned_via_promote`, `rt::test_branch_outcome_none_while_advancing` |
| NFR-001-01 pure functions, no runtime dependency | whole file imports no provider/network; `rt::test_no_runtime_import` |
| NFR-001-02 correct under failure / abandonment / shared parent | `rt::test_integrity_after_failure_abandon_and_shared_parent` |
| NFR-001-03 identifier independent of timestamp resolution | `rt::test_two_checkpoints_same_second_distinct_ids` |

| Success criterion | Verified by |
|---|---|
| SC-001 | `rt::test_identifier_stable_after_run_advances` |
| SC-002 | `rt::test_path_to_is_ordered_root_to_node` |
| SC-003 | `rt::test_child_creation_does_not_mutate_parent` |
| SC-004 | `rt::test_exactly_one_head` |
| SC-005 | `rt::test_restore_targets_excludes_released` |
| SC-006 | `rt::test_branch_outcome_*` (four) |
| SC-007 | `rt::test_as_tree_has_all_fields` |
| SC-008 | `rt::test_no_runtime_import` + the file running with no creds |
| SC-009 | `rt::test_two_checkpoints_same_second_distinct_ids` |
| SC-010 | `rt::test_integrity_after_failure_abandon_and_shared_parent` |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_run_tree.py -q` green; `check_integrity()` `[]`
  after the messy-run test.
- **G3**: no further edits to `Run` / `Checkpoint` structure.
