"""tests/e2e/test_demo_path.py — spec 007: the live end-to-end demonstration path.

@pytest.mark.live — runs the whole demo path against the real sandbox runtime
with replayed reasoning. Skipped without DAYTONA_API_KEY + captured fixtures.
This is the top of the testing pyramid (Constitution Article VI).
Traces: FR-007-02, FR-007-05, FR-007-07, NFR-007-01.
"""

import os
from pathlib import Path

import pytest

from rewind.harness import enough_fixtures, run_demo

pytestmark = pytest.mark.live

_FIX = Path(__file__).resolve().parents[2] / "fixtures" / "reasoning"


def _reasoners():
    from rewind.reasoning import ReplayReasoner
    return ReplayReasoner(str(_FIX)), ReplayReasoner(str(_FIX / "critic"))


def _have_fixtures() -> bool:
    if not os.environ.get("DAYTONA_API_KEY"):
        return False
    s, c = _reasoners()
    return enough_fixtures(s, 3) and enough_fixtures(c, 1)


@pytest.mark.skipif(not _have_fixtures(),
                    reason="DAYTONA_API_KEY and fixtures/reasoning/ required")
def test_live_run_within_budget_no_leak():
    """FR-007-02/05/07 — live path, within budget, zero leak, exit-0 conditions."""
    from rewind.providers import DaytonaProvider

    strat, critic = _reasoners()
    provider = DaytonaProvider()
    res = run_demo(provider, strat, critic, budget=90.0)

    assert res.error is None, res.error
    assert res.seed_reproduced is True                # the seed's failure is real
    assert res.leak == []                             # FR-007-07 — nothing left live
    assert res.over_budget is False                   # FR-007-05
    assert res.path_seconds < 90.0
    assert res.ok is True
    assert res.stages[-2:] == ["teardown", "leak-check"]


@pytest.mark.skipif(not _have_fixtures(),
                    reason="DAYTONA_API_KEY and fixtures/reasoning/ required")
def test_path_uses_live_provider():
    """FR-007-02 — the demonstration path runs against DaytonaProvider, not the fake."""
    from rewind.providers import DaytonaProvider, FakeProvider

    strat, critic = _reasoners()
    provider = DaytonaProvider()
    assert not isinstance(provider, FakeProvider)
    res = run_demo(provider, strat, critic, budget=90.0)
    assert res.fixture_written and res.ok
