# Phase 0 Research: Demo Harness

Spec 007 carries no `[NEEDS CLARIFICATION]`. Decisions for design. Evidence:
`demo.py` (the current path), `src/rewind/engine.py` (`Engine`, `fan_out`,
`judge_and_promote`, `restore`, `console_fixture`, `shutdown`),
`src/rewind/providers.py` (`FakeProvider.live`, `DaytonaProvider._live`,
`DaytonaProvider.leaks`), `src/rewind/reasoning.py` (`ReplayReasoner`,
`RecordingReasoner`), Constitution Articles I, XI, XII, VI.

---

## R1. The `run_demo` seam (NFR-007-04)

**Decision**: `run_demo(provider, strategist, critic, *, budget: float,
warm: bool = True, fixture_out: str = "fixtures/tree.json") -> DemoResult`. It
takes the provider and both reasoners as arguments, so:
- the **offline pure-logic** layer calls it with `FakeProvider()` + canned
  reasoners and asserts stages / budget / leak / seed behaviour with no runtime;
- the **live E2E** calls it with `DaytonaProvider()` + `ReplayReasoner(...)`;
- `demo.py` is a thin front end that builds the right pair and calls it.

`run_demo` never reads the environment or prints an exit code — it returns a
`DemoResult`. `demo.py` maps `DemoResult.ok` to `SystemExit(0|1)`.

**Rationale**: Article VI — the harness's *logic* is testable without the live
runtime; the live run is a separate `@pytest.mark.live` test. Article V —
`demo.py` stays the command.

---

## R2. Pre-warm outside the path timer (FR-007-06, SC-007)

**Decision**: `_prepare_runtime(provider)` — `h = provider.spawn(); provider.run(
h, "echo warm"); provider.destroy(h)` — runs **before** `path_t0 = time.time()`.
The `DemoResult.path_seconds` is measured from `path_t0` to the end of the
scripted path; preparation time is reported separately as `prepare_seconds` and
is **not** in `path_seconds`. `warm=False` skips it (used by an offline test that
asserts the flag is honoured).

**Rationale**: FR-007-06 — cold-start `create` cost must not be inside the
reported/budgeted path time.

---

## R3. Missing / exhausted reasoning fixture (FR-007-03, SC-005)

**Decision**: `demo.py` builds the strategist and critic as `ReplayReasoner`
instances over `fixtures/reasoning/` (a `strategist` subset and a `critic`
subset, or two directories). Before the path, it checks each `ReplayReasoner` has
at least the number of entries the path consumes; if not, it returns a
`DemoResult` with `error = "missing reasoning fixtures: <path> (need N, have M)"`
and `demo.py` exits non-zero. During the path, `ReplayReasoner` already raises
`LookupError` on exhaustion (Spec 002); `run_demo` catches it and sets
`error = "reasoning fixture exhausted at <stage>"`. No live-reasoning fallback
anywhere on the path.

`FAKE=1` (offline dev) and an explicit `REWIND_DEMO_ALLOW_CANNED=1` use the
canned reasoners instead — that is **not** the demonstration path and `demo.py`
prints that it is not.

**Rationale**: SC-005 — a fixture problem is a named non-zero exit, never a
silent live call. Keeps `demo.py` runnable today (offline) while the live path
awaits a one-time capture.

---

## R4. The leak check (FR-007-07/08, SC-008)

**Decision**: `check_no_leak(provider) -> list[str]` returns the ids of any
sandbox the provider still holds live: for `FakeProvider` that is `provider.live`;
for `DaytonaProvider` it is `provider._live` plus any `provider.leaks`
(unconfirmed-destroy leaks, Spec 000). Empty list = clean. `run_demo` calls
`provider`'s teardown (`Engine.shutdown()` and, for the warm sandbox, its own
destroy) in a `finally`, **then** `check_no_leak`. A non-empty list sets
`DemoResult.leak = [...]` and `ok = False`.

**Rationale**: FR-007-07/08 — teardown then check, on both routes; a leak fails
the run and is named.

---

## R5. The seed-reproduced check (FR-007-04, edge case)

**Decision**: `check_seed_reproduced(checkpoints) -> bool` — `True` iff the last
executed step checkpoint has `evidence.exit_code != 0` (the scripted "optimise
into subtraction" step failed as designed). `run_demo` runs the seed steps, then
this check; `False` → `error = "seed did not reproduce the failure"`, path
aborted, teardown + leak check still run.

**Rationale**: FR-007-04 — the demonstration rewinds *from a failure*; a seed
that does not fail is broken.

---

## R6. Exit-code contract (FR-007-09, NFR-007-01)

**Decision**: `DemoResult.ok` is `True` **only** when: the path completed all
stages, `error is None`, `check_budget(path_seconds, budget)` passed, and
`check_no_leak(provider)` returned `[]`. `demo.py`: `raise SystemExit(0 if
result.ok else 1)`. Every failure route (no creds, missing fixture, seed didn't
fail, runtime error, budget overrun, leak) yields `ok = False` → exit 1, with
`DemoResult.error` / `.leak` / `.over_budget` naming the cause.

`DaytonaProvider()` with no `DAYTONA_API_KEY` already raises `KeyError` at
construction; `demo.py` wraps that into a named message + exit 1 (FR-007-02 §3 /
SC-012).

---

## R7. Stage order (SC-002, US1 §2)

**Decision**: `STAGES = ("prepare", "seed", "observe-failure", "rewind",
"fan-out", "verdict", "promote", "console-fixture", "teardown", "leak-check")`.
`run_demo` appends each stage name to `DemoResult.stages` as it enters it. A test
asserts the completed offline run's `stages` equals `STAGES` (prepare present,
order fixed). Two runs producing the same `stages` + same branch instructions +
same verdict `chosen`/`reason` is SC-002.

---

## R8. `demo.py` keeps running today

**Decision**: `FAKE=1 python demo.py` → `FakeProvider` + canned reasoners →
`run_demo` → full path offline, exit 0. `python demo.py` → `DaytonaProvider` +
`ReplayReasoner`; if the reasoning fixtures are absent → named exit 1 (correct
per SC-005) with a one-line pointer to `tools/capture_demo_fixtures.py`.

---

## Open items carried to Phase 1

- `DemoResult` / `Stage` fields + state machine → [data-model.md](data-model.md)
- `run_demo` contract + check rules + exit table → [contracts/harness.md](contracts/harness.md)
- The two-run rehearsal pass → [checklists/rehearsal.md](checklists/rehearsal.md)
- FR→test map → [quickstart.md](quickstart.md)
