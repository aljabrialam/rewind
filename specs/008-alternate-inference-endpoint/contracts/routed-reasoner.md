# Contract: Routed Reasoner

`reasoning.RoutedReasoner`, `reasoning.critic_reasoner()`, and the `served_by`
pass-through in `Engine.evaluate` / `judge_and_promote`.

Traces: FR-008-01 … FR-008-08, NFR-008-01 … NFR-008-04.

---

## `RoutedReasoner(alternate, primary, *, bound, validate=None)` — a `ReasoningPort`

| # | Obligation | Trace |
|---|---|---|
| C1 | Implements `next_instruction(context) -> Mapping` — the **same** port as `LiveReasoner` / `ReplayReasoner`. No separate interface. | FR-008-02 |
| C2 | Runs `alternate.next_instruction(context)` with a wall-clock bound of `bound` (`capabilities.ALT_WAIT`). A hung alternate is abandoned at `bound` — the executor is `shutdown(wait=False, cancel_futures=True)`, never joined. | FR-008-05, SC-004 |
| C3 | If the alternate returns within `bound` **and** `validate(raw, context)` (when given) does not raise → `last_served_by = "alternate"`, return `raw`. | FR-008-01, US1 |
| C4 | On alternate timeout, any alternate exception, or a `validate` failure → `last_served_by = "primary"`, return `primary.next_instruction(context)`. | FR-008-04 |
| C5 | `validate` for the critic is `validate_verdict(raw, verdict_ids_from_bundle(context))` — the **identical** rule and rejection applied to a primary response by `Engine.evaluate`. | FR-008-03, SC-002 |
| C6 | A late alternate response (arriving after the primary was already asked) is discarded; the primary's response stands. | edge case |
| C7 | The primary's response is **not** re-validated by the router — `Engine.evaluate` validates whatever `next_instruction` returns, as before. | FR-008-03 |
| C8 | `last_served_by` reflects the most recent `next_instruction` call. | FR-008-04/06 |

---

## `critic_reasoner() -> ReasoningPort`

| Config | Returns | Trace |
|---|---|---|
| `CRITIC_BASE_URL` and `CRITIC_MODEL` both non-empty | `RoutedReasoner(LiveReasoner(base_url, model, api_key), LiveReasoner(), bound=ALT_WAIT, validate=<critic>)` | FR-008-01 |
| either unset / empty | `LiveReasoner()` — the plain primary; **identical behaviour to before this feature** | FR-008-07, SC-007/008 |

`api_key` = `CRITIC_API_KEY` or `LLM_API_KEY`. Read at call time — changing
`CRITIC_BASE_URL` between runs takes effect with no code change (FR-008-01).

---

## `served_by` on the verdict (Engine — ~4 lines)

| Location | Rule | Trace |
|---|---|---|
| `Engine.evaluate` accepted-verdict path | `served_by = getattr(critic, "last_served_by", "primary")` | FR-008-04 |
| `Engine.evaluate` `_fallback(...)` | `served_by = "deterministic-fallback"` | FR-008-04 |
| `Engine.evaluate` single-branch / no-critic path | `served_by = "primary"` | — |
| `Engine.judge_and_promote` verdict record | `record["served_by"] = ev["served_by"]` (write-once with the record) | FR-008-04/06 |
| `console_fixture` | carries the record through unchanged | FR-008-06 |
| `ui/console.html` verdict block | shows `verdict.served_by` (fallback: `verdict.provider`) | FR-008-06, SC-006 |

A plain `critic` / stub has no `last_served_by` → `"primary"`. The new key is
inert when the config is unset (SC-008).

---

## Article VIII / "unchanged when undelivered" (NFR-008-01/03, SC-007/008)

| # | Obligation |
|---|---|
| G1 | Nothing in specs 000–007 imports `RoutedReasoner` or `critic_reasoner()`; the demo path (Spec 007) replays reasoning and is untouched. |
| G2 | With `CRITIC_BASE_URL` unset, the full offline suite passes with **zero** outcome changes; the verdict record reads `primary` / `deterministic-fallback`. |
| G3 | The alternate is used on a captured demo run only after `test_alternate_endpoint_contract.py` (live, skipped when unset) is green (FR-008-08 / NFR-008-02). |
| G4 | If the alternate is not serving at the one-time assessment, `CRITIC_BASE_URL` is removed and no output claims an alternate provider (SC-007 §3, Article XIII). |

---

## Offline verifiability (NFR-008-04, SC-010)

`RoutedReasoner` is tested with in-process stub endpoints — objects with a
`next_instruction` that returns a dict / raises / sleeps — no network, no
credentials. Routing (`"alternate"`), fallback on raise / timeout / bad-schema
(`"primary"`), and both-fail → deterministic (`"deterministic-fallback"`) are all
covered offline.
