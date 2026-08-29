# Step Execution and Evidence (spec 002)

Execute each agent step inside a sandbox and capture what actually happened, so
later decisions rest on observed results, not the model's account of them. Full
spec: [`specs/002-step-execution-and-evidence/`](../specs/002-step-execution-and-evidence/).

## The pieces

| File | Role |
|---|---|
| `src/rewind/reasoning.py` | The reasoning seam. `Instruction` + `validate()` (the one schema gate), `ReasoningPort`, `ReplayReasoner` (fixtures, offline), `RecordingReasoner` (provenance-stamped capture), `LiveReasoner` (the **only** module importing a reasoning vendor). |
| `src/rewind/ports.py` | `ReasoningPort` protocol; `Checkpoint.halt_reason`; `Checkpoint.outcome` — derived from `evidence` only, never `rationale`. |
| `src/rewind/engine.py` | `Engine.next_step(reasoner)` — pull → `validate()` → `step()`. `step()` captures exit/stdout/elapsed, attaches to the checkpoint, and halts the branch on a non-zero exit. `Engine(max_steps=50)` is the single step bound; `BranchHalted` is raised on a halted or maxed-out branch. |
| `fixtures/reasoning/*.json` | Recorded reasoning responses (`recorded_at` + `model`). Hand-authored fixtures are prohibited. |

## Guarantees

- **Structured or rejected** — a reasoning response that is not `{instruction: non-empty str, rationale: non-empty str}` raises `SchemaError`; nothing runs, no checkpoint (FR-002-01).
- **Evidence is the exit code / stdout / elapsed captured from the runtime** and nothing else (FR-002-03/04). `outcome` is computed from `evidence`; `rationale` is stored in its own field and never read by a decision (FR-002-08).
- **A failing step halts the branch** and keeps every prior checkpoint byte-identical (FR-002-06).
- **One declared step bound** halts the branch the same controlled way (FR-002-07).
- **Same path live or fake** — `run` then `checkpoint` for a good step, `run` only for a failed one (NFR-002-01); the full loop runs offline with `FakeProvider` + `ReplayReasoner` (NFR-002-02/03).

## Running

```bash
pytest tests/unit/test_stepping.py tests/unit/test_reasoning.py -q   # offline
pytest tests/contract/test_reasoning_contract.py -m live -q          # live drift (needs LLM_* / DAYTONA_API_KEY)
FAKE=1 python demo.py                                                # scripted path, offline
```
