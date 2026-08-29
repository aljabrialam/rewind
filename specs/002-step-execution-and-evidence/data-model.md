# Phase 1 Data Model: Step Execution and Evidence

Concrete shapes for the entities in `spec.md` → Key Entities. Contract shapes,
not implementation. Existing types in `src/rewind/` reused where noted.

---

## 1. Instruction

The validated unit of work from the reasoning agent.

| Field | Type | Rule |
|---|---|---|
| `instruction` | string | Required. Non-empty after `strip()`. The command to run. |
| `rationale` | string | Required. The agent's stated reason. May be any non-`None` string; an empty string is a rejection (rationale is required by FR-002-01). |

Unknown keys in the source payload are ignored, not rejected. Produced only by
`validate(payload) -> Instruction`; a failure raises `SchemaError(ValueError)`.

---

## 2. Reasoning response (raw)

What a `ReasoningPort` returns before validation — an untyped `Mapping`. Never
trusted directly; always passed through `validate()`. A live response and a
fixture response are validated by the same rule.

---

## 3. Evidence

Reuses `ports.ExecResult`.

| Field | Type | Rule |
|---|---|---|
| `exit_code` | int | From the runtime. Non-zero ⇒ the step failed. |
| `stdout` | string | The runtime's returned command output. May be empty. Captured in full. |
| `elapsed` | float | Wall-clock seconds around the execution call. `> 0` for any step that ran. |
| `ok` | bool (derived) | `exit_code == 0`. |

Sourced only from `provider.run(...)`. Never constructed from a reasoning
response.

---

## 4. Rationale

A plain string field on the checkpoint (`Checkpoint.rationale`), carried from the
validated `Instruction`. Stored in a field distinct from `evidence`. Never read
when determining an outcome.

---

## 5. Step / Checkpoint additions

Reuses `ports.Checkpoint` (owned by Spec 001). This feature populates and adds:

| Field | Type | Rule |
|---|---|---|
| `instruction` | string | The executed command (existing). |
| `evidence` | ExecResult \| None | Attached after execution (existing; FR-002-05). `None` only for the synthetic `root`. |
| `rationale` | string | From the validated `Instruction` (existing field, now always populated for real steps). |
| `outcome` | `"ok"` \| `"failed"` (derived) | **NEW** — `"ok"` iff `evidence and evidence.ok`; computed from `evidence` only (FR-002-04). |
| `halt_reason` | `"step-failed"` \| `"step-bound"` \| None | **NEW** — set on the checkpoint whose completion halted the branch (FR-002-06 / FR-002-07). |
| `index` | int | Ordinal in the run (existing). |

**Invariant**: attaching evidence and setting `halt_reason` only ever writes to
the *new* checkpoint for the current step. No prior checkpoint is read-modified
(FR-002-06).

---

## 6. Branch state (on `Run` / `Engine`)

| Field | Type | Rule |
|---|---|---|
| `halted` | bool | Set true when a step fails or the step bound is reached. |
| `halt_reason` | `"step-failed"` \| `"step-bound"` \| None | Why the branch stopped. `"step-failed"` wins if both conditions coincide (Edge Cases). |
| `max_steps` | int | The single declared step bound (default 50, `MAX_STEPS` override). Read in one place. |

### Branch state machine

| State | Entry | Exit |
|---|---|---|
| `advancing` | run started (`start()`) | → `halted("step-failed")` when a step's `evidence.exit_code != 0`; → `halted("step-bound")` when the branch already holds `max_steps` steps and another is requested |
| `halted` | a halt condition fired | terminal for this feature — advancing further raises `BranchHalted`; branching from an earlier checkpoint is Spec 004's concern |

---

## 7. BranchHaltReason

Enum-like string: `"step-failed"` | `"step-bound"`. Recorded both on the branch
state and on the checkpoint that triggered it (for `step-failed`) or on the
branch state alone (for `step-bound`, where no new checkpoint is created).

---

## 8. RecordedReasoning (fixture)

One file per reasoning call under `fixtures/reasoning/`.

| Field | Type | Rule |
|---|---|---|
| `context` | string | What was sent to the agent. |
| `response` | object | The raw response object (pre-validation). |
| `recorded_at` | ISO-8601 string | Provenance — required. |
| `model` | string | The model id that produced it — required. |
| `seq` | int | Order within the recorded run; `ReplayReasoner` serves ascending. |

Hand-authored fixtures are prohibited (Constitution Article VI); a test asserts
`recorded_at` and `model` on every file.

---

## Type glossary

| Name | Definition |
|---|---|
| `Instruction` | frozen dataclass `{instruction: str, rationale: str}` |
| `SchemaError` | `ValueError` subclass raised by `validate()` |
| `BranchHalted` | raised when a step is requested on a halted branch |
| `ExecResult` | existing `ports.ExecResult` |
| `Checkpoint` | existing `ports.Checkpoint` + `outcome`, `halt_reason` |
| `ReasoningPort` | `Protocol` with `next_instruction(context: str) -> Mapping` |
