# Gates

One line per gate at the moment it passes (Constitution Article XIV).

| Gate | Time | Status | Notes |
|---|---|---|---|
| G1 — Scope | — | pending | specs 000 written (spec/plan/tasks); demo script not yet timed |
| G2 — Spine | — | partial | Spine proven earlier (`de8347b`). Spec 000 ports + fakes: `pytest -q` → 35 passed, 1 skipped offline. Live contract suite (`pytest tests/contract -m live`) not yet run — needs `DAYTONA_API_KEY` on the machine. |
| G3 — Freeze | — | pending | re-run `tests/contract` live; confirm capability map current; then no more edits to `capabilities.py` / `providers.py` |

## Spec 008 — Alternate Inference Endpoint  (Article VIII additive — deletable with zero impact)

- `reasoning.py`: `LiveReasoner(*, base_url, model, api_key)` (parameterised, no-arg
  unchanged); `RoutedReasoner` (alternate→primary, same-schema validation,
  `last_served_by`); `verdict_ids_from_bundle`; `critic_reasoner()` factory.
  `capabilities.ALT_WAIT = min(REWIND_ALT_WAIT, CRITIC_WAIT)`. `engine.py`: `served_by`
  (`alternate`/`primary`/`deterministic-fallback`) on `evaluate`'s result + the
  verdict record. `ui/console.html` verdict block shows *served by …*.
- Offline: `pytest tests/unit/test_alternate_endpoint.py -q` → 14 passed.
- **SC-008 verified — full suite unchanged**: `pytest -q` → **227 passed, 1 skipped,
  16 live-deselected** (213 from 000–007, none changed, + 14).
- **Article VIII assessment — pending**: `pytest tests/contract/test_alternate_endpoint_contract.py -m live`
  once, with `CRITIC_BASE_URL`/`CRITIC_MODEL` set to a provisioned endpoint. Green →
  allowed on a captured demo run; otherwise remove the config (record reads `primary`).

## Spec 007 — Demo Harness  (top of the pyramid — the scripted E2E)

- `src/rewind/harness.py` — `run_demo(provider, strategist, critic, *, budget,
  warm, fixture_out) -> DemoResult`; `STAGES`; pure `check_budget` /
  `check_no_leak` / `check_seed_reproduced` / `enough_fixtures`; `_prepare_runtime`
  (pre-warm before the timer).
- `demo.py` thinned to a front end: `FAKE=1` → `_SeedFake` + canned (offline,
  exit 0); default → `DaytonaProvider` + `ReplayReasoner` (named non-zero exit
  until `fixtures/reasoning/` is captured). `tools/capture_demo_fixtures.py` for
  the one-time capture.
- Offline: `pytest tests/unit/test_harness.py -q` → 20 passed.
- Full suite (000–006 + harness): **213 passed, 1 skipped, 14 live-deselected**.
- `FAKE=1 python demo.py` runs every stage and exits 0.
- **G3 evidence — pending**: `python demo.py` clean **twice** live + the failure
  spot check (`specs/007-demo-harness/checklists/rehearsal.md`). Needs
  `DAYTONA_API_KEY` + captured `fixtures/reasoning/`.

## Spec 005 — Critic Evaluation and Promotion  ✅ closes Constitution Article IX

- The loop is closed: propose (004) → execute (002) → **critic judges on the
  branches' own evidence → promotes the winner → releases the losers** → fan out
  again (FR-005-08). Stated in one sentence: *the critic judges the branches on
  their sandboxes' evidence and the winner becomes the run's next starting point.*
- `Engine.evaluate` / `judge_and_promote` / formalised `promote` / hardened
  `rank_by_evidence` (pure + total) / `Run.record_verdict` (write-once) /
  `reasoning.validate_verdict` / `capabilities.CRITIC_WAIT` / `Checkpoint.verdict`.
- Offline: `pytest tests/unit/test_critic.py -q` → 31 passed.
- Full suite (000–006): **193 passed, 1 skipped, 14 live-deselected**.
- `FAKE=1 python demo.py` runs the full loop end to end.
- Outstanding: `pytest tests/contract/test_critic_contract.py -m live` (needs
  `DAYTONA_API_KEY` + `LLM_API_KEY`) — provider op parity `branch×1` + round within
  `CRITIC_WAIT` budget.

## Spec 006 — Timeline Console

- `console_fixture()` builder added (`as_tree` + `live_sandboxes` + `session_elapsed`
  + `runtime_version` + `verdict` + branch `progress`); `demo.py` writes it to
  `fixtures/tree.json`. `ui/console.html` reworked for the 10 FRs (restore/fan-out
  request controls, per-branch state + elapsed, mono/face discipline, reduced-scale
  guards, lanes captioned by parent). Frozen at `.rewind/console-mockup.html`.
- Automated: `pytest tests/unit/test_console_fixture.py -q` → 9 passed (fixture shape only).
- **No automated UI-rendering tests (Constitution Article VI).** Sign-off is
  `specs/006-timeline-console/checklists/visual-acceptance.md` — a manual FR-by-FR
  pass, run at build and before the demo. **Status: pending a browser pass.**
- Full suite (000–004 + 006 fixture test): **162 passed, 1 skipped, 12 live-deselected**.

## Spec 004 — Branch Fan-Out

- Offline unit layer. `pytest tests/unit/test_fan_out.py -q` → 25 passed.
- Full suite (000–004): **153 passed, 1 skipped, 12 live-deselected**.
- `demo.py` fan-out beat shows derivation + 3 live sandbox ids + states, then rank → promote → restore.
- Reworked `Engine.branch_from` (concurrent execution, own snapshot per child, `try/finally`
  cleanup of every branch sandbox, live progress). `Engine.promote` re-derives the winner
  (provisional → spec 005).
- Outstanding: `pytest tests/contract/test_fan_out_contract.py -m live` (needs `DAYTONA_API_KEY`) —
  per-op count parity `branch×3, run×3, checkpoint×3, destroy×3` + wall-clock ≈ one branch.

## Spec 003 — Restore to Checkpoint

- Fully offline unit layer. `pytest tests/unit/test_restore.py -q` → 28 passed, sub-second.
- Full suite (000 + 001 + 002 + 003): **128 passed, 1 skipped, 10 live-deselected**.
- `demo.py` restore beat shows `verification: verified` + head moved + elapsed.
- Outstanding: `pytest tests/contract/test_restore_contract.py -m live` (needs `DAYTONA_API_KEY`) —
  ordered-call parity `["branch","run","run","destroy"]` + live restore under budget.

## Spec 001 — Run and Checkpoint Model

- Fully offline. `pytest tests/unit/test_run_tree.py -q` → 33 passed, sub-second.
- Full suite (000 + 001 + 002): **100 passed, 1 skipped, 8 live-deselected**.
- `check_integrity()` returns `[]` after failure + abandonment + shared-parent branch (SC-010).
- No outstanding live-key work — this feature has no external dependency.

## Spec 002 — Step Execution and Evidence

- Offline suite green: `test_reasoning.py` (schema + replay determinism + no-vendor-import),
  `test_stepping.py` (evidence capture, failure halt, step bound, evidence-over-rationale,
  offline loop). Full `pytest -q` → 67 passed, 1 skipped, 8 live-deselected.
- Outstanding before G2 fully ticked:
  1. Capture `fixtures/reasoning/*.json` from `RecordingReasoner(LiveReasoner())` (needs `LLM_*`).
  2. `pytest tests/contract/test_reasoning_contract.py -m live` green (needs `LLM_*` + `DAYTONA_API_KEY`).

## Spec 000 — Sandbox Capability Contract

- Offline suite green: base (`test_ports.py`), capability guard (`test_capabilities.py`),
  lifecycle (`test_lifecycle.py`), classification (`test_error_classification.py`).
- Outstanding before G2 can be fully ticked:
  1. Run `python tools/spine_test.py` with a live key → regenerates `.rewind/capability-map.toml`
     and confirms the 5 declared operations against the account.
  2. Capture `fixtures/daytona/*.json` from a live run (un-skips `test_fake_matches_recorded_result`).
  3. `pytest tests/contract -m live` green in < 30s.
