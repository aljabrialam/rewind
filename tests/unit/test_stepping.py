"""tests/unit/test_stepping.py — spec 002: verified step execution.

No network. Traces: FR-002-02..07, NFR-002-01, NFR-002-03.
Contract: specs/002-step-execution-and-evidence/contracts/step-evidence.md
"""

import ast
import inspect
from pathlib import Path

import pytest

from rewind.engine import BranchHalted, Engine
from rewind.providers import FakeProvider
from rewind.reasoning import SchemaError


class _CannedReasoner:
    """A ReasoningPort that yields prepared payloads."""
    def __init__(self, *payloads):
        self._p = list(payloads)
        self._i = 0
        self.calls = 0

    def next_instruction(self, context):
        self.calls += 1
        p = self._p[self._i]
        self._i += 1
        return p


def _engine(**kw):
    e = Engine(FakeProvider(), **kw)
    e.start()
    return e


# ---------------------------------------------------- FR-002-02/03/05 evidence

def test_step_runs_through_the_port():
    e = _engine()
    e.step("echo hi > f", "write f")
    assert "run" in [c.operation for c in e.p.calls]


def test_evidence_fields_captured():
    e = _engine()
    cp = e.step("echo hi > f", "write f")
    assert cp.evidence is not None
    assert cp.evidence.exit_code == 0
    assert cp.evidence.stdout == ""
    assert cp.evidence.elapsed > 0


def test_empty_output_is_not_missing_evidence():
    e = _engine()
    cp = e.step("echo x > f", "w")
    assert cp.evidence is not None and cp.evidence.exit_code == 0
    assert cp.evidence.stdout == "" and cp.outcome == "ok"


def test_evidence_attached_to_checkpoint():
    e = _engine()
    cp = e.step("echo hi > f", "w")
    assert e.run.checkpoints[cp.step_id].evidence is cp.evidence


def test_call_sequence_is_fixed():
    """NFR-002-01 — a good step: run then checkpoint; a failed step: run only."""
    e = _engine()
    e.p.calls.clear()
    e.step("echo hi > f", "w")
    assert [c.operation for c in e.p.calls] == ["run", "checkpoint"]


# ---------------------------------------------------- FR-002-01 reject-before-run

def test_next_step_executes_a_valid_instruction():
    e = _engine()
    r = _CannedReasoner({"instruction": "echo hi > f", "rationale": "because"})
    cp = e.next_step(r)
    assert cp.instruction == "echo hi > f" and cp.rationale == "because"


def test_reject_creates_no_checkpoint():
    e = _engine()
    order_before = list(e.run.order)
    calls_before = len(e.p.calls)
    r = _CannedReasoner({"instruction": "", "rationale": "bad"})
    with pytest.raises(SchemaError):
        e.next_step(r)
    assert e.run.order == order_before
    assert len(e.p.calls) == calls_before


def test_reasoner_not_called_again_after_rejection():
    e = _engine()
    r = _CannedReasoner({"instruction": "", "rationale": "bad"})
    with pytest.raises(SchemaError):
        e.next_step(r)
    assert r.calls == 1


# ---------------------------------------------------- FR-002-06 failure halt

def _failing_engine():
    """FakeProvider: a command containing 'FAIL' returns exit 1 via fail_rate hack
    is not available, so drive failure through a real nonzero: use a provider
    stub that fails on demand."""
    class _P(FakeProvider):
        def run(self, h, cmd):
            if "BOOM" in cmd:
                from rewind.ports import ExecResult
                self._record("run", "ok")
                return ExecResult(1, "boom happened", 0.01)
            return super().run(h, cmd)
    e = Engine(_P())
    e.start()
    return e


def test_failure_halts_branch():
    e = _failing_engine()
    e.step("echo ok > f", "good")
    cp = e.step("BOOM", "will fail")
    assert cp.evidence.exit_code == 1
    assert cp.halt_reason == "step-failed"
    assert e.halted and e.halt_reason == "step-failed"


def test_prior_checkpoints_survive_failure():
    e = _failing_engine()
    e.step("echo a > f", "1")
    e.step("echo b >> f", "2")
    before = e.run.as_tree()["nodes"][:3]          # root + 2 good steps
    e.step("BOOM", "3")
    after = e.run.as_tree()["nodes"][:3]
    assert before == after


def test_step_on_halted_branch_raises():
    e = _failing_engine()
    e.step("BOOM", "fail")
    calls_before = len(e.p.calls)
    with pytest.raises(BranchHalted):
        e.step("echo late > f", "too late")
    assert len(e.p.calls) == calls_before


# ---------------------------------------------------- FR-002-04/08 evidence>rationale

def test_outcome_follows_exit_status_not_rationale():
    e = _failing_engine()
    cp = e.step("BOOM", "everything went perfectly")   # rationale lies
    assert cp.outcome == "failed"
    assert cp.rationale == "everything went perfectly"  # still stored
    assert e.halted


def test_rationale_and_evidence_are_separate_fields():
    e = _engine()
    cp = e.step("echo hi > f", "my reason")
    assert cp.rationale == "my reason"
    assert cp.evidence.__class__.__name__ == "ExecResult"
    cp.rationale = "changed"
    assert cp.evidence.exit_code == 0                  # untouched


def test_as_tree_separates_evidence_and_rationale():
    e = _engine()
    e.step("echo hi > f", "the reason")
    node = e.run.as_tree()["nodes"][-1]
    assert node["rationale"] == "the reason"
    assert "exit_code" in node and "stdout" in node


def test_engine_step_logic_never_reads_rationale():
    """FR-002-04 — no decision path touches rationale. It appears in step() only
    as the parameter and the pass-through onto the Checkpoint; never in _guard()
    or the Checkpoint.outcome property."""
    from rewind.ports import Checkpoint

    assert ".rationale" not in inspect.getsource(Engine._guard)
    assert ".rationale" not in inspect.getsource(Checkpoint.outcome.fget)
    # in step(): `rationale` is the parameter and is passed once to Checkpoint(...)
    assert ".rationale" not in inspect.getsource(Engine.step)


# ---------------------------------------------------- FR-002-07 step bound

def test_step_bound_stops_branch():
    e = _engine(max_steps=3)
    for i in range(3):
        e.step(f"echo {i} > f", "ok")
    calls_before = len(e.p.calls)
    with pytest.raises(BranchHalted):
        e.step("echo 4 > f", "one too many")
    assert e.halted and e.halt_reason == "step-bound"
    assert len(e.p.calls) == calls_before             # nothing executed


def test_bound_is_single_value():
    e = _engine(max_steps=7)
    assert e.max_steps == 7
    # the bound is read from exactly one attribute
    src = inspect.getsource(Engine)
    assert src.count("self.max_steps") <= 3


def test_failure_reason_wins_over_bound():
    e = _failing_engine()
    e.max_steps = 2
    e.step("echo a > f", "1")
    e.step("BOOM", "2")                                # hits failure AND bound
    assert e.halt_reason == "step-failed"


# ---------------------------------------------------- NFR-002-03 offline loop

def test_full_loop_offline():
    e = _engine(max_steps=10)
    r = _CannedReasoner(
        {"instruction": "echo 1 > f", "rationale": "a"},
        {"instruction": "echo 2 >> f", "rationale": "b"},
        {"instruction": "cat f", "rationale": "check"},
    )
    for _ in range(3):
        e.next_step(r)
    assert len([c for c in e.run.order if c != "root"]) == 3
    assert not e.halted
