# Phase 0 Research: Branch Fan-Out

Spec 004 carries no `[NEEDS CLARIFICATION]`. Technical decisions for design.
Evidence: `src/rewind/engine.py` (`branch_from`, `promote`, `Run.add`),
`src/rewind/providers.py` (`branch(snapshot, n)` uses `ThreadPoolExecutor`;
`BoundedSemaphore` ceiling; `classify`), `src/rewind/capabilities.py`
(`VERIFIED_OPS`, `MAX_BRANCHES`), `src/rewind/reasoning.py` (`ReasoningPort`,
`validate`), `.rewind/capability-map.toml`, `demo.py`.

---

## R1. Concurrency mechanism and `run.add` thread-safety (FR-004-04)

**Decision**: create all N branch sandboxes first (`provider.branch(cp.snapshot,
N)` — already concurrent creation), then run the N strategies concurrently in a
`ThreadPoolExecutor(max_workers=N)`, each worker calling `provider.run(handle,
strategy)` and catching its own exceptions. **`Run.add` is called serially**,
after the parallel section, in strategy order — so no lock is needed on the tree.
The child `Checkpoint` objects are built inside the workers (pure), collected,
then added.

**Rationale**: FR-004-04 wants the *executions* to overlap; creation is already
parallel. Keeping tree mutation single-threaded avoids a lock on `Run` (which
Spec 001 defined as pure in-memory) while still meeting the concurrency
requirement — `provider.run` is where the wall-clock goes.

**Alternatives considered**:
- Lock `Run.add` and add from workers — rejected: adds a lock to the Spec 001
  pure model for no wall-clock benefit.
- `asyncio` — rejected: `providers.py` and the rest of `engine.py` are
  thread-based; introducing an event loop is a refactor (Article V).

---

## R2. Derivation selection (FR-004-03, SC-009)

**Decision**: `Engine._select_derivation() -> str`. An ordered preference list of
derivation names, fastest first: `("fork", "branch")`. Return the first whose
backing operation is in `capabilities.VERIFIED_OPS`. Today that is `"branch"`
(snapshot-based create-from-snapshot); `"fork"` is not in the map so it is
skipped. The chosen name is recorded on the `FanOutResult.derivation` and on
`self._last_derivation`.

**Rationale**: FR-004-03 — fastest the map declares, fall back to the next. The
selector reads only the verified map (Article IV), so a map that later adds a
`fork` op changes behaviour deliberately. `demo.py`'s README note already
anticipates "enabling fork later changes one method body".

**Alternatives considered**:
- Hard-code `"branch"` — rejected: FR-004-03 requires the selection + record + a
  fallback path.
- A capability-map field naming the fastest derivation — rejected: over-design
  for two options; the preference list in code is auditable and testable.

---

## R3. Progress report shape and thread-safety (FR-004-07, NFR-004-04)

**Decision**: `BranchProgress` per branch: `{checkpoint_id, sandbox_id, state}`
where `state ∈ {"creating", "running", "done", "failed"}`. The fan-out holds a
`list[BranchProgress]` guarded by a `threading.Lock`; each worker updates its own
entry's `state` and calls the optional `observer(list_of_progress_dicts)` after
each transition. The final list is returned on `FanOutResult.progress`. The child
checkpoints are also `run.add`ed with a live `state`, so `run.as_tree()` reflects
the branches as they land.

**Rationale**: FR-004-07 + NFR-004-04 want structured, renderable, live per-branch
status with the runtime's own id. A small locked list + a callback is the minimum
that is thread-safe and testable (a test collects the observer calls and asserts
the `creating → running → done/failed` progression).

---

## R4. Per-branch failure isolation (FR-004-08, SC-005)

**Decision**: each worker wraps `provider.run` in try/except. On any exception
(`RuntimeCallError` or otherwise) the branch's `Checkpoint` gets
`evidence = ExecResult(exit_code=1, stdout=<classified message>)`,
`terminal = "failed"`, progress `state = "failed"`. A non-zero exit (no
exception) is likewise `terminal = "failed"`. The fan-out never re-raises a
branch failure; it returns every child. If sandbox *creation* for a branch failed
(the `provider.branch` call returned fewer handles or raised), that branch is
recorded as a child with no sandbox, `state = "failed"`, reason attached.

**Rationale**: FR-004-08 — a branch failure is a result. SC-005 — the other
branches' evidence still comes back.

---

## R5. Branch-sandbox cleanup on all paths (FR-004-10, SC-006)

**Decision**: `branch_from` collects every handle it created into a list and, in
a `finally`, calls `provider.destroy` on each — so cleanup runs on the success
path, the per-branch-failure path, and the path where the whole operation raises.
Child checkpoints keep their own `snapshot` (taken before the handle is
destroyed), so nothing about a child's captured state is lost. The run head is
never moved. Net live sandbox count returns to its pre-fan-out value (SC-006).

**Consequence for `promote` (Spec 005)**: since branch sandboxes are now
destroyed, `Engine.promote(winner, losers)` can no longer keep the winner's live
handle. It is updated to re-derive the winner from `winner_cp.snapshot`
(`provider.branch(snapshot, 1)[0]`) and register that as the head handle; losers
are marked `released`/`abandoned` with no handle to destroy. **Provisional** —
Spec 005 will formalise promotion; this keeps `demo.py` working.

**Rationale**: FR-004-10 is unconditional ("in both success and failure paths").
A `finally` over a handle list is the standard way. Each branch child getting its
own snapshot (spec Assumptions) is what makes destroy-and-still-promotable true.

---

## R6. Strategies from the reasoning agent (FR-004-01)

**Decision**: `Engine.fan_out(step_id, reasoner, n, context="", observer=None)`:
call `reasoner.next_instruction(context)` `n` times, `validate()` each (Spec 002
schema — `SchemaError` propagates, nothing is created), dedupe by `instruction`
text, cap the count at `min(n, MAX_BRANCHES)` and at the number of distinct
strategies received. Delegate to `branch_from(step_id, [i.instruction for i in
strategies], rationales=[i.rationale ...], observer=observer)`. `FanOutResult.ran`
reports how many actually ran.

**Rationale**: FR-004-01 + the edge cases (fewer/duplicate strategies → run what
was received, report the count; over-max → cap and report).

**Alternatives considered**:
- One reasoner call returning a list of N strategies — rejected: the Spec 002
  port contract is one structured instruction per call; N calls keep the schema
  and the fixture-replay model unchanged.

---

## R7. Ordered-call parity observable (NFR-004-03)

**Decision**: for a fan-out of N branches with no failures, the multiset of
`provider.calls` operations is: `branch` recorded once per child by both providers (N), N × `run`
(the strategy executions, concurrent), N × `checkpoint` (each branch's own
snapshot), N × `destroy` (cleanup). Because execution is concurrent the exact
interleaving of `run`/`checkpoint`/`destroy` is not fixed, so the parity test
asserts the **counts per operation**, not the sequence: `branch×N, run×N,
checkpoint×N, destroy×N`. A unit test asserts this against `FakeProvider`; the
live contract test asserts the same counts against `DaytonaProvider` and that
total wall-clock ≈ one branch.

---

## Open items carried to Phase 1

- Exact dataclass fields + branch lifecycle states → [data-model.md](data-model.md)
- Derivation rule + concurrency/cleanup/progress obligations + call counts → [contracts/fan-out.md](contracts/fan-out.md)
- FR→test matrix → [quickstart.md](quickstart.md)
