"""tests/unit/test_fan_out.py — spec 004: branch fan-out.

Offline. No network, no credentials.
Contract: specs/004-branch-fan-out/contracts/fan-out.md
"""

import time
from collections import Counter

import pytest

from rewind import capabilities
from rewind.engine import Engine
from rewind.ports import ExecResult
from rewind.providers import FakeProvider
from rewind.reasoning import SchemaError


class _Strategist:
    """A ReasoningPort yielding prepared strategies, counting calls."""
    def __init__(self, *instructions):
        self._q = [{"instruction": i, "rationale": f"try {i}"} for i in instructions]
        self._i = 0
        self.calls = 0

    def next_instruction(self, context):
        self.calls += 1
        p = self._q[self._i % len(self._q)]
        self._i += 1
        return p


class _FanFake(FakeProvider):
    def run(self, h, cmd):
        if "BOOM" in cmd:
            self._record("run", "ok")
            return ExecResult(1, "boom", 0.01)
        return super().run(h, cmd)


class _SlowRun(FakeProvider):
    def run(self, h, cmd):
        time.sleep(0.08)
        return super().run(h, cmd)




def _parent(provider=None):
    e = Engine(provider or FakeProvider())
    e.start()
    e.step("echo base > f", "base")
    return e, e.run.head


# ============================================================ US1 — three at once

def test_asks_reasoner_n_times():
    e, p = _parent()
    s = _Strategist("echo a > f", "echo b > f", "echo c > f")
    e.fan_out(p, s, 3)
    assert s.calls == 3


def test_rejects_bad_strategy_schema():
    e, p = _parent()
    order_before = list(e.run.order)
    s = _Strategist("")                       # empty instruction -> SchemaError
    with pytest.raises(SchemaError):
        e.fan_out(p, s, 2)
    assert e.run.order == order_before        # nothing created


def test_dedupes_and_reports_ran():
    e, p = _parent()
    s = _Strategist("echo a > f", "echo a > f", "echo c > f")
    res = e.fan_out(p, s, 3)
    assert res.requested == 3 and res.ran == 2 and len(res.children) == 2


def test_one_sandbox_per_strategy_from_parent():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert len(res.children) == 3
    assert all(c.parent_id == p for c in res.children)          # SC-001


def test_children_are_parent_children():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert e.run.get(p).children == [c.step_id for c in res.children]


def test_head_unchanged():
    e, p = _parent()
    before = e.run.head
    e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert e.run.head == before == p                            # SC-002


def test_refuses_non_restorable_parent():
    e, p = _parent()
    e.run.get(p).state = "released"
    res = e.fan_out(p, _Strategist("echo a > f"), 1)
    assert res.error == "released" and res.children == []


# ============================================================ US2 — parallel

def test_branches_run_concurrently():
    e, p = _parent(_SlowRun())
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert res.elapsed_seconds < 0.2                            # 3x0.08 sequential = 0.24 (SC-003)


def test_offline_fan_out_is_fast():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert res.elapsed_seconds < 0.5                            # SC-010


# ============================================================ US3 — derivation

def test_derivation_is_branch_by_default():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f"), 2)
    assert res.derivation == "branch"


def test_prefers_faster_derivation_when_declared(monkeypatch):
    monkeypatch.setattr(capabilities, "VERIFIED_OPS",
                        frozenset({"fork", "branch", "spawn", "run", "checkpoint", "destroy"}))
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f"), 2)
    assert res.derivation == "fork"


def test_derivation_recorded():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f"), 2)
    assert res.derivation == e._last_derivation                 # SC-009


# ============================================================ US4 — failure isolation

def test_failing_branch_isolated():
    e, p = _parent(_FanFake())
    res = e.fan_out(p, _Strategist("echo a > f", "BOOM", "echo c > f"), 3)
    assert len(res.children) == 3
    assert res.children[1].evidence.exit_code == 1
    assert res.children[0].evidence.exit_code == 0
    assert res.children[2].evidence.exit_code == 0              # SC-005


def test_failed_branch_terminal_is_failed():
    e, p = _parent(_FanFake())
    res = e.fan_out(p, _Strategist("echo a > f", "BOOM", "echo c > f"), 3)
    assert res.children[1].terminal == "failed"


def test_branch_creation_shortfall_reported():
    # root takes 1 slot; ceiling 3 leaves room for only 2 branch sandboxes.
    e, p = _parent(FakeProvider(ceiling=3))
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    real = [c for c in res.children if c.sandbox_id is not None]
    capped = [c for c in res.children if c.sandbox_id is None]
    assert len(real) == 2 and len(capped) == 1
    assert capped[0].terminal == "failed" and "capacity" in capped[0].evidence.stdout


# ============================================================ US5 — live visibility

def test_progress_reports_id_and_state():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert len(res.progress) == 3
    for row in res.progress:
        assert set(row) == {"checkpoint_id", "sandbox_id", "state"}
        assert row["state"] in ("done", "failed")               # SC-008


def test_progress_advances_creating_running_done():
    e, p = _parent()
    seen = []
    e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3, observer=seen.append)
    states = [{r["state"] for r in snap} for snap in seen]
    assert any("creating" in s for s in states)
    assert any("running" in s for s in states)
    assert states[-1] == {"done"}


def test_progress_sandbox_ids_are_verbatim():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    for i, row in enumerate(res.progress):
        assert row["sandbox_id"] == res.children[i].sandbox_id  # SC-007 / NFR-004-02
        assert row["sandbox_id"].startswith("fake-")


def test_as_dict_progress_is_structured():
    e, p = _parent()
    d = e.fan_out(p, _Strategist("echo a > f", "echo b > f"), 2).as_dict()
    assert isinstance(d["progress"], list) and all(isinstance(r, dict) for r in d["progress"])


# ============================================================ US6 — no leak

def test_all_branch_sandboxes_destroyed_on_success():
    e, p = _parent()
    before = len(e.p.live)
    e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert len(e.p.live) == before                              # SC-006


def test_all_destroyed_when_a_branch_fails():
    e, p = _parent(_FanFake())
    before = len(e.p.live)
    e.fan_out(p, _Strategist("echo a > f", "BOOM", "echo c > f"), 3)
    assert len(e.p.live) == before


def test_all_destroyed_when_operation_raises(monkeypatch):
    """A failure after the branch sandboxes exist still triggers the finally cleanup."""
    e, p = _parent()
    before = len(e.p.live)
    real_add, calls = e.run.add, [0]

    def boom(cp):
        calls[0] += 1
        if calls[0] == 2:
            raise RuntimeError("mid-fan-out failure")
        return real_add(cp)

    monkeypatch.setattr(e.run, "add", boom)
    with pytest.raises(RuntimeError):
        e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert len(e.p.live) == before                              # SC-006 — finally cleaned up


def test_ceiling_not_exceeded_during_fan_out():
    e, p = _parent(FakeProvider(ceiling=3))
    before = len(e.p.live)
    res = e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    assert sum(1 for c in res.children if c.sandbox_id) <= 2    # ceiling held (root has 1)
    assert len(e.p.live) == before


def test_op_counts_are_fixed():
    e, p = _parent()
    e.p.calls.clear()
    e.fan_out(p, _Strategist("echo a > f", "echo b > f", "echo c > f"), 3)
    counts = Counter(c.operation for c in e.p.calls)
    assert counts == {"branch": 3, "run": 3, "checkpoint": 3, "destroy": 3}  # NFR-004-03


def test_each_branch_has_independent_evidence():
    e, p = _parent()
    res = e.fan_out(p, _Strategist("echo A > f", "echo B > f", "cat f"), 3)
    ev = [c.evidence for c in res.children]
    assert ev[0] is not ev[1] is not ev[2]
    assert res.children[2].evidence.stdout.strip() == "base"    # cat f -> parent snapshot state
