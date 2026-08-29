# Contract: Reasoning Port

The single interface through which the system asks a reasoning agent for the next
instruction (`src/rewind/reasoning.py`). Mirrors the Spec 000 sandbox seam: one
interface, a live implementation and a fixture-replay implementation, and no
feature code imports a reasoning vendor directly.

Traces: FR-002-01, FR-002-08, NFR-002-01, NFR-002-02, NFR-002-03.

---

## Interface

```
class ReasoningPort(Protocol):
    def next_instruction(self, context: str) -> Mapping: ...
```

Returns a raw mapping (the model's JSON object). It is **not** validated by the
port — the consumer validates, so a live response and a fixture response are
accepted or rejected by the identical rule.

| Implementation | Module | Notes |
|---|---|---|
| `LiveReasoner` | `reasoning.py` | The only module that imports the reasoning-vendor SDK. Calls an OpenAI-compatible chat completion (`LLM_BASE_URL` / `LLM_MODEL`), parses the JSON object, returns it raw. |
| `ReplayReasoner(fixtures_dir)` | `reasoning.py` | Serves `fixtures/reasoning/*.json` in ascending `seq`. Raises `LookupError` when exhausted. No network, no credentials. |
| `RecordingReasoner(inner)` | `reasoning.py` | Wraps a `ReasoningPort`, delegates, writes a provenance-stamped fixture per call. The only way a fixture is produced. |

---

## The `Instruction` schema

`validate(payload: Mapping) -> Instruction` is the gate.

| Rule | Pass | Reject (`SchemaError`) |
|---|---|---|
| `instruction` key present | `{"instruction": "...", ...}` | key absent |
| `instruction` is a string | `"echo hi"` | `42`, `["echo"]`, `None` |
| `instruction` non-empty after strip | `"echo hi"` | `""`, `"   "`, `"\n"` |
| `rationale` key present | `{"rationale": "..."}` | key absent |
| `rationale` is a string | `"because the test needs a fixture"` | `null`, `12` |
| `rationale` non-empty | `"..."` | `""` |
| unknown keys | ignored | — (never a rejection) |

`SchemaError` is a subclass of `ValueError`. On rejection the caller executes
nothing and the run tree gains no checkpoint for that step (FR-002-01, SC-002).

---

## Obligations

| # | Obligation | Trace |
|---|---|---|
| C1 | The consumer (`Engine.next_step`) MUST pass every response — live or replayed — through `validate()` before any execution. | FR-002-01 |
| C2 | A rejected response MUST NOT cause a `provider.run`, a `provider.checkpoint`, or a `run.add`. | FR-002-01, SC-002 |
| C3 | The validated `rationale` MUST be carried to `Checkpoint.rationale`, a field distinct from `Checkpoint.evidence`. | FR-002-08 |
| C4 | `ReplayReasoner` MUST return the same responses in the same order across repeated runs from the same fixtures directory. | NFR-002-02, SC-007 |
| C5 | `ReplayReasoner` and `RecordingReasoner`'s replay path MUST require no network and no credentials. | NFR-002-03, SC-008 |
| C6 | No module other than `reasoning.py` may import the reasoning-vendor SDK (AST-scan test). | Constitution Art. IV |
| C7 | Every file in `fixtures/reasoning/` MUST carry `recorded_at` and `model`; hand-authored fixtures are prohibited. | Constitution Art. VI |
| C8 | When the reasoning agent is unreachable or returns nothing, `next_instruction` raises; the caller executes nothing and creates no checkpoint. | spec Edge Cases |
