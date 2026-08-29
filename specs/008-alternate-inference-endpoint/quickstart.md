# Quickstart: Alternate Inference Endpoint

---

## Route the critic to a self-hosted endpoint

```bash
export CRITIC_BASE_URL=https://my-gpu-box:8000/v1
export CRITIC_MODEL=my-served-model
export CRITIC_API_KEY=...            # optional; falls back to LLM_API_KEY
# optional: export REWIND_ALT_WAIT=4   (clamped to <= CRITIC_WAIT)
```

Unset either of `CRITIC_BASE_URL` / `CRITIC_MODEL` → the critic uses the primary
provider and the system runs exactly as before (FR-008-07).

## Assess the endpoint (one-time, live)

```bash
pytest tests/contract/test_alternate_endpoint_contract.py -m live -q
```

Green → the alternate is reachable and returns a conforming verdict; it may go on
a captured demo run. Red / skipped → the demo uses the primary; remove
`CRITIC_BASE_URL`.

## Offline

```bash
pytest tests/unit/test_alternate_endpoint.py -q     # routing + fallback with stub endpoints (SC-010)
```

---

## FR / NFR / SC → named-test matrix

`alt` = `tests/unit/test_alternate_endpoint.py`; `live` =
`tests/contract/test_alternate_endpoint_contract.py`.

| Requirement | Named test |
|---|---|
| FR-008-01 route a role by config, no code change | `alt::test_factory_routes_when_config_complete`, `alt::test_factory_plain_when_config_absent` |
| FR-008-02 same reasoning port | `alt::test_routed_reasoner_is_a_reasoning_port` (has `next_instruction`) |
| FR-008-03 same schema, identical rejection | `alt::test_alternate_bad_schema_rejected_like_primary` (SC-002) |
| FR-008-04 fallback alternate→primary→deterministic; record which | `alt::test_alternate_ok_served_by_alternate`, `alt::test_alternate_raise_falls_back_to_primary`, `alt::test_alternate_bad_falls_back_to_primary`, `alt::test_both_fail_deterministic` (SC-001/003) |
| FR-008-05 bounded alternate wait ≤ CRITIC_WAIT | `alt::test_alt_wait_le_critic_wait`, `alt::test_slow_alternate_falls_back_within_bound` (SC-004/005) |
| FR-008-06 provider shown per verdict | `alt::test_served_by_on_verdict_record` + a console check in the visual-acceptance pass (SC-006) |
| FR-008-07 unset config = unchanged | `alt::test_unset_config_runs_unchanged` (SC-007) |
| FR-008-08 availability check gates demo-path use | `live::test_alternate_reachable_and_conforming` (NFR-008-02) |
| NFR-008-01 additive, no dependency | `alt::test_no_spec_00x_imports_routed` (AST scan of `src/rewind` for `RoutedReasoner` / `critic_reasoner` outside `reasoning.py`) |
| NFR-008-03 undelivered = complete + truthful | `alt::test_full_suite_unchanged_when_unset` (runs a representative judge_and_promote with a plain stub → record `primary`) — SC-008 |
| NFR-008-04 routing verifiable offline | the whole of `test_alternate_endpoint.py` — no network / creds (SC-010) |

| Success criterion | Verified by |
|---|---|
| SC-001 | `alt::test_alternate_ok_served_by_alternate` |
| SC-002 | `alt::test_alternate_bad_schema_rejected_like_primary` |
| SC-003 | `alt::test_alternate_raise_falls_back_to_primary`, `alt::test_both_fail_deterministic` |
| SC-004 | `alt::test_alt_wait_le_critic_wait` |
| SC-005 | `alt::test_slow_alternate_falls_back_within_bound` |
| SC-006 | `alt::test_served_by_on_verdict_record` + console visual-acceptance |
| SC-007 | `alt::test_unset_config_runs_unchanged` + full-suite run with the config unset |
| SC-008 | `alt::test_no_spec_00x_imports_routed`, full suite green unchanged |
| SC-009 | `live::test_alternate_reachable_and_conforming` (the gate) |
| SC-010 | `test_alternate_endpoint.py` runs offline |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_alternate_endpoint.py -q` green; the full
  offline suite (000–007) still green with `CRITIC_BASE_URL` unset.
- **Article VIII assessment**: `pytest tests/contract/test_alternate_endpoint_contract.py -m live`
  once — green → allowed on a captured demo run; otherwise remove the config.
