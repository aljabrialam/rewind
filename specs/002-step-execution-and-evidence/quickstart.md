# Quickstart: Step Execution and Evidence

Run / validation guide plus the FR/NFR/SC → named-test matrix (Constitution
Article VI traceability gate).

---

## Prerequisites

| Need | For |
|---|---|
| Python 3.11+, `pip install -e .`, `pytest` | everything |
| Spec 000 in place (`.rewind/capability-map.toml`, `src/rewind/capabilities.py`) | `import rewind.ports` |
| `fixtures/reasoning/*.json` present | fixture-backed offline runs |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | the live reasoning contract test + fixture capture only |

The offline unit suite needs none of the last two.

---

## 1. Offline step loop (no network, no credentials)

```bash
pytest tests/unit/test_stepping.py tests/unit/test_reasoning.py -q
```

Expected: green, sub-second. `FakeProvider` + `ReplayReasoner` drive the whole
loop — schema validation, evidence capture, failure halt, step bound.

## 2. Schema rejection

```bash
python -c "from rewind.reasoning import validate; validate({'instruction': ''})"
# -> SchemaError; nothing executes
```

## 3. Deterministic rehearsal

```bash
pytest tests/unit/test_reasoning.py::test_replay_is_deterministic -q
```

Same fixtures → same ordered instructions, twice.

## 4. Regenerate reasoning fixtures (live — needs LLM creds)

```bash
python -c "from rewind.reasoning import RecordingReasoner, LiveReasoner; \
r=RecordingReasoner(LiveReasoner()); [r.next_instruction('demo step %d'%i) for i in range(5)]"
```

Writes `fixtures/reasoning/*.json` with `recorded_at` + `model`.

## 5. Live reasoning contract (needs LLM creds)

```bash
pytest tests/contract/test_reasoning_contract.py -m live -q
```

Expected: the real provider still returns an object that passes `validate()`.

## 6. E2E

```bash
FAKE=1 python demo.py     # the scripted path, offline
```

---

## FR / NFR / SC → named-test matrix

Files: `tests/unit/test_reasoning.py` (rsn), `tests/unit/test_stepping.py` (step),
`tests/unit/test_ports.py` (ports), `tests/contract/test_reasoning_contract.py` (live).

| Requirement | Named test | Layer |
|---|---|---|
| FR-002-01 structured instruction; reject non-conforming | `rsn::test_valid_payload_accepted`, `rsn::test_missing_instruction_rejected`, `rsn::test_empty_instruction_rejected`, `rsn::test_missing_rationale_rejected`, `rsn::test_wrong_types_rejected`, `rsn::test_unknown_keys_ignored` | unit |
| FR-002-02 execute via the capability port | `step::test_step_runs_through_the_port` (asserts `provider.calls` records a `run`) | unit |
| FR-002-03 capture exit / stdout / elapsed | `step::test_evidence_fields_captured`, `step::test_empty_output_is_not_missing_evidence` | unit |
| FR-002-04 evidence is sole basis; rationale not substituted | `step::test_outcome_follows_exit_status_not_rationale` | unit |
| FR-002-05 evidence attached to the checkpoint | `step::test_evidence_attached_to_checkpoint` | unit |
| FR-002-06 failing step halts branch, prior checkpoints intact | `step::test_failure_halts_branch`, `step::test_prior_checkpoints_survive_failure`, `step::test_step_on_halted_branch_raises` | unit |
| FR-002-07 single declared step bound | `step::test_step_bound_stops_branch`, `step::test_bound_is_single_value` | unit |
| FR-002-08 rationale recorded, distinct from evidence | `step::test_rationale_and_evidence_are_separate_fields` | unit |
| NFR-002-01 identical path live vs fake | `step::test_call_sequence_is_fixed` (fake) + `live::test_call_sequence_matches_live` | unit + contract |
| NFR-002-02 reasoning replayable, deterministic | `rsn::test_replay_is_deterministic`, `rsn::test_replay_exhaustion_raises` | unit |
| NFR-002-03 full loop offline, no creds | `step::test_full_loop_offline` | unit |

| Success criterion | Verified by |
|---|---|
| SC-001 | `step::test_evidence_fields_captured`, `step::test_empty_output_is_not_missing_evidence` |
| SC-002 | `rsn::test_missing_instruction_rejected` + `step::test_reject_creates_no_checkpoint` |
| SC-003 | `step::test_prior_checkpoints_survive_failure` |
| SC-004 | `step::test_outcome_follows_exit_status_not_rationale` |
| SC-005 | `step::test_rationale_and_evidence_are_separate_fields` |
| SC-006 | `step::test_step_bound_stops_branch` |
| SC-007 | `rsn::test_replay_is_deterministic` |
| SC-008 | `step::test_full_loop_offline` |

---

## Gate checkpoints

- **G2**: `pytest tests/unit -q` green offline; live reasoning contract green.
- **G3**: re-run the live reasoning contract; confirm fixtures current; no more
  edits to `reasoning.py` / `engine.py`.
