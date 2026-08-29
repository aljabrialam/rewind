"""tests/unit/test_alternate_endpoint.py — spec 008: routing + fallback.

Offline, stub endpoints — no network, no credentials (NFR-008-04 / SC-010).
Contract: specs/008-alternate-inference-endpoint/contracts/routed-reasoner.md
"""

import ast
import re
import time
from pathlib import Path

import pytest

from rewind import capabilities
from rewind.engine import Engine
from rewind.providers import FakeProvider
from rewind.reasoning import (
    RoutedReasoner, VerdictSchemaError, critic_reasoner, validate_verdict,
    verdict_ids_from_bundle,
)

SRC = Path(__file__).resolve().parents[2] / "src" / "rewind"


# --------------------------------------------------------------- stub endpoints

class _Stub:
    """A ReasoningPort stub for the critic role — a valid verdict, or bad, or raises, or slow."""
    def __init__(self, *, bad=False, raises=None, delay=0.0, tag="?"):
        self.bad, self.raises, self.delay, self.tag = bad, raises, delay, tag
        self.calls = 0

    def next_instruction(self, context):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise self.raises
        if self.bad:
            return {"chosen": "not-a-real-id", "scores": {}, "reason": "x"}
        ids = re.findall(r"branch (\S+) \|", context) or ["a", "b"]
        return {"chosen": ids[0], "scores": {i: 1.0 for i in ids},
                "reason": f"branch {ids[0]} exited 0 with usable output"}


_VALIDATE = (lambda raw, ctx: validate_verdict(raw, verdict_ids_from_bundle(ctx)))
_CTX = "branch aaaa | exit 0\nbranch bbbb | exit 1\n"


class _Strat:
    def __init__(self, *ins):
        self._q, self._i = list(ins), 0

    def next_instruction(self, context):
        s = self._q[self._i % len(self._q)]
        self._i += 1
        return {"instruction": s, "rationale": "x"}


def _fanout():
    e = Engine(FakeProvider())
    e.start()
    e.step("echo base > f", "base")
    parent = e.run.head
    fo = e.fan_out(parent, _Strat("echo a > f", "echo b > f", "echo c > f"), 3)
    return e, parent, fo.children


class _RoutedCritic:
    """A RoutedReasoner critic that scores whatever branches the bundle names."""
    def __init__(self, alt, primary):
        self._rr = RoutedReasoner(alt, primary, bound=capabilities.ALT_WAIT, validate=_VALIDATE)

    def next_instruction(self, ctx):
        return self._rr.next_instruction(ctx)

    @property
    def last_served_by(self):
        return self._rr.last_served_by


# ============================================================ RoutedReasoner

def test_routed_reasoner_is_a_reasoning_port():
    rr = RoutedReasoner(_Stub(), _Stub(), bound=1.0)
    assert hasattr(rr, "next_instruction")


def test_alternate_ok_served_by_alternate():
    alt, prim = _Stub(tag="alt"), _Stub(tag="prim")
    rr = RoutedReasoner(alt, prim, bound=1.0, validate=_VALIDATE)
    out = rr.next_instruction(_CTX)
    assert out["chosen"] == "aaaa" and rr.last_served_by == "alternate"
    assert prim.calls == 0                                # SC-001


def test_alternate_raise_falls_back_to_primary():
    alt, prim = _Stub(raises=ConnectionError("down")), _Stub()
    rr = RoutedReasoner(alt, prim, bound=1.0, validate=_VALIDATE)
    rr.next_instruction(_CTX)
    assert rr.last_served_by == "primary" and prim.calls == 1


def test_alternate_bad_schema_rejected_like_primary():
    alt, prim = _Stub(bad=True), _Stub()
    rr = RoutedReasoner(alt, prim, bound=1.0, validate=_VALIDATE)
    out = rr.next_instruction(_CTX)                       # alt bad -> validate raises -> primary
    assert rr.last_served_by == "primary" and out["chosen"] == "aaaa"   # SC-002
    # the same bad payload straight through validate_verdict is rejected identically:
    with pytest.raises(VerdictSchemaError):
        _VALIDATE({"chosen": "not-a-real-id", "scores": {}, "reason": "x"}, _CTX)


def test_slow_alternate_falls_back_within_bound():
    alt, prim = _Stub(delay=0.4), _Stub()
    rr = RoutedReasoner(alt, prim, bound=0.05, validate=_VALIDATE)
    t0 = time.time()
    rr.next_instruction(_CTX)
    assert rr.last_served_by == "primary" and time.time() - t0 < 0.3   # SC-005


def test_alt_wait_le_critic_wait():
    assert capabilities.ALT_WAIT <= capabilities.CRITIC_WAIT           # SC-004


# ============================================================ factory

def _fake_live(monkeypatch):
    made = []

    class _FakeLive:
        def __init__(self, **kw):
            self.kw = kw
            made.append(self)

        def next_instruction(self, ctx):
            return {"chosen": "x", "scores": {}, "reason": "x"}

    monkeypatch.setattr("rewind.reasoning.LiveReasoner", _FakeLive)
    return _FakeLive, made


def test_factory_plain_when_config_absent(monkeypatch):
    monkeypatch.delenv("CRITIC_BASE_URL", raising=False)
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    _FakeLive, _ = _fake_live(monkeypatch)
    r = critic_reasoner()
    assert isinstance(r, _FakeLive) and not isinstance(r, RoutedReasoner)   # SC-007


def test_factory_routes_when_config_complete(monkeypatch):
    monkeypatch.setenv("CRITIC_BASE_URL", "https://gpu.box/v1")
    monkeypatch.setenv("CRITIC_MODEL", "served-model")
    monkeypatch.setenv("LLM_API_KEY", "k")
    _fake_live(monkeypatch)
    r = critic_reasoner()
    assert isinstance(r, RoutedReasoner)


def test_partial_config_is_absent(monkeypatch):
    monkeypatch.setenv("CRITIC_BASE_URL", "https://gpu.box/v1")
    monkeypatch.delenv("CRITIC_MODEL", raising=False)
    _FakeLive, _ = _fake_live(monkeypatch)
    assert isinstance(critic_reasoner(), _FakeLive)       # incomplete -> plain


# ============================================================ served_by on the record

def test_alternate_ok_served_by_on_record():
    e, parent, children = _fanout()
    critic = _RoutedCritic(_Stub(), _Stub())
    e.judge_and_promote(children, critic)
    assert e.run.get_verdict(parent)["served_by"] == "alternate"          # SC-001


def test_alternate_bad_falls_back_to_primary_on_record():
    e, parent, children = _fanout()
    critic = _RoutedCritic(_Stub(bad=True), _Stub())
    e.judge_and_promote(children, critic)
    assert e.run.get_verdict(parent)["served_by"] == "primary"            # SC-003


def test_both_fail_deterministic():
    e, parent, children = _fanout()
    critic = _RoutedCritic(_Stub(raises=RuntimeError("a")), _Stub(raises=RuntimeError("b")))
    e.judge_and_promote(children, critic)
    assert e.run.get_verdict(parent)["served_by"] == "deterministic-fallback"   # SC-003


def test_unset_config_runs_unchanged():
    e, parent, children = _fanout()
    e.judge_and_promote(children, _Stub())               # a plain critic — no last_served_by
    rec = e.run.get_verdict(parent)
    assert rec["served_by"] == "primary"                 # SC-007
    assert rec["chosen"] in {c.step_id for c in children} and e.run.head == rec["chosen"]


# ============================================================ Article VIII

def test_no_spec_00x_imports_routed():
    offenders = []
    for py in SRC.glob("*.py"):
        if py.name == "reasoning.py":
            continue
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in ("RoutedReasoner", "critic_reasoner"):
                offenders.append(py.name)
            if isinstance(node, ast.ImportFrom) and node.module == "reasoning":
                for a in node.names:
                    if a.name in ("RoutedReasoner", "critic_reasoner"):
                        offenders.append(py.name)
    assert offenders == [], f"routing referenced outside reasoning.py: {offenders}"
