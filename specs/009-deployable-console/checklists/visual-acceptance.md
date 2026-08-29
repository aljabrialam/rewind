# Visual Acceptance Checklist: Deployable Console

**Purpose**: the manual pass. Constitution Article VI puts UI rendering outside
automated testing — this is the stand-in, run at build time and again before the
demonstration.

**Two parts**:
1. **006 parity** — the hosted console must pass every item of
   [`specs/006-timeline-console/checklists/visual-acceptance.md`](../../006-timeline-console/checklists/visual-acceptance.md),
   run against the deployed URL instead of `ui/console.html`.
2. **Deploy-only (D1–D7)** — the items below, specific to this feature.

**How to run**: deploy `web/` (root dir `web/`, env vars set). Open the deployed
URL. In a terminal with `REWIND_CONSOLE_ENDPOINT` + `REWIND_CONSOLE_TOKEN` set,
run `FAKE=1 python demo.py`.

---

## Part 1 — 006 parity

- [ ] FR-006-01 ordered rail, head distinguished — passes on the deployed URL
- [ ] FR-006-02 branches as lanes under the parent caption — passes
- [ ] FR-006-03 / FR-006-04 restore / fan-out request recording, no runtime call — passes
- [ ] FR-006-05 per-branch id, state word, elapsed, updating on the poll — passes
- [ ] FR-006-06 evidence (exit + output) for any selection — passes
- [ ] FR-006-07 session counters always visible; live count from `live_sandboxes` — passes
- [ ] FR-006-08 rationale in a separate labelled non-evidence area; absent rationale not rendered — passes
- [ ] FR-006-09 monospace = runtime-issued, interface face = derived — passes  *(also covers FR-009-10 / SC-009-08)*
- [ ] FR-006-10 legible at ~70% zoom / 1280px; one-column collapse below 900px — passes
- [ ] NFR-006-03 palette / type / layout match the Design Reference — passes

---

## Part 2 — deploy-only

### D1 — reachable at a public URL with nothing local  *(FR-009-02, NFR-009-02, SC-009-01)*

- [ ] The Vercel project's root directory is `web/`
- [ ] Opening the deployed URL in a clean browser profile, with no local server and no repo clone, renders the full run view
- [ ] The rendered fixture is the endpoint's current one (or the shipped fixture before any push)

### D2 — push makes the hosted view advance  *(FR-009-03, SC-009-03)*

- [ ] With the hosted URL open and the push env vars set, `FAKE=1 python demo.py` makes the rail / lanes / counters advance to match the local console within one refresh interval (~2s)
- [ ] No manual action is taken on the deployment

### D3 — fallback + sample notice  *(FR-009-07, NFR-009-06, SC-009-06)*

- [ ] Before any push, the console renders `web/public/tree.json` and shows a "sample data — not a live push" notice
- [ ] With the endpoint made unreachable (e.g. offline), the console renders the built-in sample and states it is a sample
- [ ] A `GET` that fails or returns a malformed body leaves the last good view on screen (no blank / broken frame)
- [ ] Once a real push lands, the notice clears on the next poll

### D4 — no runtime / engine connection  *(FR-009-08)*

- [ ] Over a full session, the browser Network tab shows only `GET /api/fixture` (and, on fallback, `GET /tree.json`) — no other host, no websocket
- [ ] Clicking Restore / Fan-out adds a Requests row and logs JSON, with **no** network request

### D5 — push is optional and harmless  *(FR-009-09, SC-009-05)*

- [ ] With neither `REWIND_CONSOLE_ENDPOINT` nor `REWIND_CONSOLE_TOKEN` set, `FAKE=1 python demo.py` runs every beat exactly as in Specification 006 and makes no network call
- [ ] With the endpoint pointed at an unreachable host, `demo.py` still completes every beat; it prints one line about the failed push and exits 0

### D6 — the build step is contained  *(NFR-009-01, SC-009-09)*

- [ ] `git status` after building shows no change under `src/rewind/` or `ui/`
- [ ] The only repository-root edit for this feature is the env-gated push block at the end of `demo.py`
- [ ] `ui/console.html` still opens from `file://` and renders its sample (Specification 006 NFR-006-04 intact)

### D7 — no secret in the client bundle  *(NFR-009-05, SC-009-07)*

- [ ] `grep -r "$REWIND_CONSOLE_TOKEN" web/dist` returns nothing
- [ ] `grep -ri "blob_read_write_token\|BLOB_READ_WRITE" web/dist` returns nothing
- [ ] No `VITE_`-prefixed variable holds a secret

---

## Result

- Run at: __________  by: __________
- 006 parity: ____ / 10   Deploy-only: ____ / 7
- Deferred items (with reason) recorded in `docs/gates.md`.
