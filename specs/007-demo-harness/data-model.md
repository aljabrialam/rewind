# Phase 1 Data Model: Demo Harness

New members in `src/rewind/harness.py`. Everything else is composed from
specs 000–006 unchanged.

---

## 1. `run_demo` signature

```
run_demo(provider, strategist, critic, *,
         budget: float,
         warm: bool = True,
         fixture_out: str = "fixtures/tree.json") -> DemoResult
```

| Arg | Type | Notes |
|---|---|---|
| `provider` | a `SandboxProvider` | live `DaytonaProvider` on the demo path; `FakeProvider` offline |
| `strategist` | a `ReasoningPort` | `ReplayReasoner` on the demo path; canned offline |
| `critic` | a `ReasoningPort` | `ReplayReasoner` on the demo path; canned offline |
| `budget` | float (seconds) | the declared demonstration budget |
| `warm` | bool | run the preparation stage (FR-007-06); `False` only in a test that checks the flag |
| `fixture_out` | str | where the console fixture is written (FR-007-10) |

Pure of the environment — reads no env vars, prints nothing, does not call
`sys.exit`. `demo.py` supplies the arguments and maps the result to an exit code.

---

## 2. `DemoResult`

| Field | Type | Meaning |
|---|---|---|
| `ok` | bool | `True` iff completed ∧ `error is None` ∧ budget passed ∧ no leak (FR-007-09) |
| `stages` | list[str] | the stages entered, in order (see `STAGES`) |
| `prepare_seconds` | float | preparation wall-clock — **not** counted against the budget |
| `path_seconds` | float | the demonstration path wall-clock (from after prepare to end of the scripted path) |
| `budget` | float | echoed back |
| `over_budget` | bool | `path_seconds > budget` |
| `seed_reproduced` | bool | the seeded failure step exited non-zero as designed |
| `leak` | list[str] | sandbox ids still live after teardown (`[]` = clean) |
| `verdict` | dict \| None | the promoted round's verdict record (for SC-002 comparison) |
| `branch_instructions` | list[str] | the fan-out strategy instructions, in order (for SC-002) |
| `error` | str \| None | the named failure cause, if any |
| `fixture_written` | bool | `fixtures/tree.json` was written (FR-007-10) |

`as_dict()` for logging / the rehearsal record.

---

## 3. `STAGES`  (fixed order — SC-002, US1 §2)

```
("prepare", "seed", "observe-failure", "rewind", "fan-out",
 "verdict", "promote", "console-fixture", "teardown", "leak-check")
```

`prepare` is present iff `warm=True`. `teardown` and `leak-check` are appended on
**every** route, including a failure partway (FR-007-08).

---

## 4. Pure check functions (NFR-007-04)

| Function | Signature | Rule |
|---|---|---|
| `check_budget` | `(path_seconds, budget) -> bool` | `path_seconds <= budget` |
| `check_no_leak` | `(provider) -> list[str]` | ids the provider still holds live: `provider.live` (fake) / `provider._live` + leak-record ids (`DaytonaProvider`); `[]` = clean |
| `check_seed_reproduced` | `(checkpoints) -> bool` | last executed step checkpoint has `evidence.exit_code != 0` |
| `enough_fixtures` | `(reasoner, need: int) -> bool` | the `ReplayReasoner` has ≥ `need` queued entries (fail-clear precheck, FR-007-03) |

All pure: no I/O, no runtime, no credentials.

---

## 5. Harness state machine

| Stage | Enters when | Fails the run when |
|---|---|---|
| `prepare` | `warm` and before the timer | preparation `spawn`/`run`/`destroy` raises → `error`, **timed path never starts** (FR-007-06) |
| `seed` | timer started | a seed step raises at the runtime → `error` |
| `observe-failure` | seed steps done | `check_seed_reproduced` is `False` → `error = "seed did not reproduce the failure"` |
| `rewind` | failure observed | `restore` returns an `error` |
| `fan-out` | rewound | `fan_out` returns an `error`, or a reasoning fixture is exhausted → `error` names the stage |
| `verdict` | branches done | `evaluate`/critic fixture exhausted → `error` |
| `promote` | verdict in hand | `judge_and_promote` returns an `error` (headless / no eligible branch) |
| `console-fixture` | promoted | write to `fixture_out` fails → `error` |
| `teardown` | always (finally) | — teardown itself best-effort; failures noted |
| `leak-check` | always, after teardown | `check_no_leak` non-empty → `leak` set, `ok = False` (FR-007-07) |

**Invariant**: `teardown` then `leak-check` run on every exit route (FR-007-08).
`ok` is the AND of: all path stages reached, `error is None`, `not over_budget`,
`leak == []` (FR-007-09).

---

## Type glossary

| Name | Definition |
|---|---|
| `DemoResult` | dataclass — the full outcome of one `run_demo`; `as_dict()` |
| `STAGES` | the fixed tuple of stage names |
| demonstration path | the stages from `seed` to `console-fixture` — what `path_seconds` measures |
| demo-path reasoners | `ReplayReasoner` for both strategist and critic; canned only offline |
