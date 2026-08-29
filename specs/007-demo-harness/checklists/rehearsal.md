# Rehearsal Checklist: Demo Harness

**Purpose**: The pre-freeze two-run manual pass. Constitution Article XI (the demo
runs live) and Article VI (the E2E path, run twice before 15:45). G3 evidence.

**How**: with `DAYTONA_API_KEY` set and `fixtures/reasoning/` captured, run
`python demo.py` twice, back to back.

---

## Run 1

- [ ] Command run with **no arguments**, in a normal shell — no prompt appeared, no input typed
- [ ] Output showed the stages in order: prepare → seed → observe-failure → rewind → fan-out → verdict → promote → console-fixture → teardown → leak-check
- [ ] The seed step that "optimises into subtraction" **failed** (printed FAIL) — the rewind point is real
- [ ] The fan-out showed **three live sandbox ids** from the runtime
- [ ] The verdict named a winner with an evidence-citing reason; "via critic" (not fallback) if the critic fixture is good
- [ ] Reported **path time** printed, and it is **under the budget** (default ~90s)
- [ ] Leak check reported **zero live sandboxes**
- [ ] Command exited **0**
- [ ] `fixtures/tree.json` updated; opening the console renders this run

Record: path time = ______ s   |   verdict winner = ______   |   exit = ______

## Run 2 (immediately after)

- [ ] Same stage sequence as run 1
- [ ] Same branch instructions as run 1 (replayed reasoning → identical)
- [ ] Same verdict winner and reason as run 1
- [ ] Path time within ~10% of run 1, and under budget
- [ ] Leak check zero; exit 0

Record: path time = ______ s   |   verdict winner = ______   |   exit = ______

## Failure-route spot check (once)

- [ ] Set `REWIND_DEMO_BUDGET=1` and run — exits **non-zero**, message names the budget and the actual time
- [ ] Move `fixtures/reasoning/` aside and run — exits **non-zero**, message names the missing fixtures, **no live reasoning call made**
- [ ] Unset `DAYTONA_API_KEY` and run — exits **non-zero** immediately, nothing created

---

**Sign-off**: two clean runs + the failure spot check → record in `docs/gates.md`
as G3 demo-path evidence.
