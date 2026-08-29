# Quickstart: Timeline Console

---

## Build & view

```bash
python -m http.server 8000            # from the repo root
open http://localhost:8000/ui/console.html
FAKE=1 python demo.py                 # writes fixtures/tree.json — the console picks it up in ~2s
```

Opened straight from disk (`file://…/ui/console.html`) the console renders its
built-in sample and says so (NFR-006-01).

## Test the fixture shape (the only automated test)

```bash
pytest tests/unit/test_console_fixture.py -q
```

Pure-logic: `Engine.console_fixture(...)` returns every field the console reads.
Per Constitution Article VI there are **no automated UI-rendering tests**.

## Visual acceptance

Walk [checklists/visual-acceptance.md](checklists/visual-acceptance.md) — the
FR-by-FR manual pass, at build and before the demo.

---

## FR / NFR / SC → verification

`cf` = `tests/unit/test_console_fixture.py`; `va` = a
[visual-acceptance.md](checklists/visual-acceptance.md) item.

| Requirement | Verified by |
|---|---|
| FR-006-01 ordered rail, head marked | `cf::test_has_head_and_ordered_nodes` + `va` FR-006-01 |
| FR-006-02 branches as lanes under parent | `cf::test_branch_nodes_identifiable_by_parent` + `va` FR-006-02 |
| FR-006-03 request restore from selection | `va` FR-006-03 (SC-004) |
| FR-006-04 request fan-out from selection | `va` FR-006-04 (SC-004) |
| FR-006-05 branch id + state + elapsed, live | `cf::test_branch_nodes_have_progress` (state ∈ set, elapsed ≥ 0) + `va` FR-006-05 (SC-005) |
| FR-006-06 evidence for any selection | `cf::test_nodes_carry_exit_and_stdout` + `va` FR-006-06 |
| FR-006-07 live count + session elapsed always | `cf::test_live_sandboxes_is_provider_count`, `cf::test_session_elapsed_present` + `va` FR-006-07 (SC-006) |
| FR-006-08 rationale ≠ evidence | `cf::test_rationale_field_passthrough` + `va` FR-006-08 (SC-003) |
| FR-006-09 mono = runtime-issued, face = derived | `va` FR-006-09 (SC-008) |
| FR-006-10 legible at reduced scale | `va` FR-006-10 (SC-007) |
| NFR-006-01 fixture-only, sample fallback | `cf::test_fixture_is_json_serialisable` + `va` NFR-006-01 (SC-009) |
| NFR-006-02 updates without manual refresh | `cf::test_recompute_reflects_advance` + `va` FR-006-05 |
| NFR-006-03 matches Design Reference | `va` (palette/type/layout checks throughout) |
| NFR-006-04 one file, no build | `va` NFR-006-04 (SC-010) |

| Success criterion | Verified by |
|---|---|
| SC-001 | `cf::test_has_head_and_ordered_nodes` + `va` FR-006-01 |
| SC-002 | `cf::test_branch_nodes_identifiable_by_parent` + `va` FR-006-02 |
| SC-003 | `cf::test_rationale_field_passthrough` + `va` FR-006-08 |
| SC-004 | `va` FR-006-03/04 (Network tab shows no runtime call) |
| SC-005 | `cf::test_recompute_reflects_advance` + `va` FR-006-05 |
| SC-006 | `va` FR-006-07 |
| SC-007 | `va` FR-006-10 |
| SC-008 | `va` FR-006-09 |
| SC-009 | `va` NFR-006-01 |
| SC-010 | `va` NFR-006-04 |

---

## Gate checkpoints

- **G2**: `pytest tests/unit/test_console_fixture.py -q` green; the console renders the demo fixture.
- **G3**: the full visual-acceptance list passes; `.rewind/console-mockup.html` frozen; no further edits to `ui/console.html`.
