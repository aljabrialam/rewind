# Quickstart: Demo Harness

---

## Run the demonstration path

```bash
python demo.py                 # DaytonaProvider + ReplayReasoner — the demonstration path
```

Needs `DAYTONA_API_KEY` and `fixtures/reasoning/` (one-time capture below). Exits
`0` only if the path completed, stayed within `REWIND_DEMO_BUDGET` (default ~90s),
and left no sandbox live.

## Offline dev path

```bash
FAKE=1 python demo.py          # FakeProvider + canned reasoners — NOT the demo path, exits fast
```

## Capture the reasoning fixtures (one time, needs LLM + Daytona creds)

```bash
python tools/capture_demo_fixtures.py    # RecordingReasoner over a live run -> fixtures/reasoning/
```

## Tests

```bash
pytest tests/unit/test_harness.py -q                 # pure-logic + a full offline run_demo (SC-011)
pytest tests/e2e/test_demo_path.py -m live -q        # the live E2E (needs creds + fixtures)
```

Rehearsal (pre-freeze, manual): [checklists/rehearsal.md](checklists/rehearsal.md).

---

## FR / NFR / SC → verification

`h` = `tests/unit/test_harness.py`; `e2e` = `tests/e2e/test_demo_path.py`;
`reh` = a [rehearsal.md](checklists/rehearsal.md) item.

| Requirement | Verified by |
|---|---|
| FR-007-01 single no-arg command runs the whole path | `h::test_run_demo_completes_offline` + `reh` (no prompt) — SC-001 |
| FR-007-02 live sandbox, no simulation on the path | `e2e::test_path_uses_live_provider` + `reh` — SC-003 |
| FR-007-03 reasoning replayed from fixtures; fail-clear if missing | `h::test_missing_fixture_named_error`, `h::test_exhausted_fixture_named_error` + `e2e` — SC-004/005 |
| FR-007-04 seed a reproducible failure; fail if it doesn't reproduce | `h::test_seed_reproduced_true`, `h::test_seed_not_reproduced_fails` — SC edge |
| FR-007-05 report path time; fail over budget | `h::test_reports_path_seconds`, `h::test_over_budget_fails` — SC-006 |
| FR-007-06 pre-warm outside the timed path | `h::test_prepare_runs_before_timer`, `h::test_path_seconds_excludes_prepare` — SC-007 |
| FR-007-07 end-of-path leak check on every route | `h::test_leak_check_clean_on_success`, `h::test_leak_check_runs_on_failure`, `h::test_leaked_sandbox_named_and_fails` — SC-008 |
| FR-007-08 teardown before the leak check, both routes | `h::test_teardown_then_leakcheck_order` | 
| FR-007-09 both budget + leak must pass for exit 0 | `h::test_ok_requires_budget_and_leak` — SC-009 |
| FR-007-10 write the console fixture | `h::test_console_fixture_written` — SC-010 |
| NFR-007-01 non-zero exit on any failure | `h::test_demo_py_exit_codes` (subprocess over the FAKE path + forced failures) — SC-009/012 |
| NFR-007-02 no interactive input | `h::test_run_demo_completes_offline` (no stdin) + `reh` |
| NFR-007-03 budget is one declared, overridable value | `h::test_budget_env_override` |
| NFR-007-04 harness logic testable offline | the whole of `test_harness.py` — SC-011 |

| Success criterion | Verified by |
|---|---|
| SC-001 | `h::test_run_demo_completes_offline` |
| SC-002 | `h::test_two_runs_identical` (stages + branch_instructions + verdict match) |
| SC-003 | `e2e::test_path_uses_live_provider` |
| SC-004 | `e2e` (no live reasoning call recorded) |
| SC-005 | `h::test_missing_fixture_named_error`, `h::test_exhausted_fixture_named_error` |
| SC-006 | `h::test_over_budget_fails` |
| SC-007 | `h::test_path_seconds_excludes_prepare` |
| SC-008 | `h::test_leaked_sandbox_named_and_fails` |
| SC-009 | `h::test_ok_requires_budget_and_leak` |
| SC-010 | `h::test_console_fixture_written` |
| SC-011 | `test_harness.py` runs with no runtime / network / creds |
| SC-012 | `h::test_demo_py_exit_codes` (no-creds path) |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_harness.py -q` green offline.
- **G3**: `python demo.py` runs clean **twice** live + the failure spot check ([rehearsal.md](checklists/rehearsal.md)); recorded in `docs/gates.md`.
