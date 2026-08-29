# Visual Acceptance Checklist: Timeline Console

**Purpose**: the FR-by-FR manual pass. Constitution Article VI puts UI rendering
outside automated testing — this checklist is the stand-in, run at build time and
again before the live demonstration.

**How to run**: `python -m http.server 8000` from the repo root, open
`http://localhost:8000/ui/console.html`, and in another terminal run
`FAKE=1 python demo.py` (writes `fixtures/tree.json`). Then walk the list.

---

## FR-006-01 — ordered rail, head distinguished

- [ ] Every checkpoint from the fixture appears on the left rail
- [ ] They are in run order, top to bottom
- [ ] The head node is visually distinct from all others (glow ring) at a glance

## FR-006-02 — branches as parallel lanes under their parent

- [ ] Fan-out branches appear as lanes in the right column, not as rail nodes
- [ ] The lanes area is captioned with the common parent's id (mono)
- [ ] No branch is interleaved into the ordered rail

## FR-006-03 / FR-006-04 — request restore / fan-out from a selection

- [ ] With no checkpoint selected, the Restore and Fan-out controls are disabled/inert
- [ ] Selecting a checkpoint enables both controls
- [ ] Clicking Restore adds a `{kind:"restore", checkpoint_id, requested_at}` row to the Requests list and logs it to the console
- [ ] Clicking Fan-out does the same with `kind:"fan_out"`
- [ ] The browser Network tab shows **no** request to any runtime when either is clicked

## FR-006-05 — per-branch live id, state, elapsed, updating

- [ ] Each branch lane shows its sandbox id (mono), a state word (creating/running/done/failed), and an elapsed time
- [ ] Run `demo.py` again while the page is open — the lanes update within ~2s with no manual refresh
- [ ] A finished branch reads `done` or `failed` and is styled to match (promoted / running / released)

## FR-006-06 — evidence for any selection

- [ ] Selecting a rail checkpoint shows its exit code and output
- [ ] Selecting a branch lane shows that branch's own exit code and output
- [ ] Long output scrolls inside its panel; the rest of the layout does not move

## FR-006-07 — session counters always visible

- [ ] The footer shows a live sandbox count and a session elapsed time
- [ ] They stay visible with a checkpoint selected and the page scrolled
- [ ] The live count matches `live_sandboxes` in the fixture (not a node count)

## FR-006-08 — rationale distinguished from evidence

- [ ] A checkpoint with a rationale shows it in a separate area labelled as the agent's account, not evidence
- [ ] A checkpoint with no rationale shows no rationale area (not an empty one)

## FR-006-09 — monospace = runtime-issued, interface face = derived

- [ ] Sandbox ids, checkpoint ids, exit codes, captured output, executed instructions, `daytona <version>` — all monospace
- [ ] Section titles, footer counter numbers, state words, verdict prose — all interface face (not monospace)
- [ ] A checkpoint id shown inside a heading is still monospace

## FR-006-10 — legible at reduced scale

- [ ] At ~70% browser zoom, 1280px wide: rail, lanes, evidence, footer all readable
- [ ] No overlapping text, no clipped text, no horizontal page scroll on the demo fixture
- [ ] Below 900px the layout collapses to one column and stays readable

## NFR-006-01 / SC-009 — fixture-only, sample fallback

- [ ] Opening `ui/console.html` directly from disk (file://) renders the built-in sample and says it is a sample
- [ ] Served with the fixture present, it renders the fixture

## NFR-006-04 / SC-010 — one file, no build

- [ ] The console is a single `.html` file; opening it needs only a static file server, nothing else running
