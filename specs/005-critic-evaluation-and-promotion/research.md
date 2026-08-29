# Phase 0 Research: Critic Evaluation and Promotion

Spec 005 carries no `[NEEDS CLARIFICATION]`. Decisions for design. Evidence:
`src/rewind/engine.py` (`promote`, `rank_by_evidence`, `Run.mark_terminal`,
`fan_out`/`branch_from`, `console_fixture`), `src/rewind/reasoning.py`
(`ReasoningPort`, `validate`, `SchemaError`), `src/rewind/ports.py`
(`Checkpoint`), `src/rewind/capabilities.py` (declared bounds pattern),
Constitution Articles IX, X, XII.

---

## R1. The verdict schema and its validator (FR-005-02/03)

**Decision**: add to `reasoning.py`:
- `Verdict` frozen dataclass `{chosen: str, scores: dict[str, float], reason: str}`.
- `VerdictSchemaError(SchemaError)`.
- `validate_verdict(payload: Mapping, branch_ids: Sequence[str]) -> Verdict`.

Rules (all → `VerdictSchemaError`, which the caller catches → fallback):
`payload` is a mapping; `chosen` present, a str, ∈ `branch_ids`; `scores` present,
a mapping covering **every** id in `branch_ids` with a value coercible to
`float`; `reason` present, a non-empty str. `scores` given as a list of
`{branch, score}` objects is also accepted and normalised to the dict.

**Rationale**: FR-005-02/03. Same *mechanism* as Spec 002 (a `SchemaError`
subclass, rejection not exception-through), different *fields* — the strategist
and the critic have different structured responses.

**Alternatives considered**:
- Reuse `validate()` (`{instruction, rationale}`) — rejected: wrong fields.
- Accept a partial `scores` and default the rest to 0 — rejected: FR-005-03
  explicitly rejects an omitted score.

---

## R2. The evidence bundle — no self-description (FR-005-01, SC-001)

**Decision**: `Engine._evidence_bundle(branches) -> str` builds a plain-text
block, one section per branch: `branch <id> | exit <code> | elapsed <s> |
output:\n<stdout truncated>`. It reads **only** `Checkpoint.evidence` and
`Checkpoint.step_id`. It never includes `Checkpoint.rationale` (the strategist's
account) or any other agent text. The bundle is what is passed as the critic's
`context`.

**Rationale**: FR-005-01 / Article X. A test asserts the bundle string contains
each branch's exit code and none of the branches' `rationale` text.

---

## R3. Bounded critic wait (NFR-005-03, timeout edge case)

**Decision**: `capabilities.CRITIC_WAIT` (default 8.0s, `REWIND_CRITIC_WAIT`
override). `Engine.evaluate` runs `critic.next_instruction(bundle)` in a
`ThreadPoolExecutor` and calls `future.result(timeout=CRITIC_WAIT)`. A
`FuturesTimeoutError`, any exception, or a `VerdictSchemaError` from
`validate_verdict` → deterministic fallback, with `fallback_trigger` set to
`"critic-timeout"` / `"critic-unreachable: <msg>"` / `"verdict-rejected: <why>"`.

**Rationale**: NFR-005-03 and the "reasoning endpoint times out mid-verdict"
edge case — a hung call must not stall promotion past the bound. Mirrors Spec
000's bounded-wait discipline.

---

## R4. Write-once verdict record on the parent (FR-005-06, SC-007)

**Decision**: `Checkpoint.verdict: dict | None = None` (additive field).
`Run.record_verdict(parent_id, record)` sets it only if currently `None`
(a second call for the same parent is a no-op that returns the existing record);
`Run.get_verdict(parent_id)` reads it. The record:
`{chosen, scores, reason, reason_unsupported: bool, fallback_used: bool,
fallback_trigger: str | None, recorded_at}`.

**Rationale**: FR-005-06 / SC-007 — each round's parent is distinct, and a
round's record must survive later rounds. `console_fixture` already emits a
`verdict` key; it will now read the promoted parent's `verdict` record.

---

## R5. Hardened deterministic fallback (FR-005-07, NFR-005-02, SC-006)

**Decision**: `rank_by_evidence(branches)` keeps its return shape
(`{winner: <index>, scores: [...], reason, provider}`) and gains:
- sort key `(exit_code or 99, elapsed or 1e9, index, step_id)` — total and
  reproducible, including all-failed sets (every exit non-zero → still a strict
  order by exit then elapsed then index then id);
- each `scores[i]` entry gains a numeric `score = -(exit_code*1e6) - elapsed`
  (higher is better), so the fallback and the critic path both yield a
  per-branch number;
- `reason` notes a tie when the top two share `(exit_code, elapsed)`.

**Rationale**: NFR-005-02 (pure + total) and the "identical evidence" / "every
branch fails" edge cases. Keeping the shape means `demo.py`
(`branches[verdict["winner"]]`) is unaffected.

---

## R6. Formalising `promote` without a breaking change (FR-005-04/05)

**Decision**: `promote(winner_step_id, losers, *, verdict: dict | None = None,
parent_id: str | None = None) -> dict`. Keeps the positional `(winner, losers)`
call `demo.py` uses. New behaviour:
- winner re-derivation from `snapshot` wrapped in try/except → on failure return
  a result with `error=<classified msg>`, **head unchanged** (headless safety,
  FR-005-04);
- loser release: `for sid in losers:` pop the handle if any, `destroy` in
  try/except, record `{sid, released: bool, error: <class> | None}` per loser;
  an already-absent handle is a clean `released: True` (idempotent, FR-005-05);
  one failure never breaks the loop;
- if `verdict` and `parent_id` given → `run.record_verdict(parent_id, verdict)`;
- returns `{head, winner, losers: [...], verdict_recorded: bool, error}`.

`Engine.judge_and_promote(branches, critic, context="", parent_id=None) -> dict`
= `evaluate(...)` then `promote(...)` with the verdict result; resolves
`parent_id` from the branches' common `parent_id` when not given.

**Rationale**: FR-005-04/05 + backward compatibility for `demo.py`.

---

## R7. All-failed / single / empty / still-running (FR-005-09/10, edge cases)

**Decision** in `evaluate` / `judge_and_promote`:
- **empty set** → return `{error: "no branches"}`, no critic call, head unchanged.
- **single branch** with a snapshot → promote it directly, record `"single
  branch — promoted without a verdict"`, no critic call.
- **still-running branch** (a branch whose `progress.state` / `terminal` is not
  terminal, or `evidence is None`) → wait up to a short bound
  (`capabilities.CRITIC_WAIT / 4`), then **exclude** it, record the exclusion,
  judge the rest. Never score it.
- **all failed** → the fallback still returns a total order; promote the
  least-bad (it has a snapshot); `reason` records "no branch exited 0".
- **critic names a destroyed/no-snapshot branch** → `validate_verdict` rejects
  (rule b) → fallback, which only ranks branches that have a snapshot as
  head-eligible.

**Rationale**: the seven folded edge cases + FR-005-09/10.

---

## R8. Ordered-call parity (NFR-005-04)

**Decision**: for `judge_and_promote` over N branches, no failures, critic path:
`provider.calls` operations are `branch×1` (winner re-derivation) + `destroy×(N-1)`
(losers). The critic call is a reasoning-port call, not a provider call, so it
does not appear in `provider.calls`. A unit test asserts the provider op multiset
against `FakeProvider`; the live contract test asserts the same against
`DaytonaProvider` and that the round is within `CRITIC_WAIT + margin`.

---

## Open items carried to Phase 1

- Exact dataclass fields + promotion state machine → [data-model.md](data-model.md)
- Verdict schema + rejection table + evidence bundle → [contracts/verdict.md](contracts/verdict.md)
- Promotion ordered calls + release semantics + record → [contracts/promotion.md](contracts/promotion.md)
- FR→test matrix → [quickstart.md](quickstart.md)
