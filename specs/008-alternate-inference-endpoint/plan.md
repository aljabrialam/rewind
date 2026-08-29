# Implementation Plan: Alternate Inference Endpoint

**Branch**: `main` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Feature Directory**: `specs/008-alternate-inference-endpoint/`

**Input**: Feature specification from `specs/008-alternate-inference-endpoint/`

## Summary

Route the critic reasoning role to a self-hosted alternate endpoint by
configuration (`CRITIC_BASE_URL` / `CRITIC_MODEL`), through the **same** reasoning
port (Spec 002) and the **same** verdict schema (Spec 005), with automatic
fallback: alternate → primary → deterministic exit-status ranking. Record on
every verdict which provider produced it — `alternate` / `primary` /
`deterministic-fallback` — and show it on the console (Spec 006). Bound the wait
on the alternate to no more than the critic wait bound so it cannot overrun the
demonstration budget (Spec 007). When the configuration is unset or incomplete,
the alternate is absent and the whole system runs byte-for-byte as it does today
(NFR-008-03 / SC-007/008). Article VIII: additive, background-provisioned,
assessed once by a contract test, never on the critical path, and depended on by
nothing.

Technical approach: almost all of it lives in `reasoning.py` — a `RoutedReasoner`
that *is* a `ReasoningPort` (tries the alternate within `ALT_WAIT`, validates its
response with the same rule, falls back to the primary, exposes
`last_served_by`), a parameterised `LiveReasoner` (optional `base_url` / `model` /
`api_key`), and a `critic_reasoner()` factory that returns a `RoutedReasoner`
only when the alternate config is complete, else the plain primary. `engine.py`
gains ~4 lines: `evaluate` reads `getattr(critic, "last_served_by", "primary")`
and puts `served_by` in its result; `judge_and_promote` writes `served_by` onto
the verdict record. The console's verdict block shows it. `capabilities.ALT_WAIT`
is `min(REWIND_ALT_WAIT, CRITIC_WAIT)`.

## Technical Context

**Language/Version**: Python 3.11+ (venv 3.14)

**Primary Dependencies**: none new — reuses the OpenAI-compatible client already
in `LiveReasoner` (the sole reasoning-vendor importer). `pytest`.
`concurrent.futures` (stdlib) for the alternate wait bound.

**Storage**: none — `served_by` lives on the Spec 005 verdict record on the
parent checkpoint

**Testing**: `pytest`. **Offline routing/fallback layer** with in-process stub
endpoints — no network, no credentials (NFR-008-04 / SC-010). **Live availability
check** — a `@pytest.mark.live` contract test that hits the alternate endpoint,
skipped when `CRITIC_BASE_URL` is unset (NFR-008-02 / FR-008-08).

**Target Platform**: local dev + CI; the alternate endpoint is a self-hosted
model server on independent GPU infrastructure (operational, not in this repo)

**Performance Goals**: `ALT_WAIT` ≤ `CRITIC_WAIT`; an alternate that times out on
every verdict cannot push the demo path past its budget (SC-005)

**Constraints**: same port + same schema for the alternate (FR-008-02/03); unset
config ⇒ identical behaviour, zero test-outcome change 000–007 (FR-008-07,
SC-008); alternate on the demo path only after the availability check (FR-008-08);
never on the critical path, no other spec depends on it (Article VIII / NFR-008-01)

**Scale/Scope**: one routed role (critic); 8 FRs, 4 NFRs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Article | Requirement | This plan |
|---|---|---|
| **VIII — Sponsor Integration Is Load-Bearing / Additive stop line** | The second sponsor is additive: background-provisioned, assessed once, deleted from config if not serving; **never on the critical path**; **no additive integration may consume an hour the graded integration needs**; overclaiming loses judges | Routing lives behind a config flag; unset ⇒ nothing changes (NFR-008-03 / SC-007/008). The demo path *replays* reasoning (Spec 007) — the alternate is exercised only in fixture capture + the contract test, never on the timed path. The console labels the provider so the demo *shows* portability, not asserts it. **Pass** |
| II — Specification First | Tech names only in plan | Spec 008 names no tech; this plan names the OpenAI-compatible client, `pytest`. **Pass** |
| IV — Nothing Is Invented | One port per external dependency; `LiveReasoner` the only reasoning-vendor importer | The alternate is reached through `ReasoningPort`; `RoutedReasoner` composes two `LiveReasoner`s; no new vendor import. **Pass** |
| V — Vertical Slices / no refactor | Additive | New `reasoning.py` members + one `capabilities` constant + ~4 lines in `engine.py` + one console block. `evaluate` / `promote` / `rank_by_evidence` bodies otherwise untouched; `demo.py` replay path unchanged. **Pass** |
| VI — Traceability & Pyramid + Seam Rule | FR → named test; fake/stub for the dependency; offline | Routing + fallback tested with in-process stubs offline; one live availability contract test. FR→test map in [quickstart.md](quickstart.md). **Pass** |
| X — Evidence Over Assertion | The verdict shows which provider judged | `served_by` on the record + on the console — the portability claim is displayed, not narrated. **Pass** |
| XI — Proven In The Runtime, Live | The demo runs live; additive integrations replayed from fixtures | The alternate's verdict is captured live once, then replayed; the live check is a contract test. **Pass** |
| XIII — Honest Framing | No overclaiming; if reduced to decoration, say so | If the alternate is not serving by the assessment, its config is removed and the record says `primary` — the demo makes no alternate claim (SC-007 §3). **Pass** |

**Result**: No violations. Complexity Tracking empty. This feature is the
governed additive integration and is designed to be deletable with zero impact.

## Project Structure

### Documentation (this feature)

```text
specs/008-alternate-inference-endpoint/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── routed-reasoner.md   # RoutedReasoner contract: try-order, wait bound, validation, last_served_by; served_by on the record
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/rewind/
├── reasoning.py       # EDIT (additive) — LiveReasoner(*, base_url=None, model=None, api_key=None);
│                      #   RoutedReasoner(alternate, primary, *, bound, validate=None) — a ReasoningPort
│                      #   with `last_served_by`; verdict_ids_from_bundle(context);
│                      #   critic_reasoner() factory (routed iff CRITIC_BASE_URL + CRITIC_MODEL both set)
├── capabilities.py    # EDIT (additive) — ALT_WAIT = min(_f("REWIND_ALT_WAIT", CRITIC_WAIT), CRITIC_WAIT)
├── engine.py          # EDIT (additive, ~4 lines) — evaluate() puts served_by in its result
│                      #   (getattr(critic,"last_served_by","primary"); "deterministic-fallback" on _fallback);
│                      #   judge_and_promote() writes served_by onto the verdict record
├── harness.py         # UNCHANGED (the demo path replays reasoning)
├── providers.py / ports.py  # UNCHANGED
tools/
└── capture_demo_fixtures.py  # EDIT (optional) — use critic_reasoner() so a captured verdict carries served_by

ui/
└── console.html      # EDIT — the verdict block shows `verdict.served_by` (fallback: verdict.provider)

.env.example          # EDIT — note CRITIC_BASE_URL / CRITIC_MODEL / CRITIC_API_KEY / REWIND_ALT_WAIT

tests/
├── unit/
│   └── test_alternate_endpoint.py     # NEW — routing + fallback with in-process stubs (SC-001/002/003/010),
│                                       #   served_by on the record, unset-config = unchanged (SC-007/008)
└── contract/
    └── test_alternate_endpoint_contract.py   # NEW — @pytest.mark.live: alternate reachable + conforming
                                               #   verdict; skipped when CRITIC_BASE_URL unset (NFR-008-02)
```

**Structure Decision**: Single-project layout unchanged. The feature is a
`reasoning.py` composition (`RoutedReasoner` + factory) plus a tiny `served_by`
pass-through in `engine.py` and one console line. Everything is inert when the
config is unset.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.

## Phase 0 — Research

See [research.md](research.md). Spec 008 has no `[NEEDS CLARIFICATION]`. Phase 0
records: the `RoutedReasoner` try-order and why validation of the alternate
response happens in the router (FR-008-04 requires alternate-invalid → primary,
not → deterministic); the `ALT_WAIT` derivation and clamp; how `served_by`
threads from the router through `evaluate` to the verdict record and the console;
the `critic_reasoner()` factory and the complete-config gate; and why nothing in
000–007 changes when `CRITIC_BASE_URL` is unset (`critic_reasoner()` returns the
plain primary; `evaluate`'s `getattr(critic,"last_served_by","primary")` is
inert).

## Phase 1 — Design & Contracts

Outputs:

- [data-model.md](data-model.md) — `Alternate Config`, `RoutedReasoner`,
  `served_by` values, and the routing state machine
- [contracts/routed-reasoner.md](contracts/routed-reasoner.md) — `RoutedReasoner`
  inputs, the ordered fallback, the wait bound, the same-schema validation of the
  alternate response, `last_served_by`, and `served_by` on the Spec 005 record
- [quickstart.md](quickstart.md) — config guide + FR/NFR/SC → (unit | contract)
  test map

Post-design Constitution re-check: unchanged — additive, no new dependency,
deletable with zero impact (Article VIII satisfied by construction).
