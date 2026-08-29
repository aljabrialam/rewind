"""tests/unit/test_run_tree.py — spec 001: the run/checkpoint tree.

Pure logic. No network, no credentials, no sandbox (NFR-001-01).
Contract: specs/001-run-and-checkpoint-model/contracts/run-tree.md
"""

import sys

import pytest

from rewind.engine import Engine, Run
from rewind.ports import Checkpoint


def _cp(index, sid, instr, parent, **kw):
    return Checkpoint(index=index, step_id=sid, instruction=instr, parent_id=parent, **kw)


def _run_with_steps(n, *, snapshots=True):
    """root + n linear steps, each live with a snapshot."""
    r = Run()
    r.add(_cp(0, "root", "(start)", None, sandbox_id="sb-0",
             snapshot="snap-0" if snapshots else None))
    for i in range(1, n + 1):
        r.add(_cp(i, f"s{i}", f"echo {i}", r.head, sandbox_id=f"sb-{i}",
                  snapshot=f"snap-{i}" if snapshots else None))
    return r


# ================================================= US1 — addressable moments

def test_run_is_ordered_steps():
    r = _run_with_steps(3)
    assert r.order == ["root", "s1", "s2", "s3"]
    assert [r.get(i).index for i in r.order] == [0, 1, 2, 3]


def test_step_carries_index_instruction_state():
    r = _run_with_steps(1)
    s1 = r.get("s1")
    assert s1.index == 1 and s1.instruction == "echo 1" and s1.state == "live"


def test_identifier_stable_after_run_advances():
    r = _run_with_steps(2)
    early = r.order[1]                       # "s1"
    for i in range(3, 12):
        r.add(_cp(i, f"s{i}", f"echo {i}", r.head, sandbox_id=f"sb-{i}", snapshot=f"snap-{i}"))
    assert early in r.checkpoints
    assert r.get(early).instruction == "echo 1" and r.get(early).index == 1


def test_path_to_is_ordered_root_to_node():
    r = _run_with_steps(3)
    path = r.path_to("s3")
    assert [c.step_id for c in path] == ["root", "s1", "s2", "s3"]
    for prev, nxt in zip(path, path[1:]):
        assert nxt.parent_id == prev.step_id


def test_lookup_unknown_id_returns_nothing():
    r = _run_with_steps(1)
    assert r.get("nope") is None
    assert r.path_to("nope") == []


def test_checkpoint_records_snapshot_reference():
    r = _run_with_steps(1)
    assert r.get("s1").snapshot == "snap-1"          # FR-001-02


# ================================================= US2 — it is a tree

def test_parent_can_have_two_children():
    r = _run_with_steps(1)
    r.add(_cp(2, "a", "branch a", "s1", sandbox_id="sb-a", snapshot="snap-a"))
    r.add(_cp(3, "b", "branch b", "s1", sandbox_id="sb-b", snapshot="snap-b"))
    assert r.get("s1").children == ["a", "b"]
    assert r.get("a").parent_id == "s1" and r.get("b").parent_id == "s1"


def test_child_creation_does_not_mutate_parent():
    r = _run_with_steps(1)
    before = (r.get("s1").index, r.get("s1").instruction, r.get("s1").state)
    r.add(_cp(2, "a", "x", "s1", snapshot="snap-a"))
    r.add(_cp(3, "b", "y", "s1", snapshot="snap-b"))
    assert (r.get("s1").index, r.get("s1").instruction, r.get("s1").state) == before


def test_exactly_one_head():
    r = _run_with_steps(2)
    assert r.head == "s2"
    r.add(_cp(3, "a", "x", "s2", snapshot="snap-a"))
    assert r.head == "a"                              # exactly one, always


def test_checkpoint_has_parent_sandbox_and_created_at():
    r = _run_with_steps(1)
    s1 = r.get("s1")
    assert s1.parent_id == "root"
    assert s1.sandbox_id == "sb-1"
    assert isinstance(s1.created_at, str) and s1.created_at


def test_two_checkpoints_same_second_distinct_ids():
    """NFR-001-03 / SC-009 — ids do not depend on timestamp resolution."""
    r = Run()
    r.add(_cp(0, "root", "(start)", None, snapshot="s"))
    ids = set()
    for i in range(50):
        cp = _cp(i + 1, "", f"echo {i}", "root", snapshot="s")   # blank id => generated
        r.add(cp)
        ids.add(cp.step_id)
    assert len(ids) == 50
    # all created within the same wall-clock second in practice; ids still unique


# ================================================= US3 — restorability

def test_released_not_restorable():
    r = _run_with_steps(1)
    r.get("s1").state = "released"
    assert r.is_restorable("s1") is False


def test_unreachable_not_restorable():
    r = _run_with_steps(1)
    r.get("s1").state = "unreachable"
    assert r.is_restorable("s1") is False


def test_live_with_snapshot_is_restorable():
    r = _run_with_steps(1)
    assert r.is_restorable("s1") is True


def test_live_without_snapshot_not_restorable():
    r = _run_with_steps(1, snapshots=False)
    assert r.is_restorable("s1") is False


def test_restore_targets_excludes_released():
    r = _run_with_steps(3)
    r.get("s2").state = "released"
    targets = r.restore_targets()
    assert "s2" not in targets
    assert set(targets) == {"root", "s1", "s3"}


def test_set_head_refuses_released():
    r = _run_with_steps(2)
    r.get("s1").state = "released"
    with pytest.raises(ValueError, match="released"):
        r.set_head("s1")
    assert r.head == "s2"                             # unchanged


def test_set_head_refuses_unknown_and_no_snapshot():
    r = _run_with_steps(1, snapshots=False)
    with pytest.raises(ValueError, match="unknown"):
        r.set_head("ghost")
    with pytest.raises(ValueError, match="runtime state"):
        r.set_head("s1")


def test_set_head_accepts_restorable():
    r = _run_with_steps(3)
    r.set_head("s1")
    assert r.head == "s1"


# ================================================= US4 — branch terminal outcome

def test_branch_outcome_none_while_advancing():
    r = _run_with_steps(2)
    assert r.branch_outcome("s2") is None


def test_branch_outcome_succeeded():
    r = _run_with_steps(2)
    r.mark_terminal("s2", "succeeded")
    assert r.branch_outcome("s2") == "succeeded"


def test_mark_terminal_rejects_bad_value():
    r = _run_with_steps(1)
    with pytest.raises(ValueError):
        r.mark_terminal("s1", "kinda-worked")


def test_branch_outcome_failed_via_engine_step():
    class _P(_FakeFail):
        pass
    e = Engine(_P())
    e.start()
    cp = e.step("BOOM", "will fail")
    assert e.run.branch_outcome(cp.step_id) == "failed"
    assert cp.terminal == "failed"


def test_branch_outcome_abandoned_via_promote():
    from rewind.providers import FakeProvider
    e = Engine(FakeProvider())
    e.start()
    e.step("echo base > f", "base")
    base = e.run.head
    kids = e.branch_from(base, ["echo a > f", "echo b > f"])
    e.promote(kids[0].step_id, [kids[1].step_id])
    assert e.run.branch_outcome(kids[1].step_id) == "abandoned"
    assert e.run.get(kids[1].step_id).state == "released"


def test_single_step_run_that_fails():
    """Folded edge case — root + one failed checkpoint; root intact."""
    e = Engine(_FakeFail())
    e.start()
    cp = e.step("BOOM", "the only step")
    assert e.run.order == ["root", cp.step_id]
    assert cp.terminal == "failed" and cp.outcome == "failed"
    assert e.run.get("root").state == "live"


# ================================================= US5 — renderable form

_ALL_NODE_KEYS = {
    "id", "index", "instruction", "parent", "children", "sandbox", "state",
    "snapshot", "created_at", "exit_code", "stdout", "outcome", "terminal", "rationale",
}


def test_as_tree_has_all_fields():
    r = _run_with_steps(2)
    r.add(_cp(3, "a", "x", "s1", snapshot="snap-a"))
    tree = r.as_tree()
    assert tree["head"] == "a"
    for node in tree["nodes"]:
        assert set(node) == _ALL_NODE_KEYS


def test_as_tree_root_only():
    r = Run()
    r.add(_cp(0, "root", "(start)", None, snapshot="s"))
    tree = r.as_tree()
    assert len(tree["nodes"]) == 1
    assert tree["nodes"][0]["children"] == [] and tree["head"] == "root"


def test_as_tree_nodes_in_order():
    r = _run_with_steps(3)
    assert [n["id"] for n in r.as_tree()["nodes"]] == r.order


def test_as_tree_children_referenced_by_id():
    r = _run_with_steps(1)
    r.add(_cp(2, "a", "x", "s1", snapshot="snap-a"))
    node_s1 = next(n for n in r.as_tree()["nodes"] if n["id"] == "s1")
    assert node_s1["children"] == ["a"]


# ================================================= NFR-001-02 integrity

def test_integrity_of_fresh_run():
    assert _run_with_steps(4).check_integrity() == []


def test_integrity_after_failure_abandon_and_shared_parent():
    """SC-010 — a messy run stays structurally sound."""
    from rewind.providers import FakeProvider
    e = Engine(FakeProvider())
    e.start()
    e.step("echo a > f", "1")
    e.step("echo b >> f", "2")
    parent = e.run.head
    kids = e.branch_from(parent, ["echo x > f", "echo y > f"])   # two from one parent
    e.promote(kids[0].step_id, [kids[1].step_id])                # kids[1] abandoned
    # a separate failed step
    e2 = Engine(_FakeFail())
    e2.start()
    e2.step("BOOM", "fail")
    assert e.run.check_integrity() == []
    assert e2.run.check_integrity() == []


def test_integrity_flags_a_broken_tree():
    r = _run_with_steps(2)
    r.get("s2").parent_id = "does-not-exist"
    assert r.check_integrity()                        # non-empty


# ================================================= NFR-001-01 / SC-008 purity

def test_no_runtime_import():
    """NFR-001-01 / SC-008 — importing the tree model pulls in no vendor SDK."""
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-c",
         "import rewind.engine, rewind.ports, sys; "
         "assert 'daytona' not in sys.modules, 'daytona imported'; "
         "assert 'openai' not in sys.modules, 'openai imported'; "
         "print('clean')"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "clean" in proc.stdout


# --- a tiny always-fails provider, offline -----------------------------------
from rewind.providers import FakeProvider  # noqa: E402
from rewind.ports import ExecResult        # noqa: E402


class _FakeFail(FakeProvider):
    def run(self, h, cmd):
        if "BOOM" in cmd:
            self._record("run", "ok")
            return ExecResult(1, "boom", 0.01)
        return super().run(h, cmd)
