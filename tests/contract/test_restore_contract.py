"""tests/contract/test_restore_contract.py — spec 003, US1/US5/US6 live checks.

@pytest.mark.live — hits real sandboxes, skipped without DAYTONA_API_KEY.
Not correctness — parity + budget drift.
Traces: NFR-003-02, NFR-003-03.
"""

import os

import pytest

from rewind.engine import Engine, RestoreCheck

pytestmark = pytest.mark.live


def _restore_calls(provider):
    e = Engine(provider)
    e.start()
    e.step("echo step1 > log.txt", "1")
    mid = e.run.head
    e.step("echo step2 >> log.txt", "2")
    e.p.calls.clear()
    r = e.restore(mid, RestoreCheck(before=[("cat log.txt", "step1")],
                                    after=[("cat log.txt", "step2")]))
    ops = [c.operation for c in e.p.calls]
    e.shutdown()
    return ops, r


def test_ordered_calls_match_live():
    """NFR-003-03 — the restore's ordered port calls are the same on both providers."""
    from rewind.providers import FakeProvider

    fake_ops, _ = _restore_calls(FakeProvider())
    assert fake_ops == ["branch", "run", "run", "destroy"]

    if not os.environ.get("DAYTONA_API_KEY"):
        pytest.skip("DAYTONA_API_KEY not set")
    from rewind.providers import DaytonaProvider

    live_ops, r = _restore_calls(DaytonaProvider())
    assert live_ops == fake_ops
    assert r.error is None and r.verification.status == "verified"


@pytest.mark.skipif(not os.environ.get("DAYTONA_API_KEY"), reason="DAYTONA_API_KEY not set")
def test_live_restore_within_budget():
    """NFR-003-02 — a live restore fits inside a two-minute demo script."""
    from rewind.providers import DaytonaProvider

    _, r = _restore_calls(DaytonaProvider())
    assert r.elapsed_seconds < 20.0, f"restore took {r.elapsed_seconds:.1f}s"
