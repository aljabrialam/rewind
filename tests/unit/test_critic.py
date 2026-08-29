"""tests/unit/test_critic.py — spec 005: critic evaluation and promotion.

Offline. Closes the Constitution Article IX loop.
Contracts: specs/005-critic-evaluation-and-promotion/contracts/{verdict,promotion}.md
"""

import time
from collections import Counter

import pytest

from rewind import capabilities
from rewind.engine import Engine, rank_by_evidence
from rewind.ports import Checkpoint, ExecResult, Handle, RuntimeCallError
from rewind.providers import FakeProvider
from rewind.reasoning import Verdict, VerdictSchemaError, validate_verdict


# --------------------------------------------------------------- helpers

class _Critic:
    """A ReasoningPort in the judging role — returns a fixed verdict / raises / sleeps."""
    def __init__(self, payload=None, *, raises=None, delay=0.0):
        self.payload, self.raises, self.delay = payload, raises, delay
        self.calls = 0

    def next_instruction(self, context):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.raises:
            raise self.raises
        return self.payload


class _Strat:
    def __init__(self, *ins):
        self._q, self._i = list(ins), 0

    def next_instruction(self, context):
        s = self._q[self._i % len(self._q)]
        self._i += 1
        return {"instruction": s, "rationale": f"try {s}"}


def _fanout(provider=None, strategies=("echo a > f", "echo b > f", "echo c > f")):
    e = Engine(provider or FakeProvider())
    e.start()
    e.step("echo base > f", "base")
    parent = e.run.head
    fo = e.fan_out(parent, _Strat(*strategies), len(strategies))
    return e, parent, fo.children


def _cp(i, sid, exit_code, elapsed=0.1):
    return Checkpoint(index=i, step_id=sid, instruction=f"s{i}", parent_id="p",
                      snapshot=f"snap{i}", evidence=ExecResult(exit_code, "", elapsed))


def _verdict_for(children, chosen_i=0, reason="branch chose exit 0 output ok"):
    return {"chosen": children[chosen_i].step_id,
            "scores": {c.step_id: float(len(children) - k) for k, c in enumerate(children)},
            "reason": reason}


# ================================================= fallback ranking (NFR-005-02)

def test_rank_is_total_over_all_failed():
    bs = [_cp(0, "a", 3), _cp(1, "b", 1), _cp(2, "c", 2)]
    r = rank_by_evidence(bs)
    assert r["winner"] == 1 and len(r["scores"]) == 3
    assert "no branch exited 0" in r["reason"]


def test_rank_is_pure():
    bs = [_cp(0, "a", 0), _cp(1, "b", 1)]
    snap = [(b.step_id, b.evidence.exit_code, b.state) for b in bs]
    r1, r2 = rank_by_evidence(bs), rank_by_evidence(bs)
    assert r1 == r2
    assert [(b.step_id, b.evidence.exit_code, b.state) for b in bs] == snap


def test_rank_tie_break_is_deterministic():
    bs = [_cp(0, "z", 0, 0.1), _cp(1, "a", 0, 0.1)]     # identical evidence
    r = rank_by_evidence(bs)
    assert r["winner"] == 0 and "tie" in r["reason"]    # lower index wins


def test_rank_scores_are_numeric():
    r = rank_by_evidence([_cp(0, "a", 0), _cp(1, "b", 1)])
    assert all(isinstance(s["score"], float) for s in r["scores"])
    assert r["scores"][0]["score"] > r["scores"][1]["score"]   # exit 0 scores higher


# ================================================= verdict schema (FR-005-02/03)

def test_valid_verdict_accepted():
    v = validate_verdict({"chosen": "a", "scores": {"a": 2, "b": 1}, "reason": "a exit 0"}, ["a", "b"])
    assert isinstance(v, Verdict) and v.chosen == "a" and v.scores == {"a": 2.0, "b": 1.0}


def test_reason_required():
    with pytest.raises(VerdictSchemaError):
        validate_verdict({"chosen": "a", "scores": {"a": 1, "b": 1}, "reason": "  "}, ["a", "b"])


def test_reject_unknown_branch():
    with pytest.raises(VerdictSchemaError, match="not one of"):
        validate_verdict({"chosen": "ghost", "scores": {"a": 1, "b": 1}, "reason": "x"}, ["a", "b"])


def test_reject_missing_score():
    with pytest.raises(VerdictSchemaError, match="omits a score"):
        validate_verdict({"chosen": "a", "scores": {"a": 1}, "reason": "x"}, ["a", "b"])


def test_reject_bad_structure():
    with pytest.raises(VerdictSchemaError):
        validate_verdict(["not", "a", "mapping"], ["a", "b"])


def test_reason_unsupported_flag_not_a_rejection():
    v = validate_verdict({"chosen": "a", "scores": {"a": 1, "b": 1}, "reason": "vibes"}, ["a", "b"])
    assert v.reason_unsupported is True


# ================================================= US1 — evidence -> verdict -> head

def test_bundle_is_evidence_only():
    e, _, children = _fanout()
    bundle = e._evidence_bundle(children)
    assert "exit" in bundle and children[0].step_id in bundle
    assert "try echo" not in bundle                    # no strategist rationale (SC-001)


def test_evaluate_accepts_a_valid_verdict():
    e, _, children = _fanout()
    ev = e.evaluate(children, _Critic(_verdict_for(children, 1)))
    assert ev["chosen"] == children[1].step_id and ev["fallback_used"] is False


def test_winner_becomes_head():
    e, parent, children = _fanout()
    res = e.judge_and_promote(children, _Critic(_verdict_for(children, 2)))
    assert e.run.head == children[2].step_id == res["winner"]   # SC-003


def test_losers_released_and_marked():
    e, parent, children = _fanout()
    e.judge_and_promote(children, _Critic(_verdict_for(children, 0)))
    for c in children[1:]:
        cp = e.run.get(c.step_id)
        assert cp.state == "released" and cp.terminal == "abandoned"


def test_tree_intact_after_promotion():
    e, parent, children = _fanout()
    e.judge_and_promote(children, _Critic(_verdict_for(children, 0)))
    assert e.run.check_integrity() == []                # SC-004
    for c in children:
        cp = e.run.get(c.step_id)
        assert cp.instruction and cp.evidence is not None and cp.snapshot


# ================================================= US2 — reject -> fallback

def test_fallback_on_unreachable_critic():
    e, parent, children = _fanout()
    res = e.judge_and_promote(children, _Critic(raises=RuntimeError("down")))
    assert res["verdict"]["fallback_used"] is True
    assert res["verdict"]["fallback_trigger"].startswith("critic-unreachable")


def test_fallback_on_timeout(monkeypatch):
    monkeypatch.setattr(capabilities, "CRITIC_WAIT", 0.05)
    e, parent, children = _fanout()
    t0 = time.time()
    res = e.judge_and_promote(children, _Critic(_verdict_for(children), delay=0.4))
    assert res["verdict"]["fallback_trigger"] == "critic-timeout"
    assert time.time() - t0 < 0.35                      # SC-010 — bounded


def test_fallback_on_rejected_verdict():
    e, parent, children = _fanout()
    bad = {"chosen": "ghost", "scores": {}, "reason": "x"}
    res = e.judge_and_promote(children, _Critic(bad))
    assert res["verdict"]["fallback_trigger"].startswith("verdict-rejected")
    assert e.run.head in {c.step_id for c in children}  # a winner was still promoted (SC-005)


def test_reject_no_snapshot_branch():
    e, parent, children = _fanout()
    children[0].snapshot = None
    e.run.get(children[0].step_id).snapshot = None
    res = e.judge_and_promote(children, _Critic(_verdict_for(children, 0)))
    assert res["verdict"]["fallback_used"] is True      # can't promote a snapshot-less branch


# ================================================= US3/US4 — record + loop

def test_verdict_recorded_on_parent():
    e, parent, children = _fanout()
    e.judge_and_promote(children, _Critic(_verdict_for(children, 1)))
    rec = e.run.get_verdict(parent)
    assert rec and rec["chosen"] == children[1].step_id and "scores" in rec and rec["reason"]


def test_verdict_record_is_write_once():
    e, parent, children = _fanout()
    e.run.record_verdict(parent, {"chosen": "first", "reason": "one"})
    e.run.record_verdict(parent, {"chosen": "second", "reason": "two"})
    assert e.run.get_verdict(parent)["chosen"] == "first"   # SC-007


def test_second_round_from_promoted_head():
    e, p1, c1 = _fanout()
    r1 = e.judge_and_promote(c1, _Critic(_verdict_for(c1, 0)))
    head1 = e.run.head
    fo2 = e.fan_out(head1, _Strat("echo x > f", "echo y > f"), 2)
    assert fo2.error is None
    r2 = e.judge_and_promote(fo2.children, _Critic(_verdict_for(fo2.children, 1)))
    assert e.run.head == fo2.children[1].step_id
    assert e.run.get_verdict(p1)["chosen"] == c1[0].step_id       # round 1 unchanged (SC-007)
    assert e.run.get_verdict(head1)["chosen"] == fo2.children[1].step_id   # SC-008


def test_fanout_from_loser_refused():
    e, parent, children = _fanout()
    e.judge_and_promote(children, _Critic(_verdict_for(children, 0)))
    loser = children[1].step_id
    fo = e.fan_out(loser, _Strat("echo x > f"), 1)
    assert fo.error in ("released", "unreachable")


def test_replayed_verdict_is_reproducible():
    """SC-011 — the same recorded critic response over the same branch set yields
    the same DECISION and record shape on repeated offline runs (branch ids are
    fresh each run, so compare the decision, not the literal id)."""
    def run_once():
        e, parent, children = _fanout()
        p = {"chosen": children[0].step_id,
             "scores": {c.step_id: 1.0 for c in children},
             "reason": "branch exit 0 output good"}
        e.judge_and_promote(children, _Critic(p))
        rec = e.run.get_verdict(parent)
        return {
            "chose_first": rec["chosen"] == children[0].step_id,
            "head_is_choice": e.run.head == rec["chosen"],
            "fallback_used": rec["fallback_used"],
            "reason_unsupported": rec["reason_unsupported"],
            "n_scores": len(rec["scores"]),
            "losers_released": [e.run.get(c.step_id).state for c in children[1:]],
        }

    assert run_once() == run_once() == {
        "chose_first": True, "head_is_choice": True, "fallback_used": False,
        "reason_unsupported": False, "n_scores": 3, "losers_released": ["released", "released"],
    }


# ================================================= US5 + edges — releases everywhere

def test_release_is_idempotent():
    e, parent, children = _fanout()                     # fan_out already destroyed branch sandboxes
    res = e.judge_and_promote(children, _Critic(_verdict_for(children, 0)))
    assert all(l["released"] and l["error"] is None for l in res["losers"])


def test_release_continues_after_one_failure(monkeypatch):
    e, parent, children = _fanout()
    # give two losers live handles again; make destroy raise for one of them
    e.live[children[1].step_id] = Handle(id="fail-me", sandbox_class="container")
    e.live[children[2].step_id] = Handle(id="ok-me", sandbox_class="container")
    real = e.p.destroy

    def flaky(h):
        if h.id == "fail-me":
            raise RuntimeCallError("boom", "retryable")
        return real(h)

    monkeypatch.setattr(e.p, "destroy", flaky)
    res = e.promote(children[0].step_id, [children[1].step_id, children[2].step_id])
    by = {l["sid"]: l for l in res["losers"]}
    assert by[children[1].step_id] == {"sid": children[1].step_id, "released": False, "error": "retryable"}
    assert by[children[2].step_id]["released"] is True
    assert e.run.head == children[0].step_id            # winner still promoted (SC-009)


def test_headless_safe_on_rederive_failure():
    class _BranchFail(FakeProvider):
        def branch(self, snapshot, n):
            raise RuntimeCallError("no capacity", "capacity")

    e, parent, children = _fanout()
    e.p = _BranchFail()
    res = e.promote(children[0].step_id, [c.step_id for c in children[1:]])
    assert res["error"] == "capacity" and e.run.head == parent   # FR-005-04 — not headless


def test_still_running_branch_excluded():
    e, parent, children = _fanout()
    e.run.get(children[0].step_id).evidence = None      # not finished
    children[0].evidence = None
    ev = e.evaluate(children, _Critic(_verdict_for(children[1:], 0)))
    assert children[0].step_id in ev["excluded"]
    assert children[0].step_id not in ev["scores"]      # FR-005-09 — never scored


def test_empty_set_refused():
    e, parent, children = _fanout()
    ev = e.evaluate([], _Critic(raises=RuntimeError("x")))
    assert ev["error"] == "no branches"


def test_single_branch_promoted_no_verdict():
    e, parent, children = _fanout()
    critic = _Critic(raises=RuntimeError("must not be called"))
    ev = e.evaluate([children[0]], critic)
    assert ev["fallback_trigger"] == "single-branch" and critic.calls == 0


def test_provider_call_counts():
    e, parent, children = _fanout()
    e.p.calls.clear()
    e.judge_and_promote(children, _Critic(_verdict_for(children, 0)))
    counts = Counter(c.operation for c in e.p.calls)
    assert counts.get("branch", 0) == 1                 # winner re-derived; losers already gone
    assert counts.get("run", 0) == 0
