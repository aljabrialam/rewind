"""tests/contract/test_critic_contract.py — spec 005 live checks.

@pytest.mark.live — real sandboxes + a real reasoning endpoint. Skipped without
credentials. Parity + the bounded-wait budget, not correctness.
Traces: NFR-005-03, NFR-005-04.
"""

import os
import time
from collections import Counter

import pytest

from rewind import capabilities
from rewind.engine import Engine

pytestmark = pytest.mark.live


class _Strat:
    def __init__(self, *ins):
        self._q, self._i = list(ins), 0

    def next_instruction(self, context):
        s = self._q[self._i % len(self._q)]
        self._i += 1
        return {"instruction": s, "rationale": "branch"}


class _FirstCritic:
    """Picks the first branch; scores every id. Knows the ids up front."""
    def __init__(self, ids):
        self.ids = list(ids)

    def next_instruction(self, ctx):
        return {"chosen": self.ids[0],
                "scores": {i: 1.0 for i in self.ids}, "reason": "exit 0 output ok"}


def _round(provider, critic_factory):
    e = Engine(provider)
    e.start()
    e.step("echo base > f", "base")
    fo = e.fan_out(e.run.head, _Strat("echo a >> f", "echo b >> f", "echo c >> f"), 3)
    critic = critic_factory([c.step_id for c in fo.children])
    e.p.calls.clear()
    t0 = time.time()
    res = e.judge_and_promote(fo.children, critic)
    dt = time.time() - t0
    ops = Counter(c.operation for c in e.p.calls)
    e.shutdown()
    return ops, dt, res


def test_call_counts_match_live():
    """NFR-005-04 — provider op counts for a round are the same on both providers."""
    from rewind.providers import FakeProvider

    fake_ops, _, fake_res = _round(FakeProvider(), _FirstCritic)
    assert fake_ops.get("branch", 0) == 1 and fake_ops.get("run", 0) == 0
    assert fake_res["error"] is None

    if not (os.environ.get("DAYTONA_API_KEY") and os.environ.get("LLM_API_KEY")):
        pytest.skip("DAYTONA_API_KEY / LLM_API_KEY not set")
    from rewind.providers import DaytonaProvider
    from rewind.reasoning import LiveReasoner

    live_ops, dt, res = _round(DaytonaProvider(), lambda _ids: LiveReasoner())
    assert live_ops.get("branch", 0) == fake_ops.get("branch", 0)
    assert res["error"] is None
    assert dt < capabilities.CRITIC_WAIT + 15.0        # NFR-005-03


@pytest.mark.skipif(not (os.environ.get("LLM_API_KEY") and os.environ.get("DAYTONA_API_KEY")),
                    reason="LLM_API_KEY / DAYTONA_API_KEY not set")
def test_round_within_budget():
    from rewind.providers import DaytonaProvider
    from rewind.reasoning import LiveReasoner

    _, dt, _ = _round(DaytonaProvider(), lambda _ids: LiveReasoner())
    assert dt < capabilities.CRITIC_WAIT + 15.0
