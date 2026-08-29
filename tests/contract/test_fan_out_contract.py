"""tests/contract/test_fan_out_contract.py — spec 004, US2/US6 live checks.

@pytest.mark.live — hits real sandboxes, skipped without DAYTONA_API_KEY.
Not correctness — parity + wall-clock budget drift.
Traces: NFR-004-01, NFR-004-03.
"""

import os
from collections import Counter

import pytest

from rewind.engine import Engine

pytestmark = pytest.mark.live


class _Strategist:
    def __init__(self, *instructions):
        self._q = [{"instruction": i, "rationale": "branch"} for i in instructions]
        self._i = 0

    def next_instruction(self, context):
        p = self._q[self._i % len(self._q)]
        self._i += 1
        return p


def _fan(provider):
    e = Engine(provider)
    e.start()
    e.step("echo base > f", "base")
    e.p.calls.clear()
    res = e.fan_out(e.run.head, _Strategist("echo a >> f", "echo b >> f", "echo c >> f"), 3)
    counts = Counter(c.operation for c in e.p.calls)
    e.shutdown()
    return counts, res


def test_op_counts_match_live():
    """NFR-004-03 — per-operation call counts are the same on both providers."""
    from rewind.providers import FakeProvider

    fake_counts, _ = _fan(FakeProvider())
    assert fake_counts == {"branch": 3, "run": 3, "checkpoint": 3, "destroy": 3}

    if not os.environ.get("DAYTONA_API_KEY"):
        pytest.skip("DAYTONA_API_KEY not set")
    from rewind.providers import DaytonaProvider

    live_counts, res = _fan(DaytonaProvider())
    assert live_counts == fake_counts
    assert res.ran == 3 and res.error is None


@pytest.mark.skipif(not os.environ.get("DAYTONA_API_KEY"), reason="DAYTONA_API_KEY not set")
def test_wall_clock_within_budget():
    """NFR-004-01 — total time ≈ one branch, not 3×, and fits a 2-minute demo."""
    from rewind.providers import DaytonaProvider

    _, res = _fan(DaytonaProvider())
    assert res.elapsed_seconds < 30.0, f"fan-out took {res.elapsed_seconds:.1f}s"
