# Contract: Step Execution and Evidence

What one step does, what it captures, how it attaches to a checkpoint, and how the
branch halts. Implemented as additive changes to `src/rewind/engine.py`
(`Engine.step`, `Engine.next_step`, `Engine.__init__`).

Traces: FR-002-02, FR-002-03, FR-002-04, FR-002-05, FR-002-06, FR-002-07,
NFR-002-01.

---

## The ordered actions of a step (fixed for both providers)

1. `handle = self.live[self.run.head]` — the current branch head's sandbox
2. `evidence = provider.run(handle, instruction)` — the **only** source of truth
3. build `Checkpoint(instruction=instruction, rationale=rationale, evidence=evidence, parent_id=head, sandbox_id=handle.id)`
4. if `evidence.ok`: `snapshot = provider.checkpoint(handle)` and attach it
   (a failed state is never snapshotted)
5. `run.add(checkpoint)` — append only; no prior node is modified
6. if `not evidence.ok`: set `checkpoint.halt_reason = "step-failed"`, set branch
   `halted = True`, `halt_reason = "step-failed"`

Neither `FakeProvider` nor `DaytonaProvider` alters this sequence (NFR-002-01).
The observable is the ordered `provider.calls` (`CallRecord.operation`) list from
Spec 000: `["run"]` for a failed step, `["run", "checkpoint"]` for a good step.

---

## Evidence (FR-002-03, FR-002-05)

| Captured | From | Attached to |
|---|---|---|
| exit status | `provider.run(...).exit_code` | `checkpoint.evidence.exit_code` |
| standard output | `provider.run(...).stdout` (full, may be empty) | `checkpoint.evidence.stdout` |
| elapsed time | wall-clock around the `run` call, `> 0` | `checkpoint.evidence.elapsed` |

A step that exits zero with no output records `exit_code=0, stdout="",
elapsed>0` — not a missing-evidence marker (SC-001, spec US1 §2).

---

## Evidence over rationale (FR-002-04, FR-002-08)

- `Checkpoint.outcome` (derived) = `"ok"` iff `evidence and evidence.ok`, else
  `"failed"`. Computed from `evidence` only.
- `Checkpoint.rationale` is stored verbatim from the validated `Instruction`, in
  its own field, and is **never** read by `outcome`, by the halt logic, or by
  any decision in this feature.
- A step whose `rationale` claims success but whose `exit_code != 0` has
  `outcome == "failed"` and halts the branch (spec US4 §2, SC-004).

---

## Failure halt (FR-002-06)

| Condition | Effect |
|---|---|
| `evidence.exit_code != 0` | the failing step's checkpoint is still created and still carries its evidence; `checkpoint.halt_reason = "step-failed"`; branch `halted = True`; the branch advances no further |
| any checkpoint created before the failing step | untouched — same `evidence`, same `snapshot`, same position (SC-003) |
| a further `step()` / `next_step()` call on the halted branch | raises `BranchHalted`; no `provider.run` occurs |

---

## Step bound (FR-002-07)

| Condition | Effect |
|---|---|
| `Engine(max_steps=N)` | `N` is the single declared bound; default `int(os.environ.get("MAX_STEPS", 50))`; read in exactly one place |
| branch holds `< N` steps, a step is requested | it runs; branch now holds one more |
| branch holds `N` steps, a step is requested | no execution; branch `halted = True`, `halt_reason = "step-bound"`; a `BranchHalted` is raised (or the call is a recorded no-op) |
| failure and bound coincide | recorded reason is `"step-failed"` (the more specific cause — spec Edge Cases) |

---

## Entry point (FR-002-01 + FR-002-02 wiring)

`Engine.next_step(reasoner: ReasoningPort, context: str = "") -> Checkpoint`:

1. if branch `halted` or at bound → raise `BranchHalted` (no reasoner call)
2. `raw = reasoner.next_instruction(context)`
3. `instr = validate(raw)` — `SchemaError` propagates, nothing executes, no checkpoint
4. `return self.step(instr.instruction, instr.rationale)`

The raw `step(instruction, rationale)` stays public for tests and for `demo.py`.
