# Contract: Restore to Checkpoint

`Engine.restore(checkpoint_id, verify: RestoreCheck | None = None) -> RestoreResult`.
Re-materialise a sandbox from a checkpoint's captured state, prove it, move the
head, keep the tail, release the old sandbox, and report the elapsed time.

Traces: FR-003-01 … FR-003-07, NFR-003-01 … NFR-003-03.

---

## Ordered port calls (identical for both providers — NFR-003-03)

For a successful restore with one `before` and one `after` check:

```
provider.branch(cp.snapshot, 1)     # create one sandbox from the checkpoint's state
provider.run(new, before_cmd)       # verification: state written before is present
provider.run(new, after_cmd)        # verification: state written after is absent
provider.destroy(old_head_handle)   # release the previous head's sandbox (if unreferenced)
```

Observable: `[c.operation for c in provider.calls]` over the restore ==
`["branch", "run", "run", "destroy"]`. More/less checks change only the number of
`run` entries. A refusal makes **zero** port calls.

---

## Verification rules (FR-003-02, SC-009, NFR-003-01)

| `verify` | `before` checks | `after` checks | resulting `status` |
|---|---|---|---|
| `None` | — | — | `not-checked` |
| given, both lists empty | 0 | 0 | `not-checked` |
| given | ≥1, all pass | ≥1, all pass | `verified` |
| given | any present-check fails | — | `not-verified` |
| given | — | any absent-check fails (marker still there) | `not-verified` |
| given | ≥1 pass | 0 | `not-verified` (incomplete — cannot confirm "after absent") |
| given | 0 | ≥1 pass | `not-verified` (incomplete — cannot confirm "before present") |

- A `before` check passes iff its `marker` is a substring of the command's
  output.
- An `after` check passes iff its `marker` is **not** a substring of the
  command's output.
- Each check records `{command, marker, observed, passed}`; `observed` is the
  output (truncated for the render).
- A failing check does **not** abort the restore — the head still moves; the
  result reports `status = "not-verified"`. (The developer sees a restore
  happened but the proof did not hold.)
- The system MUST NEVER set `status = "verified"` without ≥1 passing `before` and
  ≥1 passing `after`.

---

## Refusal table (FR-003-05)

| Condition | `error` | port calls | head | `RestoreResult` |
|---|---|---|---|---|
| id not in `run.checkpoints` | `"unknown"` | none | unchanged | `sandbox_id=None`, `head_moved=False`, `elapsed_seconds` set, `verification.status="not-checked"` |
| checkpoint `state == "released"` | `"released"` | none | unchanged | as above |
| checkpoint `state == "unreachable"` | `"unreachable"` | none | unchanged | as above |
| checkpoint `snapshot is None` | `"unreachable"` | none | unchanged | as above |
| `provider.branch(...)` raises | classified message from the error | `branch` attempted; port already destroyed any partial | unchanged | `sandbox_id=None`, `head_moved=False` |

Every refusal still reports `elapsed_seconds` (FR-003-06).

---

## Success obligations

| # | Obligation | Trace |
|---|---|---|
| C1 | Produce exactly one sandbox, via `provider.branch(cp.snapshot, 1)`. | FR-003-01 |
| C2 | Run the supplied `RestoreCheck` probes in that sandbox; build the `RestoreVerification`. | FR-003-02 |
| C3 | `run.set_head(checkpoint_id)` (Spec 001 head mechanism); `self.live[checkpoint_id] = new_handle`; `head_moved = True`. | FR-003-03 |
| C4 | Do not remove or mutate any entry in `run.order` / `run.checkpoints` beyond `head`; later checkpoints keep their `snapshot`, `state`, `instruction`. `run.check_integrity() == []`. | FR-003-04, SC-003 |
| C5 | Pop `old_head` from `self.live`; if its handle id is not shared by any remaining `self.live` value, `provider.destroy` it. Never touch any checkpoint's `snapshot`. | FR-003-07, SC-006 |
| C6 | Net live sandbox count after a successful restore is `before + 1` at most. | SC-006 |
| C7 | Measure `elapsed_seconds` around the whole attempt (produce + verify); include it on every path. | FR-003-06, SC-005 |
| C8 | `RestoreResult.as_dict()` returns a plain dict (verification detail included) suitable for the console / a fixture. | NFR-003-01 |
| C9 | The offline path (`FakeProvider`) completes effectively instantly with no network and no credentials. | NFR-003-02, NFR-003-03, SC-008 |

---

## Edge behaviours

| Edge case | Behaviour |
|---|---|
| restore to the current head | still produces a fresh sandbox + reports elapsed; `set_head` is a no-op move; old head's sandbox released if unreferenced; `head_moved` may be `False` (it was already there) |
| restore to the synthetic `root` | allowed iff `root` has a `snapshot`; later checkpoints preserved |
| `verify` supplied but a probe command errors in the sandbox | that check `passed = False`, `observed` = the error output; overall `not-verified` |
| two restores back to back | each is a full attempt in sequence; parallel restore is out of scope |
