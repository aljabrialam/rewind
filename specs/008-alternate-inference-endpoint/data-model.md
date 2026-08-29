# Phase 1 Data Model: Alternate Inference Endpoint

New members in `reasoning.py` / `capabilities.py`; a `served_by` key added to the
Spec 005 verdict record. Everything else composed unchanged.

---

## 1. Alternate Config  (environment)

| Var | Meaning |
|---|---|
| `CRITIC_BASE_URL` | the alternate endpoint address (OpenAI-compatible) |
| `CRITIC_MODEL` | the model name at that endpoint |
| `CRITIC_API_KEY` | optional; falls back to `LLM_API_KEY` |
| `REWIND_ALT_WAIT` | optional; the alternate wait bound, clamped to ≤ `CRITIC_WAIT` |

**Complete** = `CRITIC_BASE_URL` **and** `CRITIC_MODEL` both non-empty →
routing on for the critic role. **Incomplete / unset** = alternate absent, the
role uses the primary (FR-008-07). An incomplete config is ignored, not an error.

---

## 2. `LiveReasoner`  (parameterised — additive)

```
LiveReasoner(*, base_url: str | None = None, model: str | None = None,
             api_key: str | None = None)
```

Each arg defaults to its `LLM_*` env var (`LLM_BASE_URL` / `LLM_MODEL` /
`LLM_API_KEY`). Existing no-arg construction is unchanged. Still the only module
member that imports a reasoning vendor (Article IV).

---

## 3. `RoutedReasoner`  (a `ReasoningPort`)

```
RoutedReasoner(alternate: ReasoningPort, primary: ReasoningPort, *,
               bound: float, validate: Callable[[Mapping, str], None] | None = None)
```

| Field | Type | Notes |
|---|---|---|
| `_alternate` / `_primary` | ReasoningPort | the two endpoints |
| `_bound` | float | `capabilities.ALT_WAIT` — max wait on the alternate |
| `_validate` | callable \| None | `(raw, context) -> None`, raises on non-conformance (critic: `validate_verdict(raw, verdict_ids_from_bundle(context))`) |
| `last_served_by` | `"alternate"` \| `"primary"` | which endpoint answered the most recent `next_instruction` |

`next_instruction(context) -> Mapping`:

| Step | |
|---|---|
| 1 | run `_alternate.next_instruction(context)` with `future.result(timeout=_bound)` |
| 2 | if it returned and `_validate(raw, context)` did not raise → `last_served_by = "alternate"`, **return raw** |
| 3 | on `TimeoutError`, any exception, or a `_validate` failure → `last_served_by = "primary"`, **return `_primary.next_instruction(context)`** |
| 4 | a late alternate result after step 3 is discarded (executor `shutdown(wait=False, cancel_futures=True)`) |

The primary's response is **not** re-validated by the router — `Engine.evaluate`
validates whatever `next_instruction` returns, exactly as before.

---

## 4. `verdict_ids_from_bundle(context) -> list[str]`

`re.findall(r"branch (\S+) \|", context)` — the branch ids `Engine._evidence_bundle`
writes into the critic's context. Used by the critic validator so the alternate
response is checked with the identical `validate_verdict(raw, ids)`.

---

## 5. `critic_reasoner() -> ReasoningPort`  (factory)

| Config | Returns |
|---|---|
| `CRITIC_BASE_URL` **and** `CRITIC_MODEL` set | `RoutedReasoner(LiveReasoner(base_url=…, model=…, api_key=…), LiveReasoner(), bound=ALT_WAIT, validate=<critic>)` |
| otherwise | `LiveReasoner()` — the plain primary, unchanged (FR-008-07) |

Called by fixture capture and any live critic entry point; **not** by the
replayed demo path (Article VIII — the alternate is never on the critical path).

---

## 6. `served_by` on the verdict record  (Spec 005 record + 1 key)

`Engine.evaluate` result and `judge_and_promote`'s verdict record gain:

| Value | When |
|---|---|
| `"alternate"` | the alternate endpoint produced the accepted verdict |
| `"primary"` | the primary produced it (alternate absent / unreachable / slow / invalid), or no critic was consulted (single branch) |
| `"deterministic-fallback"` | the exit-status ranking decided it (critic path exhausted) |

`Engine.evaluate`: `served_by = getattr(critic, "last_served_by", "primary")` on
the accepted-verdict path; `"deterministic-fallback"` inside `_fallback(...)`.
`console_fixture` carries the record through; the console shows `verdict.served_by`.

---

## 7. `capabilities.ALT_WAIT`

`ALT_WAIT = min(_f("REWIND_ALT_WAIT", CRITIC_WAIT), CRITIC_WAIT)` — a float,
never greater than `CRITIC_WAIT` (FR-008-05 / SC-004).

---

## 8. Routing state machine (one `next_instruction`)

| State | Enters | Exits |
|---|---|---|
| `try-alternate` | `next_instruction(context)` | → `serve-alternate` if it returns within `bound` and validates; → `try-primary` on timeout / exception / validation failure |
| `serve-alternate` | alternate ok | `last_served_by = "alternate"`, return raw |
| `try-primary` | alternate failed | `last_served_by = "primary"`, return `_primary.next_instruction(context)` (may itself raise — propagates to `Engine.evaluate`, which then uses the deterministic fallback) |

---

## Type glossary

| Name | Definition |
|---|---|
| `RoutedReasoner` | `ReasoningPort` — alternate-then-primary with `last_served_by` |
| `served_by` | `"alternate"` \| `"primary"` \| `"deterministic-fallback"` on the verdict record |
| `ALT_WAIT` | `capabilities` constant — alternate wait bound, ≤ `CRITIC_WAIT` |
| complete alternate config | `CRITIC_BASE_URL` and `CRITIC_MODEL` both set |
