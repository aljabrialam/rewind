# Restore to Checkpoint (spec 003)

Return the run to the exact runtime state of any earlier checkpoint — resume from
before a mistake instead of restarting. Full spec:
[`specs/003-restore-to-checkpoint/`](../specs/003-restore-to-checkpoint/).

## The operation

`Engine.restore(checkpoint_id, verify: RestoreCheck | None = None) -> RestoreResult`

| Step | What it does | FR |
|---|---|---|
| 1 | Refuse (returned, not raised) if the id is unknown / `released` / `unreachable` / has no snapshot — naming which | FR-003-05 |
| 2 | `provider.branch(cp.snapshot, 1)` — one sandbox re-materialised from the checkpoint's captured state | FR-003-01 |
| 3 | Run the caller's `RestoreCheck` probes in it — `before` markers must be present, `after` markers must be absent | FR-003-02 |
| 4 | `run.set_head(checkpoint_id)` — the run head moves (Spec 001 mechanism) | FR-003-03 |
| 5 | Every later checkpoint stays in the tree, snapshot and all — nothing deleted | FR-003-04 |
| 6 | Release any working sandbox now off the head's lineage (the old head's), snapshots untouched | FR-003-07 |
| 7 | `elapsed_seconds` reported on every path | FR-003-06 |

## Result shape (renderable — NFR-003-01)

```python
RestoreResult(
    checkpoint_id, sandbox_id, elapsed_seconds,
    verification=RestoreVerification(
        status="verified" | "not-verified" | "not-checked",
        before=[{command, marker, observed, passed}, ...],
        after=[...]),
    error=None | "unknown" | "released" | "unreachable" | "<runtime msg>",
    head_moved=bool,
).as_dict()
```

`status == "verified"` **only** when there is ≥1 passing `before` check **and**
≥1 passing `after` check (FR-003-02 / SC-009). A failing probe never aborts the
restore — the head still moves and the result says `not-verified`.

## Running

```bash
pytest tests/unit/test_restore.py -q                       # 28 offline tests, sub-second
pytest tests/contract/test_restore_contract.py -m live -q  # ordered-call parity + budget (needs DAYTONA_API_KEY)
FAKE=1 python demo.py                                       # includes a "restore to checkpoint" beat
```
