"""src/rewind/engine.py — the checkpoint tree and the loop. No SDK imports."""

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import capabilities
from .ports import Checkpoint, ExecResult, Handle, SandboxProvider
from .reasoning import ReasoningPort, SchemaError, validate

_MIN_ELAPSED = 1e-6          # a step that ran has elapsed > 0 (spec 002 FR-002-03)

# spec 004 FR-004-03 — fastest branch derivation first; first one the verified
# capability map declares wins, the rest are fallbacks.
_DERIVATION_PREFERENCE = ("fork", "branch")


class BranchHalted(RuntimeError):
    """Raised when a step is requested on a branch that has halted
    (spec 002 FR-002-06 / FR-002-07)."""


# --- spec 003: restore to checkpoint ---------------------------------------------


@dataclass(frozen=True)
class RestoreCheck:
    """What the caller wants proven in the restored sandbox (spec 003 FR-003-02).
    `before` markers must be PRESENT; `after` markers must be ABSENT."""
    before: list[tuple[str, str]] = field(default_factory=list)
    after: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class RestoreVerification:
    status: str = "not-checked"        # verified | not-verified | not-checked
    before: list[dict] = field(default_factory=list)   # {command, marker, observed, passed}
    after: list[dict] = field(default_factory=list)


@dataclass
class RestoreResult:
    checkpoint_id: str
    sandbox_id: str | None
    elapsed_seconds: float
    verification: RestoreVerification
    error: str | None = None          # None | "unknown" | "released" | "unreachable" | <runtime msg>
    head_moved: bool = False

    def as_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "sandbox_id": self.sandbox_id,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "error": self.error,
            "head_moved": self.head_moved,
            "verification": {
                "status": self.verification.status,
                "before": self.verification.before,
                "after": self.verification.after,
            },
        }


# --- spec 004: branch fan-out --------------------------------------------------


@dataclass
class BranchProgress:
    """FR-004-07 — live per-branch report. `sandbox_id` is the runtime's own."""
    checkpoint_id: str
    sandbox_id: str | None
    state: str                        # creating | running | done | failed


@dataclass
class FanOutResult:
    children: list                    # list[Checkpoint], one per branch that ran
    ran: int
    requested: int
    derivation: str                   # "fork" | "branch" — which was used
    elapsed_seconds: float
    progress: list                    # list[dict] — final BranchProgress entries
    error: str | None = None          # set only on a pre-branch refusal

    def as_dict(self) -> dict:
        return {
            "ran": self.ran,
            "requested": self.requested,
            "derivation": self.derivation,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "error": self.error,
            "children": [c.step_id for c in self.children],
            "progress": [dict(p) for p in self.progress],
        }


@dataclass
class Run:
    """FR-001 — the tree."""
    checkpoints: dict[str, Checkpoint] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    head: str | None = None

    # id assignment is random, never time-derived (spec 001 NFR-001-03).
    def add(self, cp: Checkpoint) -> str:
        cp.step_id = cp.step_id or uuid.uuid4().hex[:8]
        if not cp.created_at:                              # respect a caller-supplied time
            cp.created_at = datetime.now(timezone.utc).isoformat()
        self.checkpoints[cp.step_id] = cp
        self.order.append(cp.step_id)
        if cp.parent_id and cp.parent_id in self.checkpoints:
            self.checkpoints[cp.parent_id].children.append(cp.step_id)
        self.head = cp.step_id
        return cp.step_id

    def get(self, step_id: str) -> Checkpoint | None:
        """Non-raising lookup. An id that was never issued returns None."""
        return self.checkpoints.get(step_id)

    def path_to(self, step_id: str) -> list[Checkpoint]:
        """Lineage from root to step_id — the replay history (FR-001-01 §2)."""
        out, cur = [], self.checkpoints.get(step_id)
        while cur:
            out.append(cur)
            cur = self.checkpoints.get(cur.parent_id) if cur.parent_id else None
        return list(reversed(out))

    # ---- restorability (spec 001 FR-001-08) -----------------------------------
    def is_restorable(self, step_id: str) -> bool:
        cp = self.checkpoints.get(step_id)
        return cp is not None and cp.state == "live" and cp.snapshot is not None

    def restore_targets(self) -> list[str]:
        return [sid for sid in self.order if self.is_restorable(sid)]

    def set_head(self, step_id: str) -> None:
        """FR-001-08 — refuse an invalid head; a released/unreachable checkpoint
        is never a valid target."""
        cp = self.checkpoints.get(step_id)
        if cp is None:
            raise ValueError(f"unknown checkpoint {step_id!r}")
        if cp.state != "live":
            raise ValueError(f"checkpoint {step_id!r} is {cp.state}, not a valid head")
        if cp.snapshot is None:
            raise ValueError(f"checkpoint {step_id!r} has no runtime state to return to")
        self.head = step_id

    # ---- branch terminal outcome (spec 001 FR-001-09) -----------------------
    def mark_terminal(self, step_id: str, outcome: str) -> None:
        if outcome not in ("succeeded", "failed", "abandoned"):
            raise ValueError(f"terminal outcome must be succeeded|failed|abandoned, got {outcome!r}")
        self.checkpoints[step_id].terminal = outcome

    def branch_outcome(self, step_id: str) -> str | None:
        cp = self.checkpoints.get(step_id)
        return cp.terminal if cp else None

    # ---- verdict record (spec 005 FR-005-06) — write-once per parent -------
    def record_verdict(self, parent_id: str, record: dict) -> dict:
        cp = self.checkpoints[parent_id]
        if cp.verdict is None:
            cp.verdict = dict(record)
        return cp.verdict                              # existing one wins — SC-007

    def get_verdict(self, parent_id: str) -> dict | None:
        cp = self.checkpoints.get(parent_id)
        return cp.verdict if cp else None

    # ---- structural integrity (spec 001 NFR-001-02 / SC-010) ---------------
    def check_integrity(self) -> list[str]:
        problems: list[str] = []
        roots = [sid for sid, c in self.checkpoints.items() if c.parent_id is None]
        if len(roots) != 1:
            problems.append(f"expected exactly one root, found {len(roots)}")
        elif self.checkpoints[roots[0]].index != 0:
            problems.append("root is not at index 0")
        if not self.head or self.head not in self.checkpoints:
            problems.append(f"head {self.head!r} is not a known checkpoint")
        for sid, c in self.checkpoints.items():
            if c.parent_id is not None and c.parent_id not in self.checkpoints:
                problems.append(f"{sid}: parent {c.parent_id!r} does not resolve")
            elif c.parent_id is not None and sid not in self.checkpoints[c.parent_id].children:
                problems.append(f"{sid}: parent {c.parent_id} does not list it as a child")
            for ch in c.children:
                if ch not in self.checkpoints:
                    problems.append(f"{sid}: child {ch!r} does not resolve")
                elif self.checkpoints[ch].parent_id != sid:
                    problems.append(f"{sid}: child {ch} does not point back to it")
        # reachability from root + cycle check
        if len(roots) == 1:
            seen, stack = set(), [roots[0]]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    problems.append(f"cycle detected at {cur}")
                    break
                seen.add(cur)
                stack.extend(self.checkpoints[cur].children)
            missing = set(self.checkpoints) - seen
            if missing:
                problems.append(f"unreachable from root: {sorted(missing)}")
        return problems

    def as_tree(self) -> dict:
        """FR-001-07 — one form, renderable without further computation."""
        return {
            "head": self.head,
            "nodes": [
                {
                    "id": c.step_id, "index": c.index, "instruction": c.instruction,
                    "parent": c.parent_id, "children": c.children,
                    "sandbox": c.sandbox_id, "state": c.state, "snapshot": c.snapshot,
                    "created_at": c.created_at,
                    "exit_code": c.evidence.exit_code if c.evidence else None,
                    "stdout": (c.evidence.stdout[:400] if c.evidence else ""),
                    "outcome": c.outcome, "terminal": c.terminal,
                    "rationale": c.rationale,
                }
                for c in (self.checkpoints[i] for i in self.order)
            ],
        }


class Engine:
    def __init__(self, provider: SandboxProvider, max_branches: int = 3,
                 max_steps: int | None = None):
        self.p = provider
        self.run = Run()
        self.max_branches = max_branches
        # FR-002-07 — one declared step bound, read in exactly one place.
        self.max_steps = int(os.environ.get("MAX_STEPS", 50)) if max_steps is None else max_steps
        self.live: dict[str, Handle] = {}          # step_id -> handle
        self.halted = False                        # FR-002-06 / FR-002-07
        self.halt_reason: str | None = None        # "step-failed" | "step-bound"
        self._t0 = time.time()                     # spec 006 — session start

    def _steps_in_branch(self) -> int:
        """Non-root checkpoints on the current lineage."""
        if not self.run.head:
            return 0
        return sum(1 for c in self.run.path_to(self.run.head) if c.parent_id is not None)

    # ---------------------------------------------------------------- stepping
    def start(self) -> Handle:
        h = self.p.spawn()
        cp = Checkpoint(index=0, step_id="root", instruction="(start)",
                        parent_id=None, sandbox_id=h.id)
        cp.snapshot = self.p.checkpoint(h)
        self.run.add(cp)
        self.live["root"] = h
        return h

    def _guard(self) -> None:
        """FR-002-06 / FR-002-07 — no step runs on a halted or maxed-out branch."""
        if self.halted:
            raise BranchHalted(self.halt_reason or "halted")
        if self._steps_in_branch() >= self.max_steps:
            self.halted = True
            if self.halt_reason is None:
                self.halt_reason = "step-bound"
            raise BranchHalted("step-bound")

    def next_step(self, reasoner: ReasoningPort, context: str = "") -> Checkpoint:
        """FR-002-01/02 — pull a structured instruction, validate it, execute it.
        A SchemaError from validate() propagates: nothing runs, no checkpoint."""
        self._guard()
        raw = reasoner.next_instruction(context)
        instr = validate(raw)                       # SchemaError => no execution
        return self.step(instr.instruction, instr.rationale)

    def step(self, instruction: str, rationale: str = "") -> Checkpoint:
        """FR-002 — execute, capture evidence, checkpoint."""
        self._guard()
        parent = self.run.head
        h = self.live[parent]

        t0 = time.time()
        result: ExecResult = self.p.run(h, instruction)   # the SOLE evidence
        if result.elapsed <= 0:                           # FR-002-03 — a step that ran took time
            result.elapsed = max(time.time() - t0, _MIN_ELAPSED)

        cp = Checkpoint(
            index=len(self.run.order), step_id="", instruction=instruction,
            parent_id=parent, sandbox_id=h.id, evidence=result, rationale=rationale,
        )
        if result.ok:
            cp.snapshot = self.p.checkpoint(h)     # only checkpoint good states
        sid = self.run.add(cp)
        self.live[sid] = h

        if not result.ok:                          # FR-002-06 — halt, keep history
            cp.halt_reason = "step-failed"
            cp.terminal = "failed"                 # spec 001 FR-001-09
            self.halted = True
            self.halt_reason = "step-failed"
        return cp

    # ---------------------------------------------------------------- branching (spec 004)
    def _select_derivation(self) -> str:
        """FR-004-03 — the fastest branch derivation the capability map declares."""
        for d in _DERIVATION_PREFERENCE:
            if d in capabilities.VERIFIED_OPS:
                self._last_derivation = d
                return d
        self._last_derivation = "branch"
        return "branch"

    def branch_from(self, step_id: str, strategies: list[str], *,
                    rationales: list[str] | None = None, observer=None) -> list[Checkpoint]:
        """FR-004 — N isolated children from one checkpoint, run concurrently.
        Each branch sandbox is destroyed before return, on every path (FR-004-10);
        the run head is not moved (FR-004-05)."""
        cp = self.run.checkpoints[step_id]
        if cp.state != "live":
            raise ValueError(f"checkpoint {step_id} is {cp.state}")
        if not cp.snapshot:
            raise ValueError(f"checkpoint {step_id} has no snapshot to branch from")

        strategies = list(strategies)[: self.max_branches]
        rationales = list(rationales or [])[: len(strategies)]
        rationales += [""] * (len(strategies) - len(rationales))
        n = len(strategies)

        self._select_derivation()                     # FR-004-03 — records self._last_derivation
        handles = self.p.branch(cp.snapshot, n)       # concurrent creation
        made = len(handles)                           # may be < n if the ceiling had no room

        lock = threading.Lock()
        progress = [BranchProgress("", (handles[i].id if i < made else None),
                                   "creating" if i < made else "failed")
                    for i in range(n)]

        def _emit():
            if observer:
                observer([dict(p.__dict__) for p in progress])

        _emit()
        results: list[Checkpoint | None] = [None] * n

        def _one(i: int) -> None:
            h, strat = handles[i], strategies[i]
            with lock:
                progress[i].state = "running"
            _emit()
            term = None
            try:
                res = self.p.run(h, strat)           # FR-004-06 — independent evidence
            except Exception as e:                   # noqa: BLE001  FR-004-08 — isolate
                res = ExecResult(1, str(getattr(e, "error_class", None) or e), 0.0)
            snap = None
            if res.ok:
                try:
                    snap = self.p.checkpoint(h)      # each branch's OWN snapshot
                except Exception:                    # noqa: BLE001
                    snap = None
            else:
                term = "failed"
            child = Checkpoint(
                index=0, step_id="", instruction=strat, parent_id=step_id,
                sandbox_id=h.id, snapshot=snap, evidence=res, rationale=rationales[i],
            )
            if term:
                child.terminal = term
            with lock:
                progress[i].state = "failed" if term else "done"
            _emit()
            results[i] = child

        try:                                          # FR-004-04 — concurrent execution
            with ThreadPoolExecutor(max_workers=max(1, made)) as ex:
                list(ex.map(_one, range(made)))
        finally:                                       # FR-004-10 — every path
            for h in handles:
                try:
                    self.p.destroy(h)
                except Exception:                     # noqa: BLE001
                    pass

        for i in range(made, n):                       # branches the ceiling had no room for
            results[i] = Checkpoint(
                index=0, step_id="", instruction=strategies[i], parent_id=step_id,
                sandbox_id=None, snapshot=None,
                evidence=ExecResult(1, "capacity: concurrency ceiling reached", 0.0),
                rationale=rationales[i],
            )
            results[i].terminal = "failed"

        out: list[Checkpoint] = []
        for i, child in enumerate(results):
            child.index = len(self.run.order)
            sid = self.run.add(child)                  # FR-004-05 — child of the parent
            progress[i].checkpoint_id = sid
            out.append(child)
        self.run.head = step_id                        # FR-004-05 — head unchanged
        self._fan_progress = [dict(p.__dict__) for p in progress]
        _emit()
        return out

    def fan_out(self, step_id: str, reasoner: ReasoningPort, n: int,
                context: str = "", observer=None) -> FanOutResult:
        """FR-004-01 — pull N structured strategies from the strategist, then run
        the fan-out. Business refusals are returned, not raised."""
        t0 = time.time()

        def _fail(err: str) -> FanOutResult:
            return FanOutResult(children=[], ran=0, requested=n,
                                derivation=getattr(self, "_last_derivation", "branch"),
                                elapsed_seconds=time.time() - t0, progress=[], error=err)

        cp = self.run.get(step_id)
        if cp is None:
            return _fail("unknown")
        if cp.state != "live":
            return _fail(cp.state if cp.state in ("released", "unreachable") else "unreachable")
        if cp.snapshot is None:
            return _fail("unreachable")

        cap_n = min(n, self.max_branches)
        strategies: list = []
        seen: set[str] = set()
        try:
            for _ in range(cap_n):
                instr = validate(reasoner.next_instruction(context))
                if instr.instruction not in seen:
                    seen.add(instr.instruction)
                    strategies.append(instr)
        except SchemaError:
            raise                                     # non-conforming strategy — nothing created
        except Exception as e:                        # noqa: BLE001  strategist unreachable
            return _fail(str(e))

        if not strategies:
            return _fail("no-strategies")

        children = self.branch_from(
            step_id, [s.instruction for s in strategies],
            rationales=[s.rationale for s in strategies], observer=observer)
        return FanOutResult(
            children=children, ran=len(children), requested=n,
            derivation=self._last_derivation, elapsed_seconds=time.time() - t0,
            progress=list(self._fan_progress), error=None)

    # ---------------------------------------------------------------- promotion (spec 005)
    def _evidence_bundle(self, branches: list[Checkpoint]) -> str:
        """FR-005-01 — evidence ONLY. No rationale, no agent narration."""
        parts = []
        for b in branches:
            ev = b.evidence
            ex = ev.exit_code if ev else None
            el = round(ev.elapsed, 3) if ev else None
            out = (ev.stdout[:800] if ev else "")
            parts.append(f"branch {b.step_id} | exit {ex} | elapsed {el}s\noutput:\n{out}\n---")
        return "\n".join(parts)

    def evaluate(self, branches: list[Checkpoint], critic, context: str = "") -> dict:
        """FR-005-02/03/07/09/10 — bundle the evidence, ask the critic within a
        bounded wait, validate the verdict, fall back deterministically."""
        from concurrent.futures import TimeoutError as _FTimeout
        from .reasoning import VerdictSchemaError, validate_verdict

        def _r(**kw):
            kw.setdefault("excluded", []); kw.setdefault("error", None)
            kw.setdefault("reason_unsupported", False)
            kw.setdefault("fallback_used", False); kw.setdefault("fallback_trigger", None)
            kw.setdefault("served_by", "primary")           # spec 008 FR-008-04/06
            return kw

        if not branches:
            return _r(chosen=None, scores={}, reason="no branches", error="no branches")

        # FR-005-09 — a branch with no evidence yet is excluded, never scored.
        excluded = [b.step_id for b in branches if b.evidence is None]
        judged = [b for b in branches if b.evidence is not None]
        eligible = [b for b in judged if b.snapshot]
        if not eligible:
            return _r(chosen=None, scores={}, reason="no branch has a snapshot to promote",
                      excluded=excluded, error="no snapshot on any branch")

        if len(eligible) == 1:                          # FR-005-10 — single branch, no critic
            b = eligible[0]
            return _r(chosen=b.step_id, scores={b.step_id: 0.0},
                      reason="single branch — promoted without a verdict",
                      excluded=excluded, fallback_used=True, fallback_trigger="single-branch")

        ids = [b.step_id for b in eligible]

        def _fallback(trigger: str) -> dict:
            fr = rank_by_evidence(eligible)
            sc = {eligible[i].step_id: fr["scores"][i].get("score", 0.0)
                  for i in range(len(eligible))}
            return _r(chosen=eligible[fr["winner"]].step_id, scores=sc, reason=fr["reason"],
                      excluded=excluded, fallback_used=True, fallback_trigger=trigger,
                      served_by="deterministic-fallback")

        ex = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(critic.next_instruction, context or self._evidence_bundle(eligible))
        try:
            raw = fut.result(timeout=capabilities.CRITIC_WAIT)
        except _FTimeout:
            fut.cancel()
            ex.shutdown(wait=False, cancel_futures=True)   # do NOT block on a hung critic
            return _fallback("critic-timeout")
        except Exception as e:                          # noqa: BLE001
            ex.shutdown(wait=False, cancel_futures=True)
            return _fallback(f"critic-unreachable: {e}")
        ex.shutdown(wait=False)

        try:
            v = validate_verdict(raw, ids)
        except VerdictSchemaError as e:
            return _fallback(f"verdict-rejected: {e}")
        return _r(chosen=v.chosen, scores=v.scores, reason=v.reason,
                  reason_unsupported=v.reason_unsupported, excluded=excluded,
                  served_by=getattr(critic, "last_served_by", "primary"))   # spec 008

    def promote(self, winner_step_id: str, losers: list[str], *,
                verdict: dict | None = None, parent_id: str | None = None) -> dict:
        """FR-005-04/05/06 — winner becomes head (re-derived from its own snapshot),
        losers released (idempotent, continue-on-failure), verdict recorded.
        Positional `promote(winner, losers)` stays valid for existing callers."""
        win = self.run.checkpoints[winner_step_id]
        error = None
        if winner_step_id not in self.live and win.snapshot:
            try:                                        # FR-005-04 — headless-safe
                self.live[winner_step_id] = self.p.branch(win.snapshot, 1)[0]
            except Exception as e:                      # noqa: BLE001
                error = str(getattr(e, "error_class", None) or e)
        if error is None:
            self.run.head = winner_step_id              # move head only on a clean re-derive

        loser_results = []
        for sid in losers:                              # FR-005-05 — idempotent, continue-on-failure
            cp = self.run.checkpoints.get(sid)
            if cp is not None:
                cp.state = "released"
                cp.terminal = "abandoned"
            h = self.live.pop(sid, None)
            rel, err = True, None
            if h is not None:
                try:
                    self.p.destroy(h)
                except Exception as e:                  # noqa: BLE001
                    rel, err = False, str(getattr(e, "error_class", None) or e)
            loser_results.append({"sid": sid, "released": rel, "error": err})

        recorded = False
        if verdict is not None and parent_id is not None and parent_id in self.run.checkpoints:
            self.run.record_verdict(parent_id, verdict)
            recorded = True

        return {"head": self.run.head, "winner": winner_step_id,
                "losers": loser_results, "verdict_recorded": recorded, "error": error}

    def judge_and_promote(self, branches: list[Checkpoint], critic,
                          context: str = "", parent_id: str | None = None) -> dict:
        """FR-005 — one turn of the loop: evaluate the branches, promote the winner,
        record the verdict against the common parent."""
        import datetime as _dt

        if parent_id is None and branches:
            parents = {b.parent_id for b in branches if b.parent_id}
            parent_id = next(iter(parents)) if len(parents) == 1 else None

        ev = self.evaluate(branches, critic, context)
        if ev["error"]:
            return {"head": self.run.head, "error": ev["error"], "evaluate": ev, "verdict": None}

        record = {
            "chosen": ev["chosen"], "scores": ev["scores"], "reason": ev["reason"],
            "reason_unsupported": ev["reason_unsupported"],
            "fallback_used": ev["fallback_used"], "fallback_trigger": ev["fallback_trigger"],
            "excluded": ev["excluded"],
            "served_by": ev.get("served_by", "primary"),   # spec 008 FR-008-04/06
            "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        others = [b.step_id for b in branches if b.step_id != ev["chosen"]]
        res = self.promote(ev["chosen"], others, verdict=record, parent_id=parent_id)
        return {**res, "verdict": self.run.get_verdict(parent_id) or record, "evaluate": ev}

    def shutdown(self) -> None:
        """FR-000-09 — nothing survives us."""
        seen = set()
        for sid, h in list(self.live.items()):
            if h.id not in seen:
                seen.add(h.id)
                self.p.destroy(h)
        self.live.clear()

    # ---------------------------------------------------------------- restore (spec 003)
    def _verify_restore(self, handle, check: "RestoreCheck | None") -> RestoreVerification:
        """FR-003-02 — read state written before the checkpoint (must be present)
        and check state written after it (must be absent). Never infers success."""
        if check is None or (not check.before and not check.after):
            return RestoreVerification("not-checked")
        before_rows, after_rows = [], []
        for cmd, marker in check.before:
            out = self.p.run(handle, cmd).stdout
            before_rows.append({"command": cmd, "marker": marker,
                                "observed": out[:200], "passed": marker in out})
        for cmd, marker in check.after:
            out = self.p.run(handle, cmd).stdout
            after_rows.append({"command": cmd, "marker": marker,
                               "observed": out[:200], "passed": marker not in out})
        complete = bool(before_rows) and bool(after_rows)
        all_pass = all(r["passed"] for r in before_rows + after_rows)
        status = "verified" if (complete and all_pass) else "not-verified"
        return RestoreVerification(status, before_rows, after_rows)

    def restore(self, checkpoint_id: str,
                verify: "RestoreCheck | None" = None) -> RestoreResult:
        """FR-003 — re-materialise a sandbox from a checkpoint's captured state,
        prove it, move the head, keep the tail, release the old sandbox, report
        the elapsed time. Business refusals are returned, not raised."""
        t0 = time.time()

        def _res(**kw):
            kw.setdefault("verification", RestoreVerification("not-checked"))
            return RestoreResult(checkpoint_id=checkpoint_id,
                                 elapsed_seconds=time.time() - t0, **kw)

        cp = self.run.get(checkpoint_id)
        if cp is None:                                     # FR-003-05
            return _res(sandbox_id=None, error="unknown")
        if cp.state == "released":
            return _res(sandbox_id=None, error="released")
        if cp.state == "unreachable" or cp.snapshot is None:
            return _res(sandbox_id=None, error="unreachable")

        old_head = self.run.head
        try:                                              # FR-003-01
            new = self.p.branch(cp.snapshot, 1)[0]
        except Exception as e:                            # noqa: BLE001
            return _res(sandbox_id=None,
                        error=str(getattr(e, "error_class", None) or e))

        verification = self._verify_restore(new, verify)  # FR-003-02

        already_head = (old_head == checkpoint_id)
        self.run.set_head(checkpoint_id)                  # FR-003-03 (spec 001 mechanism)
        self.live[checkpoint_id] = new

        # FR-003-07 — the working path is now the lineage of the restored
        # checkpoint. Any handle held for a checkpoint off that path (the old
        # head and anything between) is released, once no kept checkpoint still
        # refers to the same sandbox. Snapshots are never touched (FR-003-04).
        keep = {c.step_id for c in self.run.path_to(checkpoint_id)}
        kept_ids = {self.live[s].id for s in keep if s in self.live}
        for sid in [s for s in list(self.live) if s not in keep]:
            h = self.live.pop(sid)
            if h.id not in kept_ids and h.id not in {x.id for x in self.live.values()}:
                self.p.destroy(h)

        return _res(sandbox_id=new.id, verification=verification,
                    error=None, head_moved=not already_head)


def console_fixture(engine: "Engine", *, verdict: dict | None = None) -> dict:
    """spec 006 — the run tree (Spec 001 `as_tree`) enriched with the operational
    numbers and per-branch progress the timeline console renders. Pure read: no
    network, no provider lifecycle call (NFR-006-01)."""
    tree = engine.run.as_tree()

    prog_by_cp = {p.get("checkpoint_id"): p
                  for p in (getattr(engine, "_fan_progress", None) or [])}

    if prog_by_cp:                                       # authoritative — set by branch_from
        branch_ids = set(prog_by_cp)
    else:                                                # fallback heuristic for bare fixtures
        branch_ids = set()
        by_parent: dict[str, list[str]] = {}
        for n in tree["nodes"]:
            if n["parent"] is not None:
                by_parent.setdefault(n["parent"], []).append(n["id"])
        for kids in by_parent.values():
            if len(kids) > 1:
                branch_ids.update(kids[1:] if len(kids) > 2 else kids)

    for n in tree["nodes"]:                              # FR-006-05 — branch nodes only
        if n["id"] in branch_ids:
            p = prog_by_cp.get(n["id"], {})
            cp = engine.run.checkpoints.get(n["id"])
            elapsed = 0.0
            if cp is not None and cp.evidence is not None:
                elapsed = round(float(getattr(cp.evidence, "elapsed", 0.0) or 0.0), 3)
            n["branch"] = True
            n["progress"] = {
                "state": p.get("state") or n.get("terminal") or n.get("state") or "done",
                "elapsed_seconds": elapsed,
            }

    prov = getattr(engine, "p", None)
    live = None
    for attr in ("live", "_live"):
        live = getattr(prov, attr, None)
        if live is not None:
            break
    if live is None:
        live = engine.live
    tree["live_sandboxes"] = len(live)                   # FR-006-07 / C2
    tree["session_elapsed"] = round(time.time() - getattr(engine, "_t0", time.time()), 2)
    tree["runtime_version"] = capabilities.RUNTIME_VERSION
    if verdict is None:                                  # spec 005 — surface a recorded verdict
        for cp in reversed(engine.run.path_to(engine.run.head)):
            if getattr(cp, "verdict", None):
                verdict = cp.verdict
                break
    tree["verdict"] = verdict                            # C5 — verbatim, recorded, or None
    return tree


def rank_by_evidence(branches: list[Checkpoint]) -> dict:
    """FR-005-07 / NFR-005-02 — the deterministic fallback. A PURE function and
    TOTAL over any non-empty branch set (all-failed included). Tie-break:
    exit status, then elapsed, then index, then id — reproducible for rehearsal."""
    def _ex(b):  return b.evidence.exit_code if b.evidence else 99
    def _el(b):  return b.evidence.elapsed if b.evidence else 1e9

    order = sorted(range(len(branches)),
                   key=lambda i: (_ex(branches[i]), _el(branches[i]), i, branches[i].step_id))
    best = order[0]
    tie = (len(order) > 1
           and (_ex(branches[best]), _el(branches[best]))
           == (_ex(branches[order[1]]), _el(branches[order[1]])))
    if all(_ex(b) != 0 for b in branches):
        reason = f"no branch exited 0; branch {best} is least-bad (exit {_ex(branches[best])})"
    else:
        reason = f"branch {best} exited {_ex(branches[best])} fastest"
    if tie:
        reason += " — tie broken on branch order"
    return {
        "winner": best,
        "scores": [{"branch": i, "exit_code": (b.evidence.exit_code if b.evidence else None),
                    "score": -(_ex(b) * 1e6) - _el(b)}
                   for i, b in enumerate(branches)],
        "reason": reason,
        "provider": "deterministic-fallback",
    }
