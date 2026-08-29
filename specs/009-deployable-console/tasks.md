---
description: "Task list for Deployable Console implementation"
---

# Tasks: Deployable Console

**Feature**: `009-deployable-console`

**Input**: Design documents from `specs/009-deployable-console/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/fixture-endpoint.md](contracts/fixture-endpoint.md), [checklists/visual-acceptance.md](checklists/visual-acceptance.md), [quickstart.md](quickstart.md)

**Tests**: Automated tests are the **fixture endpoint** accept/reject/serve logic (`web/api/__tests__/fixture.test.ts`) and the **reused** Specification 006 Console Fixture *shape* test. Constitution Article VI — "UI rendering … is not tested" — so the run view is verified by [checklists/visual-acceptance.md](checklists/visual-acceptance.md) (006 parity + D1–D7), run at build and before the demo.

**Depends on**: Specification 006 (`console_fixture`, `ui/console.html` as the visual reference, `fixtures/tree.json` as the shipped fixture) — done and unchanged here.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1–US4, on user-story tasks only

## Path Conventions

Everything new is under `web/` or `tools/`. `demo.py` gets one additive env-gated block. `src/rewind/` and `ui/console.html` are **not touched**.

---

## Phase 1: Setup

- [X] T001 Scaffold `web/`: `package.json` (`react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`, `@vercel/blob`, `vitest`; scripts `dev` / `build` / `preview` / `test`), `vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`, `index.html`, `.gitignore` (`node_modules`, `dist`, `.vercel`), `.env.example` (`REWIND_CONSOLE_TOKEN`, `BLOB_READ_WRITE_TOKEN`, optional `VITE_POLL_MS`)
- [X] T002 `web/vercel.json` — framework `vite`, `outputDirectory` `dist`; leave `api/` to the default Node serverless detection
- [X] T003 [P] Copy the Specification 006 committed `fixtures/tree.json` to `web/public/tree.json` (the shipped fallback — FR-009-07). Add a repo-root note or a small `web/scripts/sync-fixture.mjs` so it can be refreshed
- [X] T004 [P] Add `web/` install + build to `.gitignore` review; confirm `node_modules/` already ignored at repo root (it is)

**Checkpoint**: `cd web && npm install && npm run build` produces `web/dist/` with no source yet beyond the Vite entry.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the types, the theme, and the endpoint. Blocks the components and the poll hook.

- [X] T005 `web/src/types.ts` — `ConsoleFixture`, `RailNode`, `BranchProgress`, `BranchState`, `Verdict`, per [data-model.md](data-model.md) §1. A mirror of `console_fixture()` output; no extra fields
- [X] T006 `web/src/theme.css` — the Specification 006 Design Reference palette (`--ground`, `--rail`, `--ink`, `--muted`, `--live`, `--branch`, `--won`, `--killed`) and type faces (`--face`, `--mono`) as CSS custom properties; base `body` rules; `.mono` utility. Values copied verbatim from `ui/console.html` (NFR-009-03)
- [X] T007 `web/src/sample.ts` — the built-in `SAMPLE: ConsoleFixture` (minimal: a root + one step + a two-branch fan-out + a verdict) for the endpoint-unreachable case (FR-009-07)
- [X] T008 `web/api/fixture.ts` — the serverless function per [contracts/fixture-endpoint.md](contracts/fixture-endpoint.md): `GET` (stored object via `@vercel/blob` → bundled `tree.json`; `Cache-Control: no-store`); `POST` (`x-rewind-token` constant-time compare vs `REWIND_CONSOLE_TOKEN` → `401`; body > 512 KiB → `413`; `isWellFormedFixture()` → `422`; no `BLOB_READ_WRITE_TOKEN` → `501`; else `put()` and `200`); other methods → `405` + `Allow`. Export `isWellFormedFixture` and a testable `handleRequest` that takes a minimal `{method, headers, rawBody}` and a storage adapter
- [X] T009 `web/src/useFixture.ts` — poll hook: `fetch("api/fixture")` (relative — Edge Cases) on `VITE_POLL_MS` (default 2000, clamped ≤ 2000); on failure/non-2xx → `fetch("tree.json")`; on failure → `SAMPLE`. Client-side shape check; a failed/malformed poll **keeps the last good fixture + source** (NFR-009-06). Returns `{fixture, source: "live" | "shipped" | "sample"}`

**Checkpoint**: `web/api/fixture.ts` importable in a test; `useFixture` compiles.

---

## Phase 3: Endpoint tests (automated — Article VI-compliant, not UI rendering)

- [X] T010 [P] `web/api/__tests__/fixture.test.ts` — `valid_post_is_served_by_next_get`, `get_empty_store_returns_bundled` (FR-009-04, FR-009-07)
- [X] T011 [P] `web/api/__tests__/fixture.test.ts` — `missing_token_401_no_change`, `wrong_token_401_no_change`, `malformed_body_422_no_change`, `oversize_body_413` (each asserts a follow-up `GET` returns the prior fixture — FR-009-05, FR-009-06, NFR-009-04)
- [X] T012 [P] `web/api/__tests__/fixture.test.ts` — `method_not_allowed_405`, `no_store_returns_501_and_get_still_serves_bundled` (contract M1, P5)

**Checkpoint**: `cd web && npm run test` green.

- [X] T012a [P] `web/tests/e2e/console.spec.ts` + `web/playwright.config.ts` — the pyramid's single **Top — E2E** (Article VI): scripted Chromium pass over the demonstration path against `npm run dev`. Six specs: live-fixture render (rail/lanes/verdict/footer, no sample banner); HEAD marker on a rail checkpoint (`::after` "HEAD"); bundled-fixture fallback shows the "sample data — not a live push" banner; replay steps seed→fail→rewind→fan-out→verdict then returns to the live view; replay completes with **all** network blocked (client-only proof); select a checkpoint → evidence updates, **Restore** records a request row and 0 external requests fire. Behaviour/DOM/network assertions only — no pixels/layout. `vite.config.ts` excludes `tests/e2e/**` from `vitest`.

**Checkpoint**: `cd web && npm run test:e2e` green (`npx playwright install chromium` once).

---

## Phase 4: User Story 1 — Open the run at a link (Priority: P1) 🎯 MVP

**Goal**: the full Specification 006 run view, rendered from `useFixture`, deployable.

### Implementation

- [X] T013 [US1] `web/src/components/Rail.tsx` — ordered non-branch nodes; head glow ring; per-node status dot (ok / fail); `#index · id · sandbox` meta (`id`/`sandbox` mono); `exit N` on failure (mono); click selects. Port `ui/console.html` `.rail` markup/CSS (FR-006-01)
- [X] T014 [US1] `web/src/components/BranchLanes.tsx` — branch nodes (`node.branch === true` or parent has > 1 child) as lanes under a `Branches from <parent-id>` caption (`<parent-id>` mono); per lane: `Branch i`, state word from `progress.state` (fallback `terminal`/`state`), `progress.elapsed_seconds` as `Ns`, sandbox id (mono), `exit N` (mono), truncated instruction (mono, ellipsis); inset colour running/promoted/released; click selects (FR-006-02, FR-006-05)
- [X] T015 [US1] `web/src/components/EvidencePanel.tsx` — for the selected node: `exit code N` (label face, `N` mono, green/red); `<pre>` output (mono, `overflow:auto`, bounded `max-height`, `(no output)` when empty); rationale area **only when `rationale` truthy**, labelled "agent rationale — not evidence", visually distinct (FR-006-06, FR-006-08)
- [X] T016 [US1] `web/src/components/VerdictCard.tsx` — when `fixture.verdict` is non-null: the reason prose (face) + "judged on execution evidence · `<provider>`" (`provider` mono). Nothing when null (Article X)
- [X] T017 [US1] `web/src/components/Footer.tsx` — fixed footer: `live sandboxes` = `fixture.live_sandboxes`, `checkpoints` = node count, `branches` = branch count, `session` = `fixture.session_elapsed` as `N.Ns` (all numbers in the face), `daytona <runtime_version>` (version mono); `flex-wrap` (FR-006-07)
- [X] T018 [US1] `web/src/components/RequestsList.tsx` + wiring in `App.tsx` — **Restore to this checkpoint** / **Fan out from this checkpoint** buttons, disabled when nothing selected; on click append `{kind, checkpoint_id: sel, requested_at: new Date().toISOString()}` to an on-screen list and `console.log` JSON; **no fetch/XHR/WebSocket** (FR-006-03/04, FR-009-08)
- [X] T019 [US1] `web/src/App.tsx` + `web/src/main.tsx` — two-column-collapsing layout from `theme.css`; `useFixture` for state; selection state (falls back to head when the selected id disappears — Edge Cases); a `source !== "live"` banner ("sample data — …") (FR-009-01, FR-009-07); mount in `index.html`
- [X] T020 [US1] `web/index.html` + `theme.css` — reduced-scale pass at ~70% zoom / 1280px on `web/public/tree.json`; ellipsis on one-line command rows; no fixed width over 1280px; `<pre>` and lanes scroll within themselves; < 900px single-column collapse (FR-006-10)

**Manual check**: [visual-acceptance.md](checklists/visual-acceptance.md) Part 1 (006 parity) against `npm run dev`.

---

## Phase 5: User Story 2 — Push the run to the link (Priority: P1)

**Goal**: `demo.py` (opt-in) and a standalone tool push `fixtures/tree.json` to the endpoint; best-effort.

### Implementation

- [X] T021 [US2] `tools/push_console.py` — read `fixtures/tree.json`; `POST` to `REWIND_CONSOLE_ENDPOINT` with `x-rewind-token: REWIND_CONSOLE_TOKEN` using `urllib`; 5s timeout; print `pushed → <endpoint> (<status>)` or `console push skipped: <reason>`; exit 0 regardless (contract H1–H4)
- [X] T022 [US2] `demo.py` — in `main()`, after `run_demo()` returns, when `res.fixture_written` and both `REWIND_CONSOLE_ENDPOINT` + `REWIND_CONSOLE_TOKEN` are set, `sys.path`-insert the repo root, `from tools.push_console import push`, `push("fixtures/tree.json")`, all wrapped so any exception prints one line and is ignored. `rewind.harness.run_demo` (which writes the fixture, spec 007) is **not** touched. No behaviour change when the env vars are absent (FR-009-09)
- [X] T023 [US2] `.env.example` (repo root) — add commented `REWIND_CONSOLE_ENDPOINT=` and `REWIND_CONSOLE_TOKEN=` with a one-line note that both must be set to enable the push

**Manual check**: D2, D5 in [visual-acceptance.md](checklists/visual-acceptance.md).

---

## Phase 6: User Story 3 — Reject bad uploads (Priority: P1)

**Goal**: covered by the endpoint + its tests (Phase 2–3); this phase is the manual confirmation on a real deploy.

- [ ] T024 [US3] Against a deployed endpoint: `curl` a `POST` with no token, with a wrong token, and with a valid token + `{"not":"a fixture"}`; confirm `401` / `401` / `422` and that `GET` still returns the last good fixture (FR-009-05, FR-009-06)
- [ ] T025 [US3] `curl` a `POST` with a valid token + a > 512 KiB body; confirm `413`; confirm the body is never reflected/echoed (NFR-009-04)

**Manual check**: D-series notes; record results in `docs/gates.md`.

---

## Phase 7: User Story 4 — Legible before the first push (Priority: P2)

**Goal**: shipped fixture and sample both render; the on-screen notice is honest.

- [X] T026 [US4] Confirm `npm run dev` (no `/api`) renders `web/public/tree.json` with the "sample data — not a live push" banner (FR-009-07)
- [X] T027 [US4] Simulate the endpoint unreachable (block `/api/fixture` and `/tree.json`); confirm `SAMPLE` renders with the "endpoint unreachable" banner; restore the network and confirm the banner clears on the next poll (NFR-009-06)

**Manual check**: D3.

---

## Phase 7b: User Story 5 — Replay the run for a viewer (Priority: P3) — FR-009-11

**Goal**: one control plays the run's stages back through the console, client-only, no engine, no network; honest "recorded replay" banner; resumes the live view on end.

- [X] T027a [US5] `web/src/replay.ts` — `buildReplayFrames(fixture): ConsoleFixture[]`: progressive rail reveal → rewind (head → branch parent) → fan-out frames cycling `creating`/`running`/`done|failed` with `live_sandboxes` ramping → verdict frame (winner promoted to head, losers `released`). `session_elapsed` ramps. Falls back to plain rail reveal when the fixture has no branch nodes
- [X] T027b [US5] `web/src/App.tsx` — Replay / Stop button in a `.topbar`; while replaying, render `frames[i]` instead of the polled fixture, advance on `REPLAY_FRAME_MS`, hold `REPLAY_HOLD_MS` on the last frame, then `setReplay(null)` to resume the poll; show a green "▶ replaying a recorded run — not a live push" banner throughout (FR-009-11 / SC-009-10); clear selection on start
- [X] T027c [US5] `web/src/theme.css` — `.topbar`, `.replayBtn` (+ `.on`), `.notice.replay`

**Manual check**: press Replay on the deployed URL — the view steps seed → fail → rewind → fan-out → verdict over ~19s, the banner shows the whole time, and it returns to the live fixture at the end; the Network tab shows no request during replay.

---

## Phase 8: Polish & Deploy

- [X] T028 Deploy `web/` to Vercel: root dir `web/`, `REWIND_CONSOLE_TOKEN` + `BLOB_READ_WRITE_TOKEN` set for all envs, Blob store `rewind-fixture` created + linked. URL: **https://rewind-console.vercel.app**
- [X] T029 [P] `web/dist` + deployed bundle secret grep — token value / `BLOB_READ_WRITE` / `vercel-storage.com` → 0 hits (NFR-009-05 / SC-009-07 / D7)
- [X] T030 [P] `README.md` — add a "Hosted console" line under the timeline-console section: what the URL is, that it is a **shared view of the run, not the live demo**, and how to push to it (Articles XI, XIII)
- [X] T031 [P] `docs/timeline-console.md` — add a short "Deployable version (spec 009)" section pointing at `web/` and this spec
- [ ] T032 Run the full [checklists/visual-acceptance.md](checklists/visual-acceptance.md) (Part 1 006-parity on the deployed URL + Part 2 D1–D7); record the result and any deferred item in `docs/gates.md`
- [ ] T033 Confirm `git status` shows no change under `src/rewind/` or `ui/`; `pytest -q` still green; `FAKE=1 python demo.py` (no push env) unchanged; note in `docs/gates.md`

---

## Dependencies & Execution Order

- **Setup (T001–T004)** → **Foundational (T005–T009)** blocks everything.
- **Phase 3 (T010–T012)**: after T008 — the endpoint tests.
- **Phase 4 (T013–T020)**: after Foundational. T013–T017 are separate files → parallelizable; T018–T020 wire `App.tsx` → sequential after them.
- **Phase 5 (T021–T023)**: independent of Phase 4 (Python side) — can run in parallel with it.
- **Phases 6–7**: need a deploy (T028) for the real-endpoint items; the local items (T026) can run after Phase 4.
- **Phase 8**: last; T028 before T029/T032.

### Parallel opportunities

- T003 / T004 in Setup
- T010 / T011 / T012 (same file, distinct tests — write together)
- T013 / T014 / T015 / T016 / T017 (one component file each)
- T021–T023 (Python push) alongside all of Phase 4
- T029 / T030 / T031 in Polish

---

## Implementation Strategy

### MVP (US1)

1. Setup + Foundational (T001–T009) + endpoint tests (T010–T012)
2. US1 components + wiring (T013–T020)
3. **STOP and VALIDATE**: `npm run dev`, walk 006-parity against the dev server rendering `web/public/tree.json`.

### Incremental

US1 (view at a link, dev server) → US2 (push from `demo.py` / tool) → deploy (T028) → US3 (reject bad uploads on the real endpoint) → US4 (fallback + notice) → visual-acceptance pass + README/docs.

---

## Notes

- `src/rewind/` and `ui/console.html` are **not touched**. The only repository-root
  change is the env-gated push block in `demo.py` and two commented lines in
  `.env.example`.
- The **only** automated tests are the fixture endpoint's accept/reject/serve
  logic and the reused Specification 006 fixture-shape test — Constitution
  Article VI keeps UI rendering out of automated testing; the run view is signed
  off in [checklists/visual-acceptance.md](checklists/visual-acceptance.md).
- No secret is `VITE_`-prefixed; secrets are read only inside `web/api/`.
- The hosted console is a shared view, framed as such in the README — it is not
  the graded live demonstration and sits off its critical path.
