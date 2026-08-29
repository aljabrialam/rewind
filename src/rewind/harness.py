"""src/rewind/harness.py — spec 007. The scripted end-to-end demonstration path,
run unattended, budgeted, and leak-checked.

`run_demo` composes specs 000–006 through the engine / provider / reasoner APIs
and adds nothing. It is pure of the environment: no env reads, no prints, no
`sys.exit` — it returns a `DemoResult`. `demo.py` owns the environment and maps
`DemoResult.ok` to an exit code.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .engine import Engine, RestoreCheck, console_fixture

STAGES = ("prepare", "seed", "observe-failure", "rewind", "fan-out",
          "verdict", "promote", "console-fixture", "teardown", "leak-check")

_PATH_STAGES = ("seed", "observe-failure", "rewind", "fan-out",
                "verdict", "promote", "console-fixture")

# the seeded calculator regression — a passing test, then an edit that breaks it
SEED_STEPS = [
    "echo 'def add(a,b): return a+b' > calc.py",
    "echo 'assert add(2,2)==4' > test.py",
    "python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
    "echo 'def add(a,b): return a-b' > calc.py",                      # the mistake
    "python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
]

STRATEGIES = [
    "echo 'def add(a,b): return a+b' > calc.py && python3 -c "
    "\"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
    "echo 'def add(a,b): return sum([a,b])' > calc.py && python3 -c "
    "\"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
    "echo 'def add(a,b): return a*b' > calc.py && python3 -c "
    "\"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
]

DEFAULT_BUDGET = 90.0


@dataclass
class DemoResult:
    ok: bool = False
    stages: list = field(default_factory=list)
    prepare_seconds: float = 0.0
    path_seconds: float = 0.0
    budget: float = 0.0
    over_budget: bool = False
    seed_reproduced: bool = False
    leak: list = field(default_factory=list)
    verdict: dict | None = None
    branch_instructions: list = field(default_factory=list)
    error: str | None = None
    fixture_written: bool = False

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "stages": list(self.stages),
            "prepare_seconds": round(self.prepare_seconds, 3),
            "path_seconds": round(self.path_seconds, 3),
            "budget": self.budget, "over_budget": self.over_budget,
            "seed_reproduced": self.seed_reproduced, "leak": list(self.leak),
            "verdict": self.verdict, "branch_instructions": list(self.branch_instructions),
            "error": self.error, "fixture_written": self.fixture_written,
        }


# --- pure checks (NFR-007-04) -------------------------------------------------

def check_budget(path_seconds: float, budget: float) -> bool:
    return path_seconds <= budget


def check_no_leak(provider) -> list:
    """Ids of sandboxes the provider still holds live (FakeProvider.live /
    DaytonaProvider._live), plus any unconfirmed-destroy leak (spec 000)."""
    live = getattr(provider, "live", None)
    if live is None:
        live = getattr(provider, "_live", None) or set()
    ids = [i for i in live]
    ids += [getattr(lk, "sandbox_id", None) for lk in getattr(provider, "leaks", [])]
    return [i for i in ids if i]


def check_seed_reproduced(step_checkpoints) -> bool:
    """True iff the last executed step failed as the seed intends."""
    steps = [c for c in step_checkpoints
             if getattr(c, "parent_id", None) is not None and getattr(c, "evidence", None) is not None]
    return bool(steps) and steps[-1].evidence.exit_code != 0


def enough_fixtures(reasoner, need: int) -> bool:
    """A ReplayReasoner has >= `need` responses left. Non-replay reasoners pass."""
    q = getattr(reasoner, "_queue", None)
    if q is None:
        return True
    return (len(q) - getattr(reasoner, "_i", 0)) >= need


# --- the harness -----------------------------------------------------------

class _Abort(Exception):
    pass


def _prepare_runtime(provider) -> None:
    h = provider.spawn()
    try:
        provider.run(h, "echo warm")
    finally:
        provider.destroy(h)


def _finish(res: DemoResult, provider, engine) -> None:
    if "teardown" not in res.stages:
        res.stages.append("teardown")
        try:
            engine.shutdown()
        except Exception:                                    # noqa: BLE001 — best effort
            pass
    if "leak-check" not in res.stages:
        res.stages.append("leak-check")
        res.leak = check_no_leak(provider)


def run_demo(provider, strategist, critic, *, budget: float = DEFAULT_BUDGET,
             warm: bool = True, fixture_out: str = "fixtures/tree.json",
             seed_steps: list | None = None) -> DemoResult:
    res = DemoResult(budget=budget)
    seed_steps = seed_steps or SEED_STEPS
    e = Engine(provider)

    # FR-007-03 — fail clear before the path if the fixtures are too few
    if not enough_fixtures(strategist, 3):
        res.error = "missing reasoning fixtures: strategist (need 3)"
        return res
    if not enough_fixtures(critic, 1):
        res.error = "missing reasoning fixtures: critic (need 1)"
        return res

    if warm:                                                 # FR-007-06 — outside the timer
        res.stages.append("prepare")
        p0 = time.time()
        try:
            _prepare_runtime(provider)
        except Exception as ex:                              # noqa: BLE001
            res.error = f"preparation failed: {ex}"
            res.prepare_seconds = time.time() - p0
            _finish(res, provider, e)
            return res
        res.prepare_seconds = time.time() - p0

    path_t0 = time.time()
    good = None
    try:
        res.stages.append("seed")
        e.start()
        for s in seed_steps:
            cp = e.step(s)
            if cp.evidence.ok and cp.snapshot and good is None:
                good = cp.step_id
            if not cp.evidence.ok:
                break

        res.stages.append("observe-failure")
        res.seed_reproduced = check_seed_reproduced(
            [e.run.checkpoints[i] for i in e.run.order])
        if not res.seed_reproduced:
            res.error = "seed did not reproduce the failure"
            raise _Abort()
        if good is None:
            res.error = "no good checkpoint to rewind to"
            raise _Abort()

        res.stages.append("rewind")
        rr = e.restore(good, RestoreCheck(before=[("cat calc.py", "def add")],
                                          after=[("cat calc.py", "a - b")]))
        if rr.error:
            res.error = f"restore failed: {rr.error}"
            raise _Abort()

        res.stages.append("fan-out")
        try:
            fo = e.fan_out(good, strategist, 3)
        except LookupError:
            res.error = "reasoning fixture exhausted at fan-out"
            raise _Abort()
        if fo.error:
            res.error = f"fan-out failed: {fo.error}"
            raise _Abort()
        res.branch_instructions = [c.instruction for c in fo.children]

        res.stages.append("verdict")
        try:
            jp = e.judge_and_promote(fo.children, critic)
        except LookupError:
            res.error = "reasoning fixture exhausted at verdict"
            raise _Abort()
        if jp.get("error"):
            res.error = f"promote failed: {jp['error']}"
            raise _Abort()
        res.stages.append("promote")
        res.verdict = jp.get("verdict")

        res.stages.append("console-fixture")
        out = Path(fixture_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(console_fixture(e), indent=2))
        res.fixture_written = True

        res.path_seconds = time.time() - path_t0
    except _Abort:
        res.path_seconds = time.time() - path_t0
    except Exception as ex:                                  # noqa: BLE001
        res.error = res.error or f"path error: {getattr(ex, 'error_class', None) or ex}"
        res.path_seconds = time.time() - path_t0
    finally:
        _finish(res, provider, e)                            # FR-007-08 — teardown then leak-check

    res.over_budget = not check_budget(res.path_seconds, budget)   # FR-007-05
    reached_all = all(s in res.stages for s in _PATH_STAGES)
    res.ok = (reached_all and res.error is None
              and not res.over_budget and not res.leak)          # FR-007-09
    return res
