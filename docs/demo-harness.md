# Demo Harness (spec 007)

The top of the testing pyramid — the scripted end-to-end demonstration path, run
unattended, budgeted, and leak-checked. Composes specs 000–006; adds nothing.
Full spec: [`specs/007-demo-harness/`](../specs/007-demo-harness/).

## The command

```bash
python demo.py            # DaytonaProvider + ReplayReasoner — the demonstration path
FAKE=1 python demo.py     # a _SeedFake + canned reasoners — offline dev, NOT the demo path
```

No arguments. Reads only `DAYTONA_API_KEY` and optional overrides
(`REWIND_DEMO_BUDGET` default 90s, `REWIND_REASONING_FIXTURES`) from the
environment. **Exit code is the run verdict** — `0` only if the path completed
within budget with no sandbox left live (FR-007-09).

## The path (`src/rewind/harness.py` → `run_demo`)

`prepare` (pre-warm, outside the timer) → **timed:** `seed` → `observe-failure`
→ `rewind` → `fan-out` → `verdict` → `promote` → `console-fixture` → **always:**
`teardown` → `leak-check`.

`run_demo(provider, strategist, critic, *, budget, warm=True, fixture_out=…)` is
pure of the environment — no env reads, no prints, no `sys.exit`. It returns a
`DemoResult` `{ok, stages, prepare_seconds, path_seconds, over_budget,
seed_reproduced, leak, verdict, branch_instructions, error, fixture_written}`.
`demo.py` supplies the provider + reasoners and maps `ok` to the exit code — so
the harness *logic* (budget / leak / seed / stage order) is unit-tested with no
runtime (`tests/unit/test_harness.py`, 20 tests).

## Guarantees

- **Live sandbox, replayed reasoning** — the demo path uses `DaytonaProvider` and
  `ReplayReasoner` for both the strategist and the critic; no simulation, no live
  reasoning call (FR-007-02/03). A missing/exhausted fixture → named non-zero exit.
- **Seeded reproducible failure** — the calculator regression; if the "mistake"
  step does not fail, the run fails with a named error (FR-007-04).
- **Pre-warm outside the timed path** — `path_seconds` excludes it (FR-007-06).
- **Budget** — one declared value; over it → non-zero, naming budget + actual (FR-007-05).
- **Leak check on every route** — teardown then `check_no_leak`; a sandbox left
  live → named, run fails (FR-007-07/08).

## One-time fixture capture

```bash
export DAYTONA_API_KEY=...  LLM_API_KEY=...
python tools/capture_demo_fixtures.py    # -> fixtures/reasoning/ and fixtures/reasoning/critic/
```

## Rehearse before the freeze

Run `python demo.py` **twice** back to back + the failure spot check —
[`specs/007-demo-harness/checklists/rehearsal.md`](../specs/007-demo-harness/checklists/rehearsal.md).
Two clean runs are the G3 demo-path evidence (Article XI).
