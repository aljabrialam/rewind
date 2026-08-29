"""tools/capture_demo_fixtures.py — one-time: record the reasoning fixtures the
demonstration path replays (spec 007 FR-007-03 / spec 002 / spec 005).

    export DAYTONA_API_KEY=...   LLM_API_KEY=...
    python tools/capture_demo_fixtures.py

Runs the demo path once against the LIVE sandbox runtime and a LIVE reasoner,
wrapping each reasoning role in a RecordingReasoner so its responses land in
    fixtures/reasoning/          (strategist)
    fixtures/reasoning/critic/   (critic)
After this, `python demo.py` replays them deterministically.
"""

import os
import sys

STRAT_DIR = "fixtures/reasoning"
CRITIC_DIR = "fixtures/reasoning/critic"


def main() -> int:
    for var in ("DAYTONA_API_KEY", "LLM_API_KEY"):
        if not os.environ.get(var):
            print(f"{var} not set — capture needs the live runtime and a live reasoner",
                  file=sys.stderr)
            return 1

    from rewind.harness import run_demo
    from rewind.providers import DaytonaProvider
    from rewind.reasoning import LiveReasoner, RecordingReasoner, critic_reasoner

    strat = RecordingReasoner(LiveReasoner(), STRAT_DIR)
    # spec 008 — critic_reasoner() routes to CRITIC_BASE_URL when set, else the
    # plain primary; the captured verdict then carries `served_by`.
    critic = RecordingReasoner(critic_reasoner(), CRITIC_DIR)

    res = run_demo(DaytonaProvider(), strat, critic, budget=999.0)

    print("\n".join(f"  · {s}" for s in res.stages))
    if not res.ok:
        print(f"\ncapture run did not complete cleanly: {res.error or res.leak}", file=sys.stderr)
        return 1
    print(f"\ncaptured strategist -> {STRAT_DIR}/ , critic -> {CRITIC_DIR}/")
    print("`python demo.py` will now replay these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
