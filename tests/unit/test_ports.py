"""tests/unit/test_ports.py — no network. Run: pytest tests/unit -q"""

import pytest

from rewind.ports import WORKSPACE
from rewind.providers import FakeProvider


def test_branch_children_carry_parent_state():
    """FR-004-02 — the whole product depends on this."""
    p = FakeProvider()
    head = p.spawn()
    p.run(head, "echo step1 > log.txt")
    p.run(head, "echo step2 >> log.txt")
    snap = p.checkpoint(head)

    kids = p.branch(snap, 3)
    assert len(kids) == 3
    for k in kids:
        assert "step1" in p.run(k, "cat log.txt").stdout
        assert "step2" in p.run(k, "cat log.txt").stdout


def test_branches_diverge_after_creation():
    """FR-004-06 — evidence must be independent per branch."""
    p = FakeProvider()
    head = p.spawn()
    p.run(head, "echo base > log.txt")
    snap = p.checkpoint(head)
    a, b = p.branch(snap, 2)

    p.run(a, "echo only-a >> log.txt")
    assert "only-a" in p.run(a, "cat log.txt").stdout
    assert "only-a" not in p.run(b, "cat log.txt").stdout


def test_restore_returns_prior_state():
    """FR-003-02 — state after the checkpoint is absent in the restored branch."""
    p = FakeProvider()
    head = p.spawn()
    p.run(head, "echo step1 > log.txt")
    snap = p.checkpoint(head)
    p.run(head, "echo step2 >> log.txt")          # after the checkpoint

    restored = p.branch(snap, 1)[0]
    out = p.run(restored, "cat log.txt").stdout
    assert "step1" in out and "step2" not in out


def test_cleanup_always_runs():
    """FR-000-09 — the credit-burn bug."""
    p = FakeProvider()
    h = p.spawn()
    assert h.id in p.live
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        pass
    finally:
        p.destroy(h)
    assert h.id not in p.live


def test_failure_does_not_abort_others():
    """FR-004-08."""
    p = FakeProvider(fail_rate=1.0)
    head = FakeProvider().spawn()
    results = [p.run(head, "anything") for _ in range(3)]
    assert all(r.exit_code == 1 for r in results)
    assert not results[0].ok
