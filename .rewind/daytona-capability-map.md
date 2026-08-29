
## VERIFIED 12:2x — branching mechanism
- fork(): EXISTS but 422 "not supported for this sandbox" — container class. Not used.
- create_snapshot(name) on a live sandbox: WORKS, ~6.9s
- create(CreateSandboxFromSnapshotParams(snapshot=name)): WORKS, children carry parent state
- 3 branches from one snapshot: 6.8s total
- Concurrency ceiling: total CPU 10 (~10 sandboxes). MAX_BRANCHES=3
- Sandbox create rate limit: 600/min. Not a constraint.
- Workspace must be /home/daytona/... — /work is not writable
- API v0.207.0
