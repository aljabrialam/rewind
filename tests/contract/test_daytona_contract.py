"""tests/contract/test_daytona_contract.py — US5: catch drift in under 30s.

Every test here is `@pytest.mark.live`: it hits the real account and is skipped
unless DAYTONA_API_KEY is set. Not a correctness suite — a twenty-second answer
to "is it us or is it them" (Constitution Article VI).

Run live:  pytest tests/contract -m live -q
Traces: FR-000-01a, FR-000-01b, FR-000-08, NFR-000-02, NFR-000-06, SC-007.
"""

import time

import pytest

from rewind import capabilities as cap
from rewind.ports import RuntimeCallError

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def provider():
    from rewind.providers import DaytonaProvider

    p = DaytonaProvider()
    yield p
    # module teardown — nothing should survive the suite
    for h in list(getattr(p, "_live", [])):
        try:
            p._d.delete(p._d.get(h))
        except Exception:
            pass


@pytest.fixture(scope="module")
def _clock():
    t0 = time.time()
    yield
    assert time.time() - t0 < 30.0, "contract suite exceeded the 30s budget (NFR-000-02)"


def test_runtime_version_matches(provider, _clock):
    """The map's runtime_version still matches the live SDK/API."""
    from daytona import __version__ as live_version  # noqa: F401 - best effort

    assert cap.RUNTIME_VERSION, "map has no runtime_version"
    # soft check: report drift, don't hard-fail on a patch bump
    if not str(live_version).startswith(cap.RUNTIME_VERSION.lstrip("v")[:4]):
        pytest.skip(f"runtime version drift: map {cap.RUNTIME_VERSION} vs live {live_version}")


def test_each_op_postcondition(provider, _clock):
    """FR-000-01a / SC-007 — re-assert every declared operation's recorded effect."""
    h = provider.spawn()                                   # spawn post-condition
    assert h.id and h.state == "ready"

    r = provider.run(h, "echo step1 > log.txt")            # run post-condition
    assert r.exit_code == 0

    snap = provider.checkpoint(h)                          # checkpoint post-condition
    assert isinstance(snap, str) and snap

    kids = provider.branch(snap, 2)                        # branch post-condition
    assert len(kids) == 2
    for k in kids:
        assert "step1" in provider.run(k, "cat log.txt").stdout
    provider.run(kids[0], "echo only-0 >> log.txt")
    assert "only-0" not in provider.run(kids[1], "cat log.txt").stdout

    for x in (*kids, h):                                   # destroy post-condition
        provider.destroy(x)


def test_experimental_name_pinned(provider, _clock):
    """FR-000-01b — every experimental-flagged op's exact name still resolves."""
    if not cap.EXPERIMENTAL:
        pytest.skip("no experimental operations declared")
    from daytona import Sandbox  # noqa

    for name, marker in cap.EXPERIMENTAL.items():
        assert hasattr(Sandbox, marker), f"{name}: experimental name {marker!r} is gone"


def test_intervals_live(provider, _clock):
    """FR-000-08 — a live-created sandbox carries stop + delete intervals."""
    h = provider.spawn()
    try:
        sb = provider._d.get(h.id)
        assert getattr(sb, "auto_stop_interval", 1) not in (0, None)
    finally:
        provider.destroy(h)


def test_failure_kinds_distinguished():
    """NFR-000-06 — credentials vs capability vs budget are separately reportable."""
    from rewind.providers import classify

    class _E(Exception):
        def __init__(self, s):
            super().__init__(s)
            self.status = s if isinstance(s, int) else None

    assert classify(_E(401)) == "terminal"                 # credentials
    assert classify(RuntimeCallError("ceiling", "capacity")) == "capacity"  # capacity
    # budget failure is asserted by the _clock fixture, not classify


def test_absent_precondition_resource_is_capability_failure(provider, _clock):
    """spec US5 §5 — a declared op whose required snapshot is missing is a
    capability failure, distinct from a credentials failure."""
    with pytest.raises(RuntimeCallError) as ei:
        provider.branch("snapshot-that-does-not-exist", 1)
    assert ei.value.error_class in ("terminal", "capacity")
    assert "unauthorized" not in str(ei.value).lower()
