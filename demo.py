"""demo.py — the single command for the demonstration path (spec 007).

    python demo.py            # DaytonaProvider + ReplayReasoner — the demonstration path
    FAKE=1 python demo.py     # FakeProvider + canned reasoners — offline dev, NOT the demo path

No arguments. Reads only credentials and optional overrides from the environment
(REWIND_DEMO_BUDGET, REWIND_REASONING_FIXTURES). The exit code is the run verdict:
0 only if the path completed within budget with no sandbox left live.
"""

import os
import re
import sys

from rewind.harness import DEFAULT_BUDGET, STRATEGIES, enough_fixtures, run_demo
from rewind.ports import ExecResult
from rewind.providers import DaytonaProvider, FakeProvider

FAKE = os.environ.get("FAKE") == "1"
BUDGET = float(os.environ.get("REWIND_DEMO_BUDGET", DEFAULT_BUDGET))
FIXTURES = os.environ.get("REWIND_REASONING_FIXTURES", "fixtures/reasoning")


class _SeedFake(FakeProvider):
    """Offline aid: models the seeded calculator regression the toy fake can't —
    once `return a-b` is written, the test step fails, so the fail→rewind story
    is real on the FAKE=1 path. Not used on the live demonstration path."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self._broken = False

    def run(self, h, cmd):
        if "calc.py" in cmd and ">" in cmd:              # a write to calc.py
            self._broken = "return a-b" in cmd
        if "test.py" in cmd and self._broken:            # the test on a broken calc.py
            self._record("run", "ok")
            return ExecResult(1, "AssertionError: add(2,2) != 4", 0.01)
        return super().run(h, cmd)


class _Canned:
    def __init__(self, *payloads):
        self._p, self._i = list(payloads), 0

    def next_instruction(self, context):
        r = self._p[self._i % len(self._p)]
        self._i += 1
        return r


def _canned_strategist():
    return _Canned(*[{"instruction": s, "rationale": "scripted candidate continuation"}
                     for s in STRATEGIES])


class _CannedCritic:
    """Reads the branch ids out of the evidence bundle and picks the first —
    a structurally valid verdict, so the offline path exercises the critic route."""
    def next_instruction(self, context):
        ids = re.findall(r"branch (\S+) \|", context)
        if not ids:
            return {"chosen": "?", "scores": {}, "reason": "no branches seen"}
        return {"chosen": ids[0],
                "scores": {i: (1.0 if i == ids[0] else 0.4) for i in ids},
                "reason": f"branch {ids[0]} exited 0 with usable output"}


def main() -> int:
    if FAKE:
        print("offline dev path — NOT the demonstration path (FAKE=1)")
        provider, strat, crit = _SeedFake(), _canned_strategist(), _CannedCritic()
    else:
        if not os.environ.get("DAYTONA_API_KEY"):
            print("DAYTONA_API_KEY not set — the demo path runs live", file=sys.stderr)
            return 1
        try:
            provider = DaytonaProvider()
        except KeyError as e:                             # a missing credential
            print(f"missing credential: {e}", file=sys.stderr)
            return 1
        from rewind.reasoning import ReplayReasoner
        strat = ReplayReasoner(FIXTURES)
        crit = ReplayReasoner(os.path.join(FIXTURES, "critic"))
        if not enough_fixtures(strat, 3) or not enough_fixtures(crit, 1):
            print(f"missing reasoning fixtures: {FIXTURES} — "
                  f"run tools/capture_demo_fixtures.py", file=sys.stderr)
            return 1

    res = run_demo(provider, strat, crit, budget=BUDGET)

    for s in res.stages:
        print(f"  · {s}")
    print(f"\n  path {res.path_seconds:.1f}s / budget {BUDGET:.0f}s"
          f"{'   OVER BUDGET' if res.over_budget else ''}")
    if res.verdict:
        print(f"  verdict: {res.verdict.get('reason')}"
              f"{'   (deterministic fallback)' if res.verdict.get('fallback_used') else ''}")
    if res.leak:
        print(f"  LEAK — sandboxes still live: {res.leak}")
    if res.error:
        print(f"  error: {res.error}")
    print(f"  {'PASS' if res.ok else 'FAIL'}")

    # spec 009 — optionally mirror the console fixture to the deployed console.
    # Best-effort and env-gated: absence or failure never affects this run.
    if (getattr(res, "fixture_written", False)
            and os.environ.get("REWIND_CONSOLE_ENDPOINT")
            and os.environ.get("REWIND_CONSOLE_TOKEN")):
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from tools.push_console import push
            push("fixtures/tree.json")
        except Exception as exc:                          # noqa: BLE001 — never break the demo
            print(f"  console push skipped: {exc}")

    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
