"""tests/unit/test_restore.py — spec 003: restore to checkpoint.

Offline. No network, no credentials.
Contract: specs/003-restore-to-checkpoint/contracts/restore.md
"""

import pytest

from rewind.engine import Engine, RestoreCheck, RestoreResult
from rewind.providers import FakeProvider


def _run():
    """root + two linear steps writing log.txt."""
    e = Engine(FakeProvider())
    e.start()
    e.step("echo step1 > log.txt", "write step1")
    mid = e.run.head
    e.step("echo step2 >> log.txt", "write step2")
    return e, mid


_GOOD = RestoreCheck(before=[("cat log.txt", "step1")], after=[("cat log.txt", "step2")])


# ============================================================ US1 — resume

def test_restore_produces_matching_sandbox():
    e, mid = _run()
    r = e.restore(mid, _GOOD)
    assert r.error is None and r.sandbox_id is not None
    rh = e.live[mid]
    out = e.p.run(rh, "cat log.txt").stdout
    assert "step1" in out and "step2" not in out          # SC-001


def test_head_moves_to_restored_checkpoint():
    e, mid = _run()
    r = e.restore(mid, _GOOD)
    assert e.run.head == mid and r.head_moved is True      # SC-002


def test_next_step_after_restore_parents_on_restored_cp():
    e, mid = _run()
    e.restore(mid, _GOOD)
    cp = e.step("echo step3 >> log.txt", "continue")
    assert cp.parent_id == mid


def test_restore_current_head_still_produces_sandbox():
    e, mid = _run()
    head = e.run.head
    r = e.restore(head)
    assert r.sandbox_id is not None
    assert r.head_moved is False                           # it was already the head
    assert isinstance(r.elapsed_seconds, float)


def test_restore_root_when_root_has_snapshot():
    e, _ = _run()
    r = e.restore("root")
    assert r.error is None and e.run.head == "root"


# ============================================================ US2 — verified on screen

def test_verified_when_before_present_and_after_absent():
    e, mid = _run()
    r = e.restore(mid, _GOOD)
    assert r.verification.status == "verified"


def test_not_verified_when_after_still_present():
    e, mid = _run()
    r = e.restore(mid, RestoreCheck(before=[("cat log.txt", "step1")],
                                    after=[("cat log.txt", "step1")]))   # marker IS present
    assert r.verification.status == "not-verified"
    assert e.run.head == mid                               # head still moved


def test_not_verified_when_before_missing():
    e, mid = _run()
    r = e.restore(mid, RestoreCheck(before=[("cat log.txt", "NOPE")],
                                    after=[("cat log.txt", "step2")]))
    assert r.verification.status == "not-verified"


def test_not_verified_when_only_before_supplied():
    e, mid = _run()
    r = e.restore(mid, RestoreCheck(before=[("cat log.txt", "step1")]))
    assert r.verification.status == "not-verified"         # cannot confirm "after absent"


def test_not_checked_without_verify():
    e, mid = _run()
    r = e.restore(mid)
    assert r.verification.status == "not-checked"          # SC-009


def test_failing_probe_does_not_abort_restore():
    e, mid = _run()
    r = e.restore(mid, RestoreCheck(before=[("cat log.txt", "NOPE")],
                                    after=[("cat log.txt", "step2")]))
    assert e.run.head == mid and r.error is None           # restore happened
    assert r.verification.status == "not-verified"         # proof did not hold


def test_as_dict_has_renderable_verification():
    e, mid = _run()
    d = e.restore(mid, _GOOD).as_dict()
    v = d["verification"]
    assert v["status"] == "verified"
    for row in v["before"] + v["after"]:
        assert set(row) == {"command", "marker", "observed", "passed"}
    assert "elapsed_seconds" in d and "head_moved" in d    # SC-007 / NFR-003-01


# ============================================================ US3 — tail preserved

def test_tail_checkpoints_preserved():
    e, mid = _run()
    tail_id = e.run.head                                   # s2
    tail_before = (e.run.get(tail_id).instruction, e.run.get(tail_id).snapshot)
    order_before = list(e.run.order)
    e.restore(mid, _GOOD)
    assert e.run.get(tail_id) is not None
    assert (e.run.get(tail_id).instruction, e.run.get(tail_id).snapshot) == tail_before
    assert e.run.order == order_before                     # SC-003 — nothing removed


def test_integrity_after_restore():
    e, mid = _run()
    e.restore(mid, _GOOD)
    assert e.run.check_integrity() == []


def test_later_checkpoint_still_restorable_after_restore():
    e, mid = _run()
    tail_id = e.run.head
    e.restore(mid, _GOOD)
    assert e.run.is_restorable(tail_id)
    r2 = e.restore(tail_id, RestoreCheck(before=[("cat log.txt", "step2")],
                                         after=[("cat log.txt", "NOPE")]))
    assert r2.error is None and e.run.head == tail_id


# ============================================================ US4 — refusals

def test_refuse_released_names_reason():
    e, mid = _run()
    e.run.get(mid).state = "released"
    r = e.restore(mid)
    assert r.error == "released" and r.sandbox_id is None and r.head_moved is False


def test_refuse_unreachable_names_reason():
    e, mid = _run()
    e.run.get(mid).state = "unreachable"
    assert e.restore(mid).error == "unreachable"
    e2, mid2 = _run()
    e2.run.get(mid2).snapshot = None                       # no runtime state
    assert e2.restore(mid2).error == "unreachable"


def test_refuse_unknown_id():
    e, _ = _run()
    assert e.restore("ghost").error == "unknown"


def test_refusal_makes_no_port_calls():
    e, mid = _run()
    e.p.calls.clear()
    e.run.get(mid).state = "released"
    e.restore(mid)
    assert e.p.calls == []


def test_refusal_leaves_head_unchanged():
    e, mid = _run()
    head_before = e.run.head
    e.restore("ghost")
    assert e.run.head == head_before


def test_refusal_still_reports_elapsed():
    e, _ = _run()
    r = e.restore("ghost")
    assert isinstance(r.elapsed_seconds, float) and r.elapsed_seconds >= 0


# ============================================================ US5 — fast + reports cost

def test_elapsed_reported_on_success():
    e, mid = _run()
    assert isinstance(e.restore(mid, _GOOD).elapsed_seconds, float)


def test_elapsed_reported_on_refusal():
    e, _ = _run()
    assert isinstance(e.restore("ghost").elapsed_seconds, float)


def test_offline_restore_is_fast():
    e, mid = _run()
    assert e.restore(mid, _GOOD).elapsed_seconds < 0.5     # NFR-003-02 / SC-008


# ============================================================ US6 — release old sandbox

def test_old_head_sandbox_released():
    e = Engine(FakeProvider())
    e.start()
    h0 = e.live["root"].id
    s1 = e.step("echo hi > f", "step").step_id
    assert h0 in e.p.live
    r = e.restore("root")
    assert r.error is None and r.head_moved is True
    assert h0 not in e.p.live                              # FR-003-07
    assert s1 not in e.live                                # stale working entry dropped
    assert e.run.get(s1) is not None and e.run.get(s1).snapshot is not None  # preserved


def test_live_count_grows_by_at_most_one():
    e, mid = _run()
    before = len(e.p.live)
    e.restore(mid, _GOOD)
    assert len(e.p.live) <= before + 1                     # SC-006


def test_old_head_checkpoint_snapshot_untouched():
    e, mid = _run()
    tail_id = e.run.head
    snap_before = e.run.get(tail_id).snapshot
    e.restore(mid, _GOOD)
    assert e.run.get(tail_id).snapshot == snap_before


def test_ordered_calls_are_fixed():
    e = Engine(FakeProvider())
    e.start()
    e.step("echo hi > f", "step")
    e.p.calls.clear()
    e.restore("root", RestoreCheck(before=[("cat f", "")], after=[("cat f", "hi")]))
    assert [c.operation for c in e.p.calls] == ["branch", "run", "run", "destroy"]
