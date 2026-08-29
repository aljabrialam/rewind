"""tests/unit/test_console_fixture.py — spec 006: the Console Fixture shape.

The ONLY automated test for spec 006. Constitution Article VI keeps UI rendering
out of automated testing; the ten FRs are signed off in
specs/006-timeline-console/checklists/visual-acceptance.md.

Contract: specs/006-timeline-console/contracts/console-fixture.md
"""

import json

from rewind.engine import Engine, console_fixture, rank_by_evidence
from rewind.providers import FakeProvider


class _Strat:
    def __init__(self, *ins):
        self._q, self._i = list(ins), 0

    def next_instruction(self, context):
        s = self._q[self._i % len(self._q)]
        self._i += 1
        return {"instruction": s, "rationale": f"try {s}"}


def _run_with_fanout():
    e = Engine(FakeProvider())
    e.start()
    e.step("echo step1 > log.txt", "write step1")
    e.step("echo step2 >> log.txt", "")               # no rationale
    parent = e.run.head
    fo = e.fan_out(parent, _Strat("echo a > f", "echo b > f", "echo c > f"), 3)
    v = rank_by_evidence(fo.children)
    return e, v


# ------------------------------------------------------------ FR-006-01 / 06 / 08

def test_has_head_and_ordered_nodes():
    e, _ = _run_with_fanout()
    d = console_fixture(e)
    assert d["head"] and d["head"] in {n["id"] for n in d["nodes"]}
    assert [n["id"] for n in d["nodes"]] == e.run.order        # SC-001


def test_nodes_carry_exit_and_stdout():
    e, _ = _run_with_fanout()
    for n in console_fixture(e)["nodes"]:
        assert "exit_code" in n and "stdout" in n              # FR-006-06


def test_rationale_field_passthrough():
    e, _ = _run_with_fanout()
    nodes = {n["instruction"]: n for n in console_fixture(e)["nodes"]}
    assert nodes["echo step1 > log.txt"]["rationale"] == "write step1"
    assert not nodes["echo step2 >> log.txt"]["rationale"]     # absent -> falsy (SC-003)


# ------------------------------------------------------------ FR-006-07 counters

def test_live_sandboxes_is_provider_count():
    e, _ = _run_with_fanout()
    d = console_fixture(e)
    assert d["live_sandboxes"] == len(e.p.live)                # not a node count (C2)


def test_session_elapsed_present():
    e, _ = _run_with_fanout()
    se = console_fixture(e)["session_elapsed"]
    assert isinstance(se, float) and se >= 0                   # C3


def test_fixture_is_json_serialisable():
    e, v = _run_with_fanout()
    d = console_fixture(e, verdict=v)
    assert json.loads(json.dumps(d))["verdict"]["reason"] == v["reason"]   # C9 / C5


# ------------------------------------------------------------ FR-006-05 / 02 branch progress

def test_branch_nodes_have_progress():
    e, _ = _run_with_fanout()
    d = console_fixture(e)
    child_count = {}
    for n in d["nodes"]:
        if n["parent"]:
            child_count[n["parent"]] = child_count.get(n["parent"], 0) + 1
    branch, plain = [], []
    for n in d["nodes"]:
        (branch if child_count.get(n["parent"], 0) > 1 else plain).append(n)
    assert branch
    for n in branch:
        assert n["progress"]["state"] in ("creating", "running", "done", "failed")
        assert n["progress"]["elapsed_seconds"] >= 0
    for n in plain:
        assert "progress" not in n                             # C7


def test_branch_nodes_identifiable_by_parent():
    e, _ = _run_with_fanout()
    d = console_fixture(e)
    branch_parents = {n["parent"] for n in d["nodes"] if "progress" in n}
    for p in branch_parents:
        assert sum(1 for n in d["nodes"] if n["parent"] == p) > 1   # FR-006-02


def test_recompute_reflects_advance():
    e = Engine(FakeProvider())
    e.start()
    e.step("echo a > f", "one")
    before = console_fixture(e)
    e.step("echo b > f", "two")
    after = console_fixture(e)
    assert len(after["nodes"]) == len(before["nodes"]) + 1
    assert after["session_elapsed"] >= before["session_elapsed"]   # NFR-006-02 / C10
