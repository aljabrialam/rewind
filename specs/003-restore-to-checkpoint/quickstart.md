# Quickstart: Restore to Checkpoint

Run / validation guide + the FR/NFR/SC → named-test matrix (Article VI gate).

---

## Prerequisites

Python 3.11+, `pip install -e .`, `pytest`. Specs 000 + 001 in place. Live
contract test needs `DAYTONA_API_KEY`.

---

## 1. Restore, offline

```bash
pytest tests/unit/test_restore.py -q
```

Expected: green, sub-second. `FakeProvider` — restore, verify, head move, tail
preserved, refusals, elapsed time, old sandbox released.

## 2. See a verified restore

```python
from rewind.engine import Engine, RestoreCheck
from rewind.providers import FakeProvider
e = Engine(FakeProvider()); e.start()
e.step("echo A > log.txt", "write A")          # before-marker
mid = e.run.head
e.step("echo B >> log.txt", "write B")         # after-marker
r = e.restore(mid, RestoreCheck(
    before=[("cat log.txt", "A")],
    after=[("cat log.txt", "B")]))
print(r.as_dict())          # status == "verified", head_moved True, elapsed_seconds set
```

## 3. Live contract (needs DAYTONA_API_KEY)

```bash
pytest tests/contract/test_restore_contract.py -m live -q
```

Expected: ordered calls `["branch","run","run","destroy"]` match the fake; a live
restore completes within the demo budget.

## 4. E2E

```bash
FAKE=1 python demo.py        # includes a "rewind to checkpoint" beat printing the verification
```

---

## FR / NFR / SC → named-test matrix

All unit tests in `tests/unit/test_restore.py` (`rs`); live in
`tests/contract/test_restore_contract.py` (`live`).

| Requirement | Named test |
|---|---|
| FR-003-01 produce a sandbox matching the checkpoint | `rs::test_restore_produces_matching_sandbox` |
| FR-003-02 verify before-present / after-absent; never false "verified" | `rs::test_verified_when_before_present_and_after_absent`, `rs::test_not_verified_when_after_still_present`, `rs::test_not_verified_when_before_missing`, `rs::test_not_checked_without_verify` (SC-009) |
| FR-003-03 head moves to the restored checkpoint | `rs::test_head_moves_to_restored_checkpoint` |
| FR-003-04 later checkpoints preserved | `rs::test_tail_checkpoints_preserved`, `rs::test_integrity_after_restore` |
| FR-003-05 refuse released / unreachable / unknown, name which | `rs::test_refuse_released_names_reason`, `rs::test_refuse_unreachable_names_reason`, `rs::test_refuse_unknown_id`, `rs::test_refusal_makes_no_port_calls` |
| FR-003-06 report elapsed time on every path | `rs::test_elapsed_reported_on_success`, `rs::test_elapsed_reported_on_refusal` |
| FR-003-07 release the old head sandbox when unreferenced | `rs::test_old_head_sandbox_released`, `rs::test_live_count_grows_by_at_most_one` |
| NFR-003-01 verification is renderable structured data | `rs::test_as_dict_has_renderable_verification` |
| NFR-003-02 offline restore effectively instant | `rs::test_offline_restore_is_fast` |
| NFR-003-03 identical ordered calls live vs fake; offline no creds | `rs::test_ordered_calls_are_fixed` + `live::test_ordered_calls_match_live` |

| Success criterion | Verified by |
|---|---|
| SC-001 | `rs::test_restore_produces_matching_sandbox` |
| SC-002 | `rs::test_head_moves_to_restored_checkpoint` |
| SC-003 | `rs::test_tail_checkpoints_preserved`, `rs::test_integrity_after_restore` |
| SC-004 | `rs::test_refuse_*` (four) |
| SC-005 | `rs::test_elapsed_reported_on_success`, `rs::test_elapsed_reported_on_refusal` |
| SC-006 | `rs::test_old_head_sandbox_released`, `rs::test_live_count_grows_by_at_most_one` |
| SC-007 | `rs::test_as_dict_has_renderable_verification` |
| SC-008 | `rs::test_offline_restore_is_fast` + file runs with no creds |
| SC-009 | `rs::test_not_checked_without_verify`, `rs::test_not_verified_when_*` |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_restore.py -q` green; live contract green within budget.
- **G3**: re-run the live contract; no further edits to `Engine.restore`.
