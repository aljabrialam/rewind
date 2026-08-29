# Phase 0 Research: Step Execution and Evidence

Spec 002 carries no `[NEEDS CLARIFICATION]` — the open choices were closed as
Assumptions. This document records the technical decisions for design.

Evidence: `src/rewind/engine.py` (`Engine.step`, `Checkpoint`, `Run`),
`src/rewind/ports.py` (`LLMClient` stub, `ExecResult`, `Checkpoint`),
`.env.example` (`LLM_BASE_URL` / `LLM_MODEL` / `CRITIC_*`), README "The feedback
loop", Constitution Articles X and VI.

---

## R1. Instruction schema and validation

**Decision**: `Instruction` is a frozen dataclass `{instruction: str, rationale:
str}`. A module-level `validate(payload: Mapping) -> Instruction` enforces:
`instruction` present, a `str`, non-empty after strip; `rationale` present and a
`str` (may be empty string? — no: Assumptions say rationale is required; empty
rationale is a violation). Unknown keys are ignored. Any failure raises
`SchemaError` (subclass of `ValueError`). No `jsonschema` dependency — the schema
is four lines of checks.

**Rationale**: FR-002-01 requires rejection of non-conforming responses; the
minimal schema keeps the rejection rule unambiguous and testable. Article II
spirit — the smallest thing that works.

**Alternatives considered**:
- `jsonschema` / `pydantic` — rejected: a dependency for a two-field check; the
  repo has no runtime validation library and the hackathon clock discourages
  adding one.
- Accepting a bare command string — rejected: FR-002-08 needs the rationale in
  the same response, structurally.

---

## R2. Reasoning port and fixture replay

**Decision**: Replace the `LLMClient` stub in `ports.py` with `ReasoningPort`:

```
class ReasoningPort(Protocol):
    def next_instruction(self, context: str) -> Mapping: ...
```

Two implementations in `reasoning.py`:
- `LiveReasoner` — the only module that imports the reasoning-vendor SDK; calls
  an OpenAI-compatible chat completion, returns the parsed JSON object (still
  unvalidated — `validate()` is the gate, so a bad live response is rejected the
  same way a bad fixture is).
- `ReplayReasoner(fixtures_dir)` — returns recorded responses in recorded order;
  raises `LookupError` when exhausted.

`Engine.next_step(reasoner)` calls `reasoner.next_instruction(...)`, passes the
result through `validate()`, then delegates to the existing `step(instruction,
rationale)`.

**Rationale**: Mirrors the Spec 000 sandbox seam exactly (one port, live impl +
replay impl, no vendor import outside the boundary — Article IV). NFR-002-02 /
NFR-002-03 fall out of `ReplayReasoner` needing no network.

**Alternatives considered**:
- Reuse `LLMClient.complete(prompt, schema)` as-is — rejected: its `schema` arg
  implies the port does validation; the spec wants validation in the consumer so
  live and replay are rejected identically.
- A single reasoner with a "replay mode" flag — rejected: two classes keep the
  offline path free of any vendor import.

---

## R3. Capturing reasoning fixtures with provenance

**Decision**: A `RecordingReasoner(inner)` wrapper (same pattern as Spec 000's
`RecordingProvider`) writes `fixtures/reasoning/<seq>.json` with the context sent,
the raw response object, `recorded_at`, and the model id. Hand-authored reasoning
fixtures are prohibited; a provenance check test enforces `recorded_at` + `model`
on every file.

**Rationale**: Constitution Article VI — fixtures come from live runs. Determinism
for rehearsal (NFR-002-02) requires the fixtures to be real, ordered, and stable.

**Alternatives considered**:
- Commit a curated JSON by hand — rejected by the same rule that governs Spec
  000 fixtures.
- Record at the HTTP layer — rejected: wrong layer, breaks on an SDK bump.

---

## R4. Failure-halt and step-bound semantics on `Engine`

**Decision**: Additive changes to `engine.py`:
- `Engine.__init__(..., max_steps: int = int(os.environ.get("MAX_STEPS", 50)))`.
- `Run` / `Engine` gains `halted: bool` and `halt_reason: str | None`
  (`"step-failed"` | `"step-bound"`).
- `step()` after capturing evidence: if `not result.ok` → set halt state,
  record the failure on the checkpoint, return the checkpoint, do **not** advance
  (do not snapshot a failed state — already the case).
- `step()` / `next_step()` entry: if `self.halted` or
  `len(steps_in_branch) >= max_steps` → raise `BranchHalted` (or a no-op that
  records `"step-bound"`); never execute.
- Prior checkpoints are never mutated — `Run.add` only appends; halt sets flags,
  touches no existing node.

**Rationale**: FR-002-06 (halt, keep history), FR-002-07 (single bound). Keeping
it to flags + a guard clause means the run tree, `path_to`, `as_tree`,
`branch_from`, `promote` are untouched (Article V).

**Alternatives considered**:
- Raise on the failing step itself — rejected: the failing step's checkpoint and
  evidence must be recorded (FR-002-06), so the step completes, then the branch
  halts.
- A separate `StepRunner` class wrapping `Engine` — rejected: `Engine.step`
  already owns this responsibility; a wrapper duplicates head/handle bookkeeping.

---

## R5. Live-vs-fake path parity

**Decision**: The ordered actions for a step are fixed in `Engine.step()`:
`provider.run(handle, instruction)` → build `Checkpoint(evidence=...)` → if
`evidence.ok` then `provider.checkpoint(handle)` → `run.add`. Neither provider
branches this sequence. A parity test records the ordered `CallRecord.operation`
list (Spec 000 gives `provider.calls`) for a fixed script against `FakeProvider`
and asserts the sequence; the live contract test asserts the same sequence
against `DaytonaProvider`.

**Rationale**: NFR-002-01. The `CallRecord` list from Spec 000 is the observable
that makes "identical path" testable without mocking.

**Alternatives considered**:
- Assert on wall-clock or output equality — rejected: outputs differ live vs
  fake; the *path* is what must match.

---

## R6. Evidence over rationale

**Decision**: `Checkpoint.evidence: ExecResult | None` and
`Checkpoint.rationale: str` are already separate fields. Add a derived
`Checkpoint.outcome` property = `"ok"` if `evidence and evidence.ok` else
`"failed"` — computed only from `evidence`, never from `rationale`. `as_tree()`
already emits them as separate keys; keep that. A test drives a step where
`rationale` says "success" and the command exits non-zero and asserts
`outcome == "failed"`.

**Rationale**: FR-002-04 / FR-002-08, Constitution Article X.

---

## Open items carried to Phase 1

- Exact field lists / state machine → [data-model.md](data-model.md)
- Exact rejection rule table → [contracts/reasoning-port.md](contracts/reasoning-port.md)
- Halt / bound behaviour table + FR→test matrix → [contracts/step-evidence.md](contracts/step-evidence.md), [quickstart.md](quickstart.md)
