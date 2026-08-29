# Quickstart: Sandbox Capability Contract

How to run and validate this feature. Implementation detail belongs in
`tasks.md`; this is the run/validation guide and the FR → named-test matrix
required by Constitution Article VI.

---

## Prerequisites

| Need | For |
|---|---|
| Python 3.11+, `pip install -e .` (pulls `daytona`, `pytest`) | everything |
| `.rewind/capability-map.toml` present | import of `rewind.ports` to succeed at all |
| `DAYTONA_API_KEY` in `.env` | the live contract test and the fixture-capture run only |
| Network access | the live contract test and the fixture-capture run only |

The offline unit suite needs **none** of the last three.

---

## 1. Offline unit suite (no network, no credentials)

```bash
pytest tests/unit -q
```

Expected: all pass, sub-second. Proves the contract logic, the `FakeProvider`
behaviour, import-time rejection, the lifecycle guarantees, and error
classification without touching the runtime (Constitution Seam Rule).

## 2. Prove import-time rejection

```bash
# temporarily point at a map missing an operation the port declares
python -c "import rewind.ports"      # expect CapabilityError naming the operation, exit != 0
```

Expected: process exits before any `main()` runs, message names the offending
operation and points at the map (FR-000-03, NFR-000-01).

## 3. Regenerate the capability map + fixtures (live, needs key + network)

```bash
python tools/spine_test.py            # writes .rewind/capability-map.toml from a live run
python -c "from rewind.recording import RecordingProvider; from rewind.providers import DaytonaProvider; \
p=RecordingProvider(DaytonaProvider()); h=p.spawn(); p.run(h,'echo hi > f'); s=p.checkpoint(h); \
k=p.branch(s,2); [p.destroy(x) for x in (*k,h)]"   # writes fixtures/daytona/*.json
```

Expected: map lists only operations whose post-condition was asserted; `fork`
absent; `fixtures/daytona/*.json` all traceable to this run (NFR-000-03).

## 4. Contract / drift check (live, must finish < 30s)

```bash
time pytest tests/contract -q -m live
```

Expected: every declared operation exercised, each post-condition re-asserted,
experimental names pinned, wall clock < 30s enforced by the `_clock` fixture
(NFR-000-02, SC-007). Output distinguishes a credentials failure from a
capability failure from a budget-exceeded failure (NFR-000-06).

## 5. E2E demo path

```bash
python demo.py                        # or: pytest tests/e2e -q -m live
```

Expected: runs live against real sandboxes, live sandbox count visible, every
sandbox destroyed on exit including on a raised step (Constitution Articles XI,
XII).

---

## FR → named-test matrix (traceability gate)

Test files: `tests/unit/test_capabilities.py` (cap), `tests/unit/test_lifecycle.py` (life),
`tests/unit/test_error_classification.py` (err), `tests/unit/test_ports.py` (ports),
`tests/contract/test_daytona_contract.py` (live).

| Requirement | Named test | Layer |
|---|---|---|
| FR-000-01 map is machine-readable & complete | `cap::test_map_loads_and_is_complete`, `cap::test_missing_required_class_rejected` | unit |
| FR-000-01a verified only if post-condition asserted | `cap::test_missing_post_condition_rejected` + `live::test_each_op_postcondition` | unit + contract |
| FR-000-01b experimental name recorded with marker + pinned | `cap::test_experimental_without_marker_rejected` + `live::test_experimental_name_pinned` | unit + contract |
| FR-000-02 single port, no other path | `cap::test_no_sdk_import_outside_providers` (AST scan of `src/rewind`) | unit |
| FR-000-03 reject undeclared op at load time | `cap::test_undeclared_op_raises_on_import`, `cap::test_assert_declared_names_the_offender` | unit |
| FR-000-04 refuse op against unsupported class, before any call | `cap::test_assert_class_rejects_wrong_class_without_a_call` | unit |
| FR-000-05 offline port behaviourally equivalent | `ports::*` + `life::test_recording_then_replay_round_trips` + `life::test_fake_matches_recorded_result` (skips until live fixtures exist) | unit |
| FR-000-06 identifiers preserved verbatim, no parse/construct | `cap::test_identifier_is_opaque` | unit |
| FR-000-07 record operation, outcome, elapsed per call | `err::test_call_record_fields_present` | unit |
| FR-000-08 stop + delete interval on every sandbox | `life::test_intervals_attached_on_create` + `live::test_intervals_live` | unit + contract |
| FR-000-08a not returned until command-ready | `life::test_created_sandbox_is_ready_before_handoff`, `life::test_not_ready_fails_creation_and_destroys` | unit |
| FR-000-09 destroyed even when using op raises / creation fails; retry then leak | `ports::test_cleanup_always_runs`, `life::test_cleanup_runs_even_when_using_op_raises`, `life::test_destroy_retry_then_leak`, `life::test_destroy_retry_succeeds_within_bound` | unit |
| FR-000-10 classify retryable / capacity / terminal + ambiguous→capacity | `err::test_transient_is_retryable`, `err::test_quota_and_capacity_are_capacity`, `err::test_bad_request_is_terminal`, `err::test_ambiguous_defaults_to_capacity_never_terminal` | unit |
| FR-000-11 enforce ceiling; bounded wait; keep siblings | `life::test_ceiling_blocks_then_capacity` | unit |
| NFR-000-01 undeclared op fails at load, not demo | `cap::test_undeclared_op_raises_on_import` (subprocess `import rewind.ports`) | unit |
| NFR-000-02 contract suite re-runnable < 30s | `live::_clock` fixture (asserts wall clock < 30s) | contract |
| NFR-000-03 fixtures captured from live runs only | `life::test_every_fixture_carries_provenance` (`recorded_at` + `runtime_version` on every file) | unit |
| NFR-000-04 fake supports configurable latency + failure rate | `life::test_fake_latency_configurable`, `life::test_fake_failure_rate_configurable`, `ports::test_failure_does_not_abort_others` | unit |
| NFR-000-05 bounded waits/retries are declared & recorded | `life::test_bounds_are_declared_constants` | unit |
| NFR-000-06 contract output separates failure kinds | `live::test_failure_kinds_distinguished` | contract |

| Success criterion | Verified by |
|---|---|
| SC-001 | `cap::test_undeclared_op_raises_on_import`, `cap::test_map_loads_and_is_complete` |
| SC-002 | `pytest -q` green with network + creds absent (35 passed, 1 skipped) |
| SC-003 | `life::test_fake_matches_recorded_result` (needs committed live fixtures) |
| SC-004 | `life::test_intervals_attached_on_create`, `life::test_cleanup_runs_even_when_using_op_raises`, `life::test_destroy_retry_then_leak` |
| SC-005 | `life::test_ceiling_blocks_then_capacity` |
| SC-006 | `err::test_call_record_fields_present`, `err::test_classification_on_record` |
| SC-007 | `live::_clock`, `live::test_each_op_postcondition`, `live::test_experimental_name_pinned` |
| SC-008 | `life::test_every_fixture_carries_provenance` |
| SC-009 | `life::test_fake_latency_configurable` |

---

## Gate checkpoints (Constitution)

- **G2 (by 13:00)**: `pytest tests/unit` green offline; `tests/contract` green
  live in < 30s. Tag `g2`.
- **G3 (15:00 freeze)**: re-run `tests/contract` live; confirm the map is
  current; tag `g3`. No further changes to `capabilities.py` / `providers.py`.
