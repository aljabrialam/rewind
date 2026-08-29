"""tests/contract/test_reasoning_contract.py — spec 002, US6 live checks.

Every test is @pytest.mark.live: hits the real reasoning provider / real
sandboxes, skipped unless credentials are set. Not correctness — drift.

Run:  pytest tests/contract/test_reasoning_contract.py -m live -q
Traces: FR-002-01 (live), NFR-002-01.
"""

import os

import pytest

from rewind.reasoning import validate

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("LLM_API_KEY"), reason="LLM_API_KEY not set")
def test_live_response_passes_validate():
    """The real provider still returns an object the schema accepts."""
    from rewind.reasoning import LiveReasoner

    raw = LiveReasoner().next_instruction(
        "The task: create calc.py with add(a,b). Give the first shell step.")
    instr = validate(raw)                       # SchemaError => drift
    assert instr.instruction.strip() and instr.rationale.strip()


@pytest.mark.skipif(not os.environ.get("DAYTONA_API_KEY"), reason="DAYTONA_API_KEY not set")
def test_call_sequence_matches_live():
    """NFR-002-01 — the ordered port actions for a good step then a good step are
    the same against the live provider as against the fake: run, checkpoint."""
    from rewind.engine import Engine
    from rewind.providers import DaytonaProvider, FakeProvider

    def sequence(provider):
        e = Engine(provider)
        e.start()
        e.p.calls.clear()
        e.step("echo a > f", "1")
        e.step("echo b >> f", "2")
        ops = [c.operation for c in e.p.calls]
        e.shutdown()
        return ops

    fake_ops = sequence(FakeProvider())
    live_ops = sequence(DaytonaProvider())
    assert live_ops == fake_ops == ["run", "checkpoint", "run", "checkpoint"]
