"""tests/unit/test_lifecycle.py — offline behaviour of the port.

US2 (runs offline, equivalent to recorded live) and US3 (bounded + always
cleaned up). No network. Run: pytest tests/unit -q
"""

import json
from pathlib import Path

import pytest

from rewind import capabilities as cap
from rewind.ports import Handle, UnconfirmedDestroyLeak
from rewind.providers import FakeProvider
from rewind.recording import RecordingProvider, ReplayProvider

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "daytona"


def _live_fixtures():
    return [f for f in FIXTURES.glob("*.json")]


# ============================================================ US2: offline parity

def test_recording_then_replay_round_trips(tmp_path):
    """The mechanism: record a run, replay it with no network, same results."""
    rec = RecordingProvider(FakeProvider(), fixtures_dir=tmp_path)
    h = rec.spawn()
    rec.run(h, "echo step1 > log.txt")
    snap = rec.checkpoint(h)
    kids = rec.branch(snap, 2)
    for k in kids:
        rec.destroy(k)
    rec.destroy(h)

    replay = ReplayProvider(fixtures_dir=tmp_path)
    h2 = replay.spawn()
    assert isinstance(h2, Handle) and h2.id == h.id
    assert replay.run(h2, "anything").exit_code == 0
    assert isinstance(replay.checkpoint(h2), str)
    assert len(replay.branch("s", 2)) == 2


def test_every_fixture_carries_provenance(tmp_path):
    """NFR-000-03 — a fixture is only ever produced by a real run: it has
    recorded_at + runtime_version. Checked on freshly captured files and on any
    committed live fixtures."""
    rec = RecordingProvider(FakeProvider(), fixtures_dir=tmp_path)
    rec.destroy(rec.spawn())
    produced = list(tmp_path.glob("*.json"))
    assert produced
    for f in produced + _live_fixtures():
        blob = json.loads(f.read_text())
        assert blob["recorded_at"] and blob["runtime_version"], f"{f} has no provenance"


@pytest.mark.skipif(not _live_fixtures(), reason="no committed live fixtures yet (run tools/spine_test.py)")
def test_fake_matches_recorded_result():
    """FR-000-05 / SC-003 — the offline port's observable result matches the
    recorded live result for each declared operation."""
    fake = FakeProvider()
    for f in sorted(_live_fixtures()):
        blob = json.loads(f.read_text())
        op = blob["operation"]
        if op == "spawn":
            assert fake.spawn().id
        elif op == "run" and blob["result"]:
            got = fake.run(Handle(id="x", sandbox_class="container"), blob["args"].get("cmd", "echo"))
            assert (got.exit_code == 0) == (blob["result"]["exit_code"] == 0)


def test_fake_latency_configurable():
    """NFR-000-04 — observed delay tracks the configured latency."""
    import time
    fast = FakeProvider(latency=0.0)
    slow = FakeProvider(latency=0.05)
    t0 = time.time(); fast.spawn(); fast_dt = time.time() - t0
    t0 = time.time(); slow.spawn(); slow_dt = time.time() - t0
    assert slow_dt >= 0.05 > fast_dt


def test_fake_failure_rate_configurable():
    """NFR-000-04 — a fail_rate of 1.0 fails every run, classified."""
    p = FakeProvider(fail_rate=1.0)
    h = p.spawn()
    r = p.run(h, "anything")
    assert not r.ok


# ============================================================ US3: bounded lifecycle

def test_intervals_attached_on_create():
    """FR-000-08 — every created sandbox carries stop + delete intervals."""
    p = FakeProvider()
    h = p.spawn()
    assert h.id in p.stop_interval and h.id in p.delete_interval
    kids = p.branch(p.checkpoint(h), 2)
    for k in kids:
        assert k.id in p.stop_interval and k.id in p.delete_interval


def test_created_sandbox_is_ready_before_handoff():
    """FR-000-08a — the handle is not returned until it accepts a command."""
    p = FakeProvider()
    h = p.spawn()
    assert h.state == "ready"


def test_not_ready_fails_creation_and_destroys():
    """FR-000-08a — never hand back a sandbox that is not command-ready."""
    p = FakeProvider(never_ready=True)
    with pytest.raises(Exception):
        p.spawn()
    assert not p.live                      # the half-created sandbox was destroyed


def test_ceiling_blocks_then_capacity():
    """FR-000-11 + clarification Q1 — surplus fails `capacity` after the bounded
    wait; siblings created before the ceiling stay live."""
    p = FakeProvider(ceiling=2, slot_wait=0.05)
    a = p.spawn()
    b = p.spawn()
    with pytest.raises(Exception) as ei:
        p.spawn()
    assert getattr(ei.value, "error_class", None) == "capacity"
    assert a.id in p.live and b.id in p.live       # siblings untouched
    assert len(p.live) == 2                        # ceiling never breached


def test_bounds_are_declared_constants():
    """NFR-000-05 — the waits/retries come from capabilities, not magic numbers."""
    assert cap.READINESS_WAIT > 0 and cap.SLOT_WAIT > 0
    assert cap.DESTROY_RETRIES >= 1 and cap.DESTROY_RETRY_GAP >= 0


def test_destroy_retry_then_leak():
    """FR-000-09 — an unconfirmed destroy is retried, then recorded as a leak
    that still counts against the ceiling; a terminal error is surfaced."""
    p = FakeProvider(ceiling=3, destroy_always_fails=True)
    h = p.spawn()
    with pytest.raises(Exception) as ei:
        p.destroy(h)
    assert getattr(ei.value, "error_class", None) == "terminal"
    assert len(p.leaks) == 1 and isinstance(p.leaks[0], UnconfirmedDestroyLeak)
    assert p.leaks[0].sandbox_id == h.id
    assert p.leaks[0].retries_attempted == cap.DESTROY_RETRIES
    assert p.live_count == 1                        # leak still counts


def test_destroy_retry_succeeds_within_bound():
    """A transient destroy failure that clears within the retry bound is not a leak."""
    p = FakeProvider(ceiling=3, destroy_fails_times=2)
    h = p.spawn()
    p.destroy(h)
    assert not p.leaks and h.id not in p.live and p.live_count == 0


def test_cleanup_runs_even_when_using_op_raises():
    """FR-000-09 — destroy is attempted on the raise path."""
    p = FakeProvider()
    h = p.spawn()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        pass
    finally:
        p.destroy(h)
    assert h.id not in p.live
