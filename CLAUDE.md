<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/008-alternate-inference-endpoint/plan.md`

Active feature: **008 — Alternate Inference Endpoint** (Article VIII additive;
deletable with zero impact). `reasoning.py`: `LiveReasoner(*, base_url, model,
api_key)` params; `RoutedReasoner(alternate, primary, *, bound, validate)` — a
ReasoningPort, alternate→primary fallback, `last_served_by`;
`verdict_ids_from_bundle`; `critic_reasoner()` factory (routed iff CRITIC_BASE_URL
+ CRITIC_MODEL set). `capabilities.ALT_WAIT = min(REWIND_ALT_WAIT, CRITIC_WAIT)`.
`engine.py` ~4 lines: `served_by` (alternate/primary/deterministic-fallback) into
`evaluate`'s result + the verdict record. Console verdict block shows it. Nothing
in 000–007 changes when CRITIC_BASE_URL is unset.

--- prior ---

Active feature: **007 — Demo Harness** (top of the pyramid; the scripted E2E).
New `src/rewind/harness.py`: `run_demo(provider, strategist, critic, *, budget,
warm, fixture_out) -> DemoResult` (provider + reasoner seam so the checks are
testable offline), `STAGES`, pure `check_budget` / `check_no_leak` /
`check_seed_reproduced` / `enough_fixtures`, `_prepare_runtime` (pre-warm before
the timer). `demo.py` becomes a thin front end: live `DaytonaProvider` +
`ReplayReasoner` by default (fail-clear non-zero if fixtures missing), canned +
`FakeProvider` under `FAKE=1`; `SystemExit(0 if result.ok else 1)`.
`tools/capture_demo_fixtures.py` for the one-time reasoning-fixture capture.
Implemented: 000–006. **All seven specs.** Under `specs/`.

Stack: Python 3.11+, `pytest`. Single-project layout under `src/rewind/`.
- Spec 000 (done): `capabilities.py` import-time guard, `providers.py` (sole
  `daytona` importer), `recording.py` live fixture capture.
- Spec 002 (in progress): new `reasoning.py` = the reasoning seam (Instruction
  schema + `validate()`, `ReasoningPort`, `ReplayReasoner`, `LiveReasoner` sole
  reasoning-vendor importer). Additive edits to `engine.py` (step bound, failure
  halt, `next_step(reasoner)`) and `ports.py` (`ReasoningPort` replaces the
  `LLMClient` stub; `Checkpoint.outcome` / `halt_reason`).

Test convention: `.venv/bin/python -m pytest`; live tests are `@pytest.mark.live`,
skipped without credentials. No Docker.
<!-- SPECKIT END -->
