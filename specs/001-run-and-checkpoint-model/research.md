# Phase 0 Research: Run and Checkpoint Model

Spec 001 carries no `[NEEDS CLARIFICATION]`. This records the technical decisions
for design. Evidence: `src/rewind/engine.py` (`Run`, `Checkpoint` via `ports.py`,
`add`, `path_to`, `as_tree`, `Engine.promote`, `Engine.step`),
`src/rewind/ports.py` (`Checkpoint` dataclass, `outcome` property from Spec 002),
`fixtures/tree.json`, `ui/console.html` / `.rewind/console.html`.

---

## R1. Per-checkpoint creation time (FR-001-06)

**Decision**: `Checkpoint.created_at: str` — ISO-8601, `default_factory` of
`datetime.now(timezone.utc).isoformat()`. Additive field on the existing
`ports.Checkpoint` dataclass. Used for display and as a tie-break for ordering;
never an identity or a correctness input (spec Assumptions).

**Rationale**: FR-001-06 explicitly requires "the time it was created" per
checkpoint. String ISO form keeps `as_tree()` JSON-serialisable with no encoder.

**Alternatives considered**:
- `float` epoch — rejected: `as_tree` feeds a JSON file the console reads; a
  human-readable string is friendlier and still sorts.
- Deriving order from `created_at` — rejected: `Run.order` already holds
  insertion order; `NFR-001-03` forbids leaning on timestamp resolution.

---

## R2. Branch terminal outcome (FR-001-09)

**Decision**: `Checkpoint.terminal: str | None` on the tip checkpoint of a
branch, one of `"succeeded" | "failed" | "abandoned"`, `None` while advancing.
Set by:
- `Engine.step` (Spec 002): on a non-zero exit, the failing checkpoint gets
  `terminal = "failed"` (alongside the existing `halt_reason`).
- `Engine.promote` (Spec 005, already present): each loser checkpoint gets
  `terminal = "abandoned"` (alongside the existing `state = "released"`).
- A caller that finishes a branch cleanly calls `Run.mark_terminal(tip,
  "succeeded")`.

`Run.branch_outcome(step_id) -> str | None` returns that checkpoint's `terminal`.
`Run.mark_terminal(step_id, outcome)` validates the enum and sets it.

**Rationale**: FR-001-09 wants the outcome readable "as a property of the branch
without inspecting individual steps" — a single field on the tip is exactly that.
Keeping `halt_reason` (Spec 002's finer cause) and `terminal` (Spec 001's coarse
outcome) as separate fields avoids overloading one.

**Alternatives considered**:
- Derive the outcome by walking the branch each call — rejected: the FR says
  "without inspecting individual steps".
- A separate `Branch` object — rejected: there is no branch identity in the model
  beyond "the checkpoint at the tip"; a field on that checkpoint is the minimal
  representation.

---

## R3. Restorability and head validation (FR-001-08)

**Decision**:
- `Run.is_restorable(step_id) -> bool` = the checkpoint exists **and**
  `state == "live"` **and** `snapshot is not None` (it has captured runtime
  state).
- `Run.restore_targets() -> list[str]` = ids in `order` that are restorable.
- `Run.set_head(step_id)` = refuse (`ValueError`) if the target is unknown or not
  restorable; otherwise set `self.head`. Head-*moving* policy still lives in
  other features; head *validity* lives here.

`Engine.promote` continues to set losers `state = "released"`; those then fail
`is_restorable` and never appear in `restore_targets()`.

**Rationale**: FR-001-08 — "never present a released checkpoint as restorable"
and (folded edge case) "a released checkpoint is not a valid head target". A
predicate plus a guarded setter covers both.

**Alternatives considered**:
- Let callers check `state` themselves — rejected: three call sites already do it
  three slightly different ways; one predicate removes the drift.

---

## R4. Structural-integrity check (NFR-001-02, SC-010)

**Decision**: `Run.check_integrity() -> list[str]` — returns a list of problem
strings, empty when the tree is sound. Rules:
1. exactly one `head`, and it is in `checkpoints`;
2. exactly one root (`parent_id is None`), at `index 0`;
3. every non-root `parent_id` resolves to a known checkpoint;
4. every id in every `children` list resolves;
5. parent/child links agree (if B lists A as parent, A lists B as child);
6. every checkpoint is reachable from the root by walking `children`;
7. no cycles.

**Rationale**: NFR-001-02 and SC-010 want a single assertion the tests can run
after a messy sequence (failure + abandonment + shared-parent branch).

---

## R5. `as_tree()` field additions (FR-001-07) and the console

**Decision**: add `created_at`, `outcome` (from `Checkpoint.outcome`),
`terminal`, and `snapshot` to each node dict in `as_tree()`. Keep the existing
`id`, `index`, `instruction`, `parent`, `sandbox`, `state`, `exit_code`,
`stdout`, `rationale`, `children`. `stdout` stays truncated at 400 chars for the
render (display concern, not evidence loss — full evidence is on the checkpoint).

**Rationale**: FR-001-07 lists the fields the renderable form must carry. The
console reads `fixtures/tree.json`; adding keys is backward-compatible (a
renderer ignores unknown keys). `demo.py` writes `fixtures/tree.json` from
`as_tree()`, so the new keys flow through automatically.

**Alternatives considered**:
- A second "detailed" form — rejected: FR-001-07 wants *one* form renderable
  without further computation.

---

## Open items carried to Phase 1

- Exact field list + state machine → [data-model.md](data-model.md)
- Operation pre/postconditions + invariants → [contracts/run-tree.md](contracts/run-tree.md)
- FR→test matrix → [quickstart.md](quickstart.md)
