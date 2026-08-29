# Contract: Demo Harness

`src/rewind/harness.py` — `run_demo(...)`, the check functions, and `demo.py`'s
exit-code mapping.

Traces: FR-007-01 … FR-007-10, NFR-007-01 … NFR-007-04.

---

## `run_demo(provider, strategist, critic, *, budget, warm=True, fixture_out=…) -> DemoResult`

| # | Obligation | Trace |
|---|---|---|
| C1 | No environment reads, no prints, no `sys.exit` — returns a `DemoResult`. `demo.py` owns the env and the exit code. | FR-007-01, NFR-007-04 |
| C2 | If `warm`: run `_prepare_runtime(provider)` (spawn + trivial run + destroy) **before** `path_t0`. `prepare_seconds` is recorded and is **not** part of `path_seconds` or the budget. A preparation failure → `error`, the timed path never starts. | FR-007-06, SC-007 |
| C3 | Execute the scripted path via the `engine` API only: `start` → seed steps → `fan_out(good, strategist, 3)` → `judge_and_promote(branches, critic)` → `restore(good, …)` → `console_fixture` write. Sandbox ops go through `provider` (the caller decides live vs fake). | FR-007-02 |
| C4 | Every strategist and critic response comes from the passed reasoner. `run_demo` makes **no** direct reasoning call and no live-reasoning fallback. `LookupError` from an exhausted `ReplayReasoner` → `error = "reasoning fixture exhausted at <stage>"`. | FR-007-03, SC-004/005 |
| C5 | After the seed steps, `check_seed_reproduced(checkpoints)` must be `True`; else `error = "seed did not reproduce the failure"` and the path aborts (still to teardown). | FR-007-04, SC edge |
| C6 | `path_seconds` = wall-clock from `path_t0` to the end of `console-fixture`. `over_budget = path_seconds > budget`. | FR-007-05 |
| C7 | `teardown` (`Engine.shutdown()` + destroy the warm handle if still held) runs in a `finally`, on the success and every failure route, **before** `leak-check`. | FR-007-08 |
| C8 | `leak-check` = `check_no_leak(provider)`; a non-empty list sets `DemoResult.leak` and forces `ok = False`. | FR-007-07, SC-008 |
| C9 | `fixtures/tree.json` (or `fixture_out`) is written with `console_fixture(engine)` reflecting the completed path, overwriting any prior file; `fixture_written = True`. Skipped only if the path aborted before `promote`. | FR-007-10, SC-010 |
| C10 | `stages` lists each stage entered, in the fixed `STAGES` order; `teardown` + `leak-check` always appear last. | SC-002 |
| C11 | `ok` is `True` **iff**: every path stage was reached ∧ `error is None` ∧ `not over_budget` ∧ `leak == []`. | FR-007-09, SC-009 |

---

## Check functions (pure — NFR-007-04, SC-011)

| Function | Pass |
|---|---|
| `check_budget(path_seconds, budget)` | `path_seconds <= budget` |
| `check_no_leak(provider)` | returns `[]` — no id in `provider.live` / `provider._live` / leak records |
| `check_seed_reproduced(checkpoints)` | last executed step's `evidence.exit_code != 0` |
| `enough_fixtures(reasoner, need)` | the `ReplayReasoner` has ≥ `need` queued responses |

No I/O, no runtime, no credentials. Tested directly.

---

## `demo.py` — the single command (FR-007-01, NFR-007-01/02, SC-012)

| Condition | Behaviour |
|---|---|
| no arguments, non-interactive | builds provider + reasoners from the env, calls `run_demo`, prints the stages + `path_seconds` + budget verdict + leak verdict |
| `FAKE=1` | `FakeProvider` + canned reasoners — the **offline dev path**, printed as "not the demonstration path" |
| default (no `FAKE`) | `DaytonaProvider` + `ReplayReasoner(fixtures/reasoning/…)` for both roles — the demonstration path |
| `DAYTONA_API_KEY` absent | exit `1` immediately with `"DAYTONA_API_KEY not set — the demo path runs live"`; nothing created (SC-012) |
| reasoning fixtures absent / too few | exit `1` with `"missing reasoning fixtures: <path> — run tools/capture_demo_fixtures.py"` (SC-005) |
| `REWIND_DEMO_BUDGET` set | overrides the default ~90s budget (NFR-007-03) |
| `run_demo` returns `ok=True` | `raise SystemExit(0)` |
| `run_demo` returns `ok=False` | print `error` / `leak` / over-budget detail, `raise SystemExit(1)` |

Exit code is the run verdict. No prompt, no TTY requirement.

---

## Exit-code table

| Outcome | `DemoResult` | Exit |
|---|---|---|
| path complete, within budget, no leak | `ok=True` | `0` |
| no credentials | (constructed before `run_demo`) | `1` |
| reasoning fixtures missing / exhausted | `error` set | `1` |
| seed did not reproduce the failure | `error` set | `1` |
| a live runtime op failed mid-path | `error` set (classified) | `1` |
| path time > budget | `over_budget=True` | `1` |
| a sandbox left live after teardown | `leak != []` | `1` |
