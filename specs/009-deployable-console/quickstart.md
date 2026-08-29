# Quickstart: Deployable Console

The hosted console lives entirely in `web/`. `ui/console.html` and the engine are
untouched.

---

## Local dev

```bash
cd web
npm install
npm run dev                     # Vite dev server; the console falls back to public/tree.json (no /api locally)
```

To exercise the endpoint locally, use the deploy target's dev command
(`npx vercel dev` from `web/`), which serves `api/fixture.ts` alongside the app.

## Build

```bash
cd web
npm run build                   # → web/dist/  (static) + the serverless api/ function
npm run test                    # web/api accept/reject/serve logic (Article VI: no UI-rendering test)
```

## Deploy (Vercel — the named target)

1. New project, **root directory `web/`**. Framework preset: Vite (auto).
2. Environment variables (server-side — **not** `VITE_`-prefixed):
   - `REWIND_CONSOLE_TOKEN` — the shared upload secret you choose.
   - `BLOB_READ_WRITE_TOKEN` — from the project's Blob store (Storage tab). If
     omitted, the deploy still serves the bundled fixture; `POST` returns `501`.
3. Deploy. The console renders `web/public/tree.json` until the first push.

## Push a run to the deployed console

The demo still runs locally exactly as before. To also feed the hosted console:

```bash
export REWIND_CONSOLE_ENDPOINT="https://<your-deploy>/api/fixture"
export REWIND_CONSOLE_TOKEN="<the same secret>"

FAKE=1 python demo.py           # writes fixtures/tree.json, then pushes it (best-effort)
# or, any time, push the current fixture on its own:
python tools/push_console.py
```

With neither env var set, `demo.py` behaves byte-for-byte as in Specification 006
— no push, no network (FR-009-09).

---

## FR / NFR / SC → verification

`ep` = `web/api/__tests__/fixture.test.ts`; `cf` =
`tests/unit/test_console_fixture.py` (Specification 006, reused); `va` = a
[visual-acceptance.md](checklists/visual-acceptance.md) item (which for the run
view points at Specification 006's checklist).

| Requirement | Verified by |
|---|---|
| FR-009-01 full Specification 006 run view | `cf` (payload shape) + `va` "006 parity" (all ten FR-006 items) |
| FR-009-02 reachable at a public URL, nothing local | `va` D1 (open deployed URL in a clean profile) |
| FR-009-03 single endpoint, polled, no manual refresh | `ep::get_returns_fixture` + `va` D2 (push → hosted view advances) |
| FR-009-04 authenticated upload becomes what is served | `ep::valid_post_is_served_by_next_get` |
| FR-009-05 no / wrong secret rejected, no state change | `ep::missing_token_401_no_change`, `ep::wrong_token_401_no_change` |
| FR-009-06 malformed body rejected, no state change | `ep::malformed_body_422_no_change` |
| FR-009-07 fallback shipped → sample, notice on screen | `ep::get_empty_store_returns_bundled` + `va` D3 (endpoint down → sample notice) |
| FR-009-08 no runtime/engine connection | `va` D4 (Network tab: only `/api/fixture` + `/tree.json`) |
| FR-009-09 push optional; failure never affects the local run | `ep` (helper contract) + `va` D5 (`demo.py` with no env vars = unchanged) |
| FR-009-10 mono = runtime-issued, face = derived | `va` FR-006-09 (reused) |
| NFR-009-01 build step scoped to `web/`; `ui/console.html` unchanged | `va` D6 (`git status` shows no `ui/` change) |
| NFR-009-02 deployable from `web/` alone | `va` D1 (root dir `web/`) |
| NFR-009-03 matches Specification 006 Design Reference | `va` (palette / type / layout, reused from 006) |
| NFR-009-04 upload size-capped, stored as data only | `ep::oversize_body_413`, `ep` (no eval of body) |
| NFR-009-05 no secret in the client bundle | `va` D7 (grep `web/dist` for the token value → nothing) |
| NFR-009-06 failed/malformed poll keeps last good fixture | `ep` + `va` D3 |

| Success criterion | Verified by |
|---|---|
| SC-009-01 | `va` D1 |
| SC-009-02 | `va` "006 parity" |
| SC-009-03 | `va` D2 |
| SC-009-04 | `ep::*_no_change` group |
| SC-009-05 | `va` D5 |
| SC-009-06 | `va` D3 |
| SC-009-07 | `va` D7 |
| SC-009-08 | `va` FR-006-09 (reused) |
| SC-009-09 | `va` D6 |

---

## Gate checkpoints

- **G2**: `npm run test` green in `web/`; `npm run build` succeeds; the built
  console renders `web/public/tree.json`.
- **G3**: the full visual-acceptance list (006 parity + D1–D7) passes; a live
  deploy URL exists; `git status` shows no change under `src/rewind/` or `ui/`;
  the README carries the hosted-console entry, framed as a shared view, not the
  demo.
