# Phase 0 Research: Alternate Inference Endpoint

Spec 008 carries no `[NEEDS CLARIFICATION]`. Decisions for design. Evidence:
`src/rewind/reasoning.py` (`ReasoningPort`, `LiveReasoner`, `validate_verdict`),
`src/rewind/engine.py` (`Engine.evaluate` — bounded critic call + `_fallback`;
`judge_and_promote` — verdict record; `rank_by_evidence` — `provider:
"deterministic-fallback"`), `src/rewind/capabilities.py` (`CRITIC_WAIT`, `_f`),
`.env.example` (`CRITIC_BASE_URL` / `CRITIC_MODEL`), Constitution Article VIII.

---

## R1. Where routing lives — `RoutedReasoner`, not `engine.py` (FR-008-01/02/04)

**Decision**: a `RoutedReasoner` in `reasoning.py` that *implements* the
`ReasoningPort` (`next_instruction(context) -> Mapping`). It holds an `alternate`
and a `primary` (both `LiveReasoner`), an `ALT_WAIT` bound, and an optional
`validate(raw, context)` callable. `next_instruction`:

1. run `alternate.next_instruction(context)` in a `ThreadPoolExecutor` with
   `future.result(timeout=ALT_WAIT)`;
2. if it returns and `validate` (if given) does not raise → `last_served_by =
   "alternate"`, return it;
3. any timeout / exception / validation failure → `last_served_by = "primary"`,
   return `primary.next_instruction(context)`.

`Engine.evaluate` is passed this object as its `critic` and calls it exactly as
before. It reads `getattr(critic, "last_served_by", "primary")` after the call.

**Rationale**: FR-008-02 (same port — `RoutedReasoner` *is* a `ReasoningPort`);
FR-008-04 (alternate-invalid → *primary*, which only works if the router
validates the alternate's response itself — `evaluate`'s existing
`VerdictSchemaError` handler goes to the *deterministic* fallback, not primary).
Keeping routing out of `engine.py` means the loop code is untouched (Article V)
and a plain `LiveReasoner` still works (Article VIII — deletable).

**Alternatives considered**:
- Add the retry-primary logic to `Engine.evaluate` — rejected: `engine.py` would
  grow provider-routing knowledge for one role; `RoutedReasoner` keeps it in the
  reasoning seam.

---

## R2. Validating the alternate's response with the same schema (FR-008-03)

**Decision**: `RoutedReasoner` for the critic is built with
`validate=lambda raw, ctx: validate_verdict(raw, verdict_ids_from_bundle(ctx))`.
`verdict_ids_from_bundle(context)` = `re.findall(r"branch (\S+) \|", context)` —
the branch ids `Engine._evidence_bundle` writes into the context. So the
alternate response is checked by the **identical** `validate_verdict` the primary
response is checked by (in `evaluate`); a non-conforming alternate response
raises `VerdictSchemaError` inside the router and triggers the primary call.

**Rationale**: FR-008-03 / SC-002 — same rule, same rejection. A generic
`RoutedReasoner` stays role-agnostic; the critic factory supplies the critic
validator.

---

## R3. `ALT_WAIT` derivation and clamp (FR-008-05, SC-004/005)

**Decision**: `capabilities.ALT_WAIT = min(_f("REWIND_ALT_WAIT", CRITIC_WAIT),
CRITIC_WAIT)`. The alternate can be given a *shorter* bound but never a longer
one than the critic role already has. `Engine.evaluate` still bounds the *whole*
critic call at `CRITIC_WAIT`; the router bounds just the alternate at `ALT_WAIT`
and then spends the remainder on the primary — so the total is still ≤
`CRITIC_WAIT`, and the demo path (Spec 007) budget holds.

**Rationale**: FR-008-05 — the alternate's latency cannot extend the path.

---

## R4. `served_by` from router → record → console (FR-008-04/06)

**Decision**:
- `Engine.evaluate` adds `served_by` to its result dict: on the success path
  `getattr(critic, "last_served_by", "primary")`; in `_fallback(...)`
  `"deterministic-fallback"`; on the single-branch / no-critic paths `"primary"`
  (no critic was consulted).
- `Engine.judge_and_promote` copies `ev["served_by"]` onto the verdict record
  (`{..., "served_by": ...}`) — write-once with the rest of the record.
- `ui/console.html` verdict block shows `verdict.served_by` (falling back to
  `verdict.provider` for older fixtures).

**Rationale**: FR-008-06 / Article X — the console *shows* which provider judged.
Values are exactly the three the spec names.

---

## R5. `critic_reasoner()` factory + the complete-config gate (FR-008-01/07)

**Decision**: `reasoning.critic_reasoner() -> ReasoningPort`:
- `primary = LiveReasoner()` (reads `LLM_*`).
- if `os.environ.get("CRITIC_BASE_URL")` **and** `os.environ.get("CRITIC_MODEL")`
  are both non-empty → `alternate = LiveReasoner(base_url=…, model=…,
  api_key=os.environ.get("CRITIC_API_KEY") or os.environ["LLM_API_KEY"])`;
  return `RoutedReasoner(alternate, primary, bound=capabilities.ALT_WAIT,
  validate=<critic validator>)`.
- else → return `primary` unchanged.

`LiveReasoner.__init__` gains keyword-only `base_url` / `model` / `api_key`,
each defaulting to the corresponding `LLM_*` env var — backward compatible
(existing no-arg construction unchanged).

**Rationale**: FR-008-01 (config selects, no code change); FR-008-07 (partial or
unset config → the plain primary, identical behaviour — SC-007/008). The factory
is called by fixture capture / a live entry point, **not** by the replayed demo
path.

---

## R6. Nothing in 000–007 changes when unset (NFR-008-03, SC-007/008)

**Decision**: with `CRITIC_BASE_URL` unset:
- `critic_reasoner()` returns a plain `LiveReasoner` — no `RoutedReasoner`.
- `Engine.evaluate`'s new line is `getattr(critic, "last_served_by", "primary")`
  — a plain critic / stub has no such attribute → `"primary"`, inert.
- `judge_and_promote` writes `served_by="primary"` (or
  `"deterministic-fallback"`) — an extra key on the record; the console tolerates
  its absence in old fixtures and its presence here.
- No test 000–007 constructs a `RoutedReasoner`; all pass unchanged. Verified by
  running the full suite after the edit.

---

## R7. The availability check (FR-008-08, NFR-008-02)

**Decision**: `tests/contract/test_alternate_endpoint_contract.py`,
`@pytest.mark.live`, `skipif(not CRITIC_BASE_URL)`. It builds the alternate
`LiveReasoner` directly, sends one evidence-bundle-shaped prompt, and asserts
`validate_verdict` accepts the response. This is the one-time assessment: green ⇒
the alternate may go on a captured demo run; red ⇒ remove `CRITIC_BASE_URL` and
the record says `primary` (SC-007 §3).

---

## Open items carried to Phase 1

- `RoutedReasoner` fields + state machine → [data-model.md](data-model.md)
- try-order / bound / validation / `served_by` obligations → [contracts/routed-reasoner.md](contracts/routed-reasoner.md)
- FR→test map → [quickstart.md](quickstart.md)
