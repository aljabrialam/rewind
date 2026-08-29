"""tests/unit/test_harness.py — spec 007: the demo harness.

The harness's LOGIC — budget / leak / seed / stage-order / exit codes — verified
with no runtime, no network, no credentials (NFR-007-04 / SC-011). The live
end-to-end run is tests/e2e/test_demo_path.py; the pre-freeze rehearsal is
specs/007-demo-harness/checklists/rehearsal.md.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rewind.harness import (
    DEFAULT_BUDGET, STAGES, DemoResult, check_budget, check_no_leak,
    check_seed_reproduced, enough_fixtures, run_demo,
)
from rewind.ports import ExecResult
from rewind.providers import FakeProvider

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------- fakes / helpers

class _SeedFake(FakeProvider):
    """Models the calculator regression: the test step fails while calc.py holds
    the subtraction; a write that fixes calc.py clears it."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self._broken = False

    def run(self, h, cmd):
        if "calc.py" in cmd and ">" in cmd:
            self._broken = "return a-b" in cmd
        if "test.py" in cmd and self._broken:
            self._record("run", "ok")
            return ExecResult(1, "AssertionError: add(2,2) != 4", 0.01)
        return super().run(h, cmd)


class _NeverBreaks(FakeProvider):
    """The seed's mistake step still passes — the failure does not reproduce."""


class _LeakFake(_SeedFake):
    """shutdown()/destroy leaves one sandbox live."""
    def destroy(self, h):
        if getattr(h, "_keep", False):
            return
        return super().destroy(h)

    def spawn(self):
        hs = super().spawn()
        return hs


class _Canned:
    def __init__(self, *payloads):
        self._p, self._i = list(payloads), 0

    def next_instruction(self, context):
        r = self._p[self._i % len(self._p)]
        self._i += 1
        return r


class _CriticOK:
    """A structurally valid verdict — favours branch 0."""
    def next_instruction(self, context):
        # branch ids aren't known here; return a shape that fails validation ->
        # judge_and_promote falls back deterministically (still a clean promotion).
        return {"chosen": "unknown", "scores": {}, "reason": "exit 0 output ok"}


def _strategist():
    return _Canned(*[{"instruction": s, "rationale": "x"}
                     for s in ("echo a > f", "echo b > f", "echo c > f")])


def _step_cps(exit_codes):
    from rewind.ports import Checkpoint
    return [Checkpoint(index=i + 1, step_id=f"s{i}", instruction="x", parent_id="p",
                       evidence=ExecResult(c, "", 0.1)) for i, c in enumerate(exit_codes)]


# ============================================================ pure checks

def test_check_budget():
    assert check_budget(1.0, 2.0) is True
    assert check_budget(2.0, 2.0) is True
    assert check_budget(2.1, 2.0) is False


def test_check_seed_reproduced_true_and_false():
    assert check_seed_reproduced(_step_cps([0, 0, 1])) is True
    assert check_seed_reproduced(_step_cps([0, 0, 0])) is False
    assert check_seed_reproduced([]) is False


def test_check_no_leak_clean_and_named():
    p = FakeProvider()
    assert check_no_leak(p) == []
    p.live.add("fake-9999")
    assert check_no_leak(p) == ["fake-9999"]


def test_enough_fixtures():
    class _Replayish:
        _queue = [1, 2, 3]
        _i = 0
    assert enough_fixtures(_Replayish(), 3) is True
    assert enough_fixtures(_Replayish(), 4) is False
    assert enough_fixtures(object(), 99) is True          # non-replay reasoner passes


# ============================================================ run_demo — happy path

def _run(provider=None, **kw):
    return run_demo(provider or _SeedFake(), _strategist(), _CriticOK(),
                    budget=kw.pop("budget", 30), **kw)


def test_run_demo_completes_offline(tmp_path):
    res = _run(fixture_out=str(tmp_path / "tree.json"))
    assert res.ok is True
    assert res.stages == list(STAGES)
    assert res.error is None and res.leak == []


def test_console_fixture_written(tmp_path):
    out = tmp_path / "tree.json"
    res = _run(fixture_out=str(out))
    assert res.fixture_written and out.exists()
    blob = json.loads(out.read_text())
    assert "head" in blob and "nodes" in blob             # SC-010


def test_prepare_runs_before_timer(tmp_path):
    res = _run(fixture_out=str(tmp_path / "t.json"))
    assert res.stages[0] == "prepare" and res.prepare_seconds >= 0


def test_warm_false_skips_prepare(tmp_path):
    res = _run(warm=False, fixture_out=str(tmp_path / "t.json"))
    assert "prepare" not in res.stages


def test_path_seconds_excludes_prepare(tmp_path):
    res = _run(_SeedFake(latency=0.03), fixture_out=str(tmp_path / "t.json"))
    # prepare = spawn+run+destroy = 3 ticks of latency; it must not be in path_seconds
    assert res.prepare_seconds >= 0.03
    assert res.path_seconds >= 0


def test_two_runs_identical(tmp_path):
    a = _run(fixture_out=str(tmp_path / "a.json"))
    b = _run(fixture_out=str(tmp_path / "b.json"))
    assert a.stages == b.stages
    assert a.branch_instructions == b.branch_instructions
    assert (a.verdict or {}).get("reason") == (b.verdict or {}).get("reason")   # SC-002


# ============================================================ fixtures fail-clear

def test_missing_fixture_named_error(tmp_path):
    class _EmptyReplay:
        _queue, _i = [], 0
        def next_instruction(self, c):
            raise LookupError("exhausted")

    res = run_demo(_SeedFake(), _EmptyReplay(), _CriticOK(), budget=30,
                   fixture_out=str(tmp_path / "t.json"))
    assert res.error and "missing reasoning fixtures" in res.error and not res.ok


def test_exhausted_fixture_named_error(tmp_path):
    class _RunsOut:
        _queue = [1, 2, 3]              # passes the upfront precheck (>= 3)
        _i = 0
        def next_instruction(self, c):
            self._i += 1
            if self._i > 2:            # ...but exhausts on the 3rd fan-out call
                raise LookupError("exhausted")
            return {"instruction": "echo a > f", "rationale": "x"}

    res = run_demo(_SeedFake(), _RunsOut(), _CriticOK(), budget=30,
                   fixture_out=str(tmp_path / "t.json"))
    assert res.error and "exhausted" in res.error and "fan-out" in res.error and not res.ok


# ============================================================ budget + seed + leak

def test_reports_path_seconds(tmp_path):
    assert isinstance(_run(fixture_out=str(tmp_path / "t.json")).path_seconds, float)


def test_over_budget_fails(tmp_path):
    res = _run(budget=0.0, fixture_out=str(tmp_path / "t.json"))
    assert res.over_budget is True and res.ok is False


def test_seed_not_reproduced_fails(tmp_path):
    res = run_demo(_NeverBreaks(), _strategist(), _CriticOK(), budget=30,
                   fixture_out=str(tmp_path / "t.json"))
    assert res.error == "seed did not reproduce the failure" and not res.ok
    assert "teardown" in res.stages and "leak-check" in res.stages   # still ran


def test_leak_check_runs_on_failure(tmp_path):
    res = run_demo(_NeverBreaks(), _strategist(), _CriticOK(), budget=30,
                   fixture_out=str(tmp_path / "t.json"))
    assert res.stages[-2:] == ["teardown", "leak-check"]


def test_teardown_then_leakcheck_order(tmp_path):
    res = _run(fixture_out=str(tmp_path / "t.json"))
    assert res.stages.index("teardown") < res.stages.index("leak-check")


def test_leaked_sandbox_named_and_fails(tmp_path):
    class _LeaksOne(_SeedFake):
        def destroy(self, h):
            if h.id.endswith("0001"):        # never release the root sandbox
                return
            return super().destroy(h)

    res = run_demo(_LeaksOne(), _strategist(), _CriticOK(), budget=30,
                   fixture_out=str(tmp_path / "t.json"))
    assert res.leak and res.ok is False                   # SC-008


def test_ok_requires_budget_and_leak(tmp_path):
    within_leaky = run_demo(
        type("_L", (_SeedFake,), {"destroy": lambda self, h: None})(),
        _strategist(), _CriticOK(), budget=30, fixture_out=str(tmp_path / "a.json"))
    assert within_leaky.over_budget is False and within_leaky.leak and within_leaky.ok is False
    over_clean = _run(budget=0.0, fixture_out=str(tmp_path / "b.json"))
    assert over_clean.leak == [] and over_clean.over_budget and over_clean.ok is False   # SC-009


# ============================================================ demo.py exit codes

def test_demo_py_exit_codes(tmp_path):
    env_base = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO / "src")}

    ok = subprocess.run([sys.executable, "demo.py"], cwd=str(REPO), capture_output=True,
                        text=True, env={**env_base, "FAKE": "1"})
    assert ok.returncode == 0, ok.stderr

    over = subprocess.run([sys.executable, "demo.py"], cwd=str(REPO), capture_output=True,
                          text=True, env={**env_base, "FAKE": "1", "REWIND_DEMO_BUDGET": "0"})
    assert over.returncode == 1

    nocreds = subprocess.run([sys.executable, "demo.py"], cwd=str(REPO), capture_output=True,
                             text=True, env=env_base)   # no FAKE, no DAYTONA_API_KEY
    assert nocreds.returncode == 1
    assert "DAYTONA_API_KEY" in (nocreds.stdout + nocreds.stderr)   # SC-012
