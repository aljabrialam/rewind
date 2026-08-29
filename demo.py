"""demo.py — the vertical slice. FAKE=1 python demo.py  |  python demo.py

Runs steps, fails, branches from an earlier checkpoint, picks a winner.
This is the 14:00 checkpoint: if this prints a winner, the product exists.
"""

import json
import os
import time

from rewind.engine import Engine, rank_by_evidence
from rewind.providers import DaytonaProvider, FakeProvider

FAKE = os.environ.get("FAKE") == "1"

# a deterministic little task: build up a file, then a step that fails
STEPS = [
    "echo 'def add(a,b): return a+b' > calc.py",
    "echo 'assert add(2,2)==4' > test.py",
    "python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
    "echo 'def add(a,b): return a-b' > calc.py",          # the mistake
    "python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
]

STRATEGIES = [
    "echo 'def add(a,b): return a+b' > calc.py && python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
    "echo 'def add(a,b): return sum([a,b])' > calc.py && python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
    "echo 'def add(a,b): return a*b' > calc.py && python3 -c \"exec(open('calc.py').read()); exec(open('test.py').read()); print('PASS')\"",
]


def main() -> int:
    p = FakeProvider() if FAKE else DaytonaProvider()
    e = Engine(p, max_branches=int(os.environ.get("MAX_BRANCHES", 3)))
    t0 = time.time()
    try:
        print("── run ──")
        e.start()
        good_step = None
        for s in STEPS:
            cp = e.step(s)
            mark = "ok " if cp.evidence.ok else "FAIL"
            print(f"  [{cp.index}] {mark} {s[:58]}")
            if cp.evidence.ok and cp.snapshot:
                good_step = good_step or cp.step_id      # remember an early good one
            if not cp.evidence.ok:
                print(f"       stderr/stdout: {cp.evidence.stdout[:120]}")
                break

        print(f"\n── rewind to checkpoint {good_step} and branch ──")
        branches = e.branch_from(good_step, STRATEGIES)
        for i, b in enumerate(branches):
            print(f"  branch {i}  sandbox={b.sandbox_id}  exit={b.evidence.exit_code}  "
                  f"{b.evidence.stdout.strip()[:40]}")

        verdict = rank_by_evidence(branches)
        print(f"\n── verdict ({verdict['provider']}) ──\n  {verdict['reason']}")

        win = branches[verdict["winner"]]
        e.promote(win.step_id, [b.step_id for i, b in enumerate(branches)
                                if i != verdict["winner"]])
        print(f"  promoted {win.step_id} → head")

        with open("fixtures/tree.json", "w") as f:        # feeds the console
            json.dump(e.run.as_tree(), f, indent=2)
        print(f"\n  wrote fixtures/tree.json   total {time.time()-t0:.1f}s")
        return 0
    finally:
        e.shutdown()
        print("  all sandboxes destroyed")


if __name__ == "__main__":
    raise SystemExit(main())
