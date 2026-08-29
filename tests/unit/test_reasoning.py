"""tests/unit/test_reasoning.py — spec 002: structured instructions, replayable.

No network. Traces: FR-002-01, FR-002-08, NFR-002-02.
Rules: specs/002-step-execution-and-evidence/contracts/reasoning-port.md
"""

import ast
import json
from pathlib import Path

import pytest

from rewind.reasoning import (
    FIXTURES_DIR,
    Instruction,
    RecordingReasoner,
    ReplayReasoner,
    SchemaError,
    validate,
)

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "rewind"


class _CannedReasoner:
    def __init__(self, responses):
        self._r = list(responses)
        self._i = 0

    def next_instruction(self, context):
        r = self._r[self._i]
        self._i += 1
        return r


# --------------------------------------------------------------- FR-002-01 schema

def test_valid_payload_accepted():
    got = validate({"instruction": "echo hi", "rationale": "smoke test"})
    assert isinstance(got, Instruction)
    assert got.instruction == "echo hi" and got.rationale == "smoke test"


def test_missing_instruction_rejected():
    with pytest.raises(SchemaError, match="instruction"):
        validate({"rationale": "x"})


def test_empty_instruction_rejected():
    for bad in ("", "   ", "\n\t"):
        with pytest.raises(SchemaError):
            validate({"instruction": bad, "rationale": "x"})


def test_missing_rationale_rejected():
    with pytest.raises(SchemaError, match="rationale"):
        validate({"instruction": "echo hi"})


def test_empty_rationale_rejected():
    with pytest.raises(SchemaError, match="rationale"):
        validate({"instruction": "echo hi", "rationale": "  "})


def test_wrong_types_rejected():
    for payload in (
        {"instruction": 42, "rationale": "x"},
        {"instruction": ["echo"], "rationale": "x"},
        {"instruction": "echo", "rationale": None},
        {"instruction": "echo", "rationale": 7},
        ["not", "a", "mapping"],
    ):
        with pytest.raises(SchemaError):
            validate(payload)


def test_unknown_keys_ignored():
    got = validate({"instruction": "ls", "rationale": "look", "confidence": 0.9, "notes": "hi"})
    assert got == Instruction("ls", "look")


# ------------------------------------------------------- NFR-002-02 replay

def _write_fixtures(d, responses):
    for i, r in enumerate(responses, 1):
        (d / f"{i:03d}.json").write_text(json.dumps({
            "seq": i, "context": f"step {i}", "response": r,
            "recorded_at": "2026-08-29T00:00:00Z", "model": "test-model",
        }))


def test_replay_is_deterministic(tmp_path):
    responses = [
        {"instruction": "echo 1", "rationale": "a"},
        {"instruction": "echo 2", "rationale": "b"},
        {"instruction": "echo 3", "rationale": "c"},
    ]
    _write_fixtures(tmp_path, responses)

    def run_once():
        r = ReplayReasoner(tmp_path)
        return [validate(r.next_instruction("")).instruction for _ in responses]

    assert run_once() == run_once() == ["echo 1", "echo 2", "echo 3"]


def test_replay_exhaustion_raises(tmp_path):
    _write_fixtures(tmp_path, [{"instruction": "echo 1", "rationale": "a"}])
    r = ReplayReasoner(tmp_path)
    r.next_instruction("")
    with pytest.raises(LookupError):
        r.next_instruction("")


def test_recording_then_replay_round_trips(tmp_path):
    canned = _CannedReasoner([
        {"instruction": "echo a", "rationale": "1"},
        {"instruction": "echo b", "rationale": "2"},
    ])
    rec = RecordingReasoner(canned, fixtures_dir=tmp_path)
    rec.next_instruction("ctx1")
    rec.next_instruction("ctx2")
    files = sorted(tmp_path.glob("*.json"))
    assert len(files) == 2
    replay = ReplayReasoner(tmp_path)
    assert validate(replay.next_instruction("")).instruction == "echo a"
    assert validate(replay.next_instruction("")).instruction == "echo b"


def test_every_reasoning_fixture_has_provenance(tmp_path):
    canned = _CannedReasoner([{"instruction": "echo a", "rationale": "1"}])
    RecordingReasoner(canned, fixtures_dir=tmp_path).next_instruction("c")
    committed = list((REPO / "fixtures" / "reasoning").glob("*.json"))
    for f in list(tmp_path.glob("*.json")) + committed:
        blob = json.loads(f.read_text())
        assert blob["recorded_at"] and blob["model"], f"{f} missing provenance"


# --------------------------------------------------- Constitution Art. IV

def test_no_reasoning_sdk_outside_reasoning_module():
    banned = ("openai", "anthropic", "litellm", "cohere")
    offenders = []
    for py in SRC.glob("*.py"):
        if py.name == "reasoning.py":
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            if any(n.split(".")[0] in banned for n in names):
                offenders.append(py.name)
    assert offenders == [], f"reasoning SDK imported outside reasoning.py: {offenders}"


def test_default_fixtures_dir_points_into_repo():
    assert FIXTURES_DIR.name == "reasoning" and FIXTURES_DIR.parent.name == "fixtures"
