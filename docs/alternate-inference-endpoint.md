# Alternate Inference Endpoint (spec 008)

Route the **critic** reasoning role to a self-hosted model on independent GPU
infrastructure, by configuration, through the same reasoning port, with automatic
fallback to the primary. The **additive second-sponsor integration**
(Constitution Article VIII): background-provisioned, assessed once, and
**deletable with zero impact** — nothing in specs 000–007 changes when
`CRITIC_BASE_URL` is unset. Full spec:
[`specs/008-alternate-inference-endpoint/`](../specs/008-alternate-inference-endpoint/).

## Configure

```bash
export CRITIC_BASE_URL=https://my-gpu-box:8000/v1
export CRITIC_MODEL=my-served-model
export CRITIC_API_KEY=...            # optional; falls back to LLM_API_KEY
# export REWIND_ALT_WAIT=4           # optional; clamped to <= REWIND_CRITIC_WAIT
```

**Both** `CRITIC_BASE_URL` and `CRITIC_MODEL` set → the critic is routed. Either
unset → the plain primary, identical to before this feature.

## The pieces (`src/rewind/reasoning.py`)

| Member | Role |
|---|---|
| `LiveReasoner(*, base_url, model, api_key)` | now parameterised; each arg defaults to its `LLM_*` env var. Still the only reasoning-vendor importer. |
| `RoutedReasoner(alternate, primary, *, bound, validate)` | a `ReasoningPort`: tries `alternate` within `bound` (`capabilities.ALT_WAIT ≤ CRITIC_WAIT`), validates its response with the **same** rule as the primary's, falls back to `primary` on timeout / error / non-conformance. `last_served_by` = `"alternate"` \| `"primary"`. |
| `verdict_ids_from_bundle(context)` | parses the branch ids from the critic's evidence bundle, so the alternate response is checked with the identical `validate_verdict`. |
| `critic_reasoner()` | the factory — a `RoutedReasoner` iff the config is complete, else a plain `LiveReasoner`. |

`Engine.evaluate` reads `getattr(critic, "last_served_by", "primary")` and puts
`served_by` on the verdict record — one of `alternate` / `primary` /
`deterministic-fallback`. The console's Verdict block shows it: *served by …*.

## Assess it (Article VIII — once)

```bash
CRITIC_BASE_URL=... CRITIC_MODEL=... pytest tests/contract/test_alternate_endpoint_contract.py -m live -q
```

Green → the alternate is reachable and conforming; it may go on a **captured**
demo run (`tools/capture_demo_fixtures.py`). Red / not serving by the assessment
→ remove `CRITIC_BASE_URL`; the record reads `primary` and the demo claims no
alternate provider.

## Deletability

Remove `RoutedReasoner` + `critic_reasoner()` + the ~4 `served_by` lines in
`engine.py` and the system is exactly spec 007. That is the Article VIII
contract, made structural.

## Running

```bash
pytest tests/unit/test_alternate_endpoint.py -q     # 14 offline tests (stub endpoints)
```
