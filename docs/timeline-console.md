# Timeline Console (spec 006)

One screen for the run's tree, its live branches, and the evidence behind every
decision. This is the surface the demonstration is given on. Full spec:
[`specs/006-timeline-console/`](../specs/006-timeline-console/).

## The pieces

| File | Role |
|---|---|
| `ui/console.html` | The console — one self-contained static page, dark theme, no build. Reads `fixtures/tree.json` on a 2s poll, re-renders, holds no runtime connection. |
| `src/rewind/engine.py` → `console_fixture(engine, *, verdict=None)` | Pure builder: `run.as_tree()` (Spec 001) + `live_sandboxes` + `session_elapsed` + `runtime_version` + `verdict` + per-branch `progress` (Spec 004). |
| `demo.py` | Writes `console_fixture(e, verdict=verdict)` to `fixtures/tree.json` after every beat. |
| `.rewind/console-mockup.html` | Frozen visual reference (a copy of the finished console). |

## What it shows

- **Rail** — every checkpoint in run order, the head marked `HEAD` with a glow ring (FR-006-01).
- **Branch lanes** — fan-out branches under a `Branches from <parent-id>` caption, each with its runtime sandbox id, running-state word (creating / running / done / failed), and elapsed time; live-updating on the poll (FR-006-02, FR-006-05).
- **Evidence panel** — exit code + output for any selected checkpoint or lane; the agent rationale in a separate area labelled *agent rationale — not evidence*, absent when there is none (FR-006-06, FR-006-08).
- **Controls** — *Restore to this checkpoint* / *Fan out from this checkpoint*; enabled on a selection; each records `{kind, checkpoint_id, requested_at}` to an on-screen Requests list and `console.log` — **no runtime call** (FR-006-03/04).
- **Footer** — live sandbox count, checkpoint count, branch count, session elapsed, `daytona <version>` — always visible (FR-006-07).

## Type rule (FR-006-09)

Monospace = a value the **runtime issued** (sandbox/checkpoint ids, exit codes, output, executed instructions, `daytona` version). Interface face = everything the console **derived** (headings, counters, state words, verdict prose).

## Testing

The only automated test is `tests/unit/test_console_fixture.py` — the fixture
*shape*. Constitution Article VI keeps UI rendering out of automated testing; the
ten FRs are signed off in
[`checklists/visual-acceptance.md`](../specs/006-timeline-console/checklists/visual-acceptance.md),
run at build and before the demo.

## Running

```bash
python -m http.server 8000
open http://localhost:8000/ui/console.html
FAKE=1 python demo.py        # console picks up fixtures/tree.json within ~2s
```

## Deployable version (spec 009)

[`web/`](../web/) is this same console rebuilt as a React app for a public URL —
component per region, fed by one `/api/fixture` endpoint that `demo.py` can push
`fixtures/tree.json` to (`tools/push_console.py`, env-gated, best-effort). It is a
**shared view, not the live demo** (`ui/console.html` stays the stage surface and
is untouched). Full spec: [`specs/009-deployable-console/`](../specs/009-deployable-console/).
