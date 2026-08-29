"""src/rewind/engine.py — the checkpoint tree and the loop. No SDK imports."""

import uuid
from dataclasses import dataclass, field

from .ports import Checkpoint, ExecResult, Handle, SandboxProvider


@dataclass
class Run:
    """FR-001 — the tree."""
    checkpoints: dict[str, Checkpoint] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    head: str | None = None

    def add(self, cp: Checkpoint) -> str:
        cp.step_id = cp.step_id or uuid.uuid4().hex[:8]
        self.checkpoints[cp.step_id] = cp
        self.order.append(cp.step_id)
        if cp.parent_id and cp.parent_id in self.checkpoints:
            self.checkpoints[cp.parent_id].children.append(cp.step_id)
        self.head = cp.step_id
        return cp.step_id

    def path_to(self, step_id: str) -> list[Checkpoint]:
        """Lineage from root to step_id — the replay history."""
        out, cur = [], self.checkpoints.get(step_id)
        while cur:
            out.append(cur)
            cur = self.checkpoints.get(cur.parent_id) if cur.parent_id else None
        return list(reversed(out))

    def as_tree(self) -> dict:
        """FR-001-07 — renderable without further computation."""
        return {
            "head": self.head,
            "nodes": [
                {
                    "id": c.step_id, "index": c.index, "instruction": c.instruction,
                    "parent": c.parent_id, "sandbox": c.sandbox_id, "state": c.state,
                    "exit_code": c.evidence.exit_code if c.evidence else None,
                    "stdout": (c.evidence.stdout[:400] if c.evidence else ""),
                    "rationale": c.rationale, "children": c.children,
                }
                for c in (self.checkpoints[i] for i in self.order)
            ],
        }


class Engine:
    def __init__(self, provider: SandboxProvider, max_branches: int = 3):
        self.p = provider
        self.run = Run()
        self.max_branches = max_branches
        self.live: dict[str, Handle] = {}          # step_id -> handle

    # ---------------------------------------------------------------- stepping
    def start(self) -> Handle:
        h = self.p.spawn()
        cp = Checkpoint(index=0, step_id="root", instruction="(start)",
                        parent_id=None, sandbox_id=h.id)
        cp.snapshot = self.p.checkpoint(h)
        self.run.add(cp)
        self.live["root"] = h
        return h

    def step(self, instruction: str, rationale: str = "") -> Checkpoint:
        """FR-002 — execute, capture evidence, checkpoint."""
        parent = self.run.head
        h = self.live[parent]
        result: ExecResult = self.p.run(h, instruction)

        cp = Checkpoint(
            index=len(self.run.order), step_id="", instruction=instruction,
            parent_id=parent, sandbox_id=h.id, evidence=result, rationale=rationale,
        )
        if result.ok:
            cp.snapshot = self.p.checkpoint(h)     # only checkpoint good states
        sid = self.run.add(cp)
        self.live[sid] = h
        return cp

    # ---------------------------------------------------------------- branching
    def branch_from(self, step_id: str, strategies: list[str]) -> list[Checkpoint]:
        """FR-004 — N isolated children from one checkpoint, in parallel."""
        cp = self.run.checkpoints[step_id]
        if cp.state != "live":
            raise ValueError(f"checkpoint {step_id} is {cp.state}")
        if not cp.snapshot:
            raise ValueError(f"checkpoint {step_id} has no snapshot to branch from")

        strategies = strategies[: self.max_branches]
        handles = self.p.branch(cp.snapshot, len(strategies))

        out = []
        for h, strat in zip(handles, strategies):
            res = self.p.run(h, strat)
            child = Checkpoint(
                index=len(self.run.order), step_id="", instruction=strat,
                parent_id=step_id, sandbox_id=h.id, snapshot=cp.snapshot, evidence=res,
            )
            sid = self.run.add(child)
            self.live[sid] = h
            out.append(child)
        self.run.head = step_id                    # head only moves on promotion
        return out

    def promote(self, winner_step_id: str, losers: list[str]) -> None:
        """FR-005-04/05 — winner becomes head, losers released."""
        self.run.head = winner_step_id
        for sid in losers:
            self.run.checkpoints[sid].state = "released"
            h = self.live.pop(sid, None)
            if h:
                self.p.destroy(h)

    def shutdown(self) -> None:
        """FR-000-09 — nothing survives us."""
        seen = set()
        for sid, h in list(self.live.items()):
            if h.id not in seen:
                seen.add(h.id)
                self.p.destroy(h)
        self.live.clear()


def rank_by_evidence(branches: list[Checkpoint]) -> dict:
    """FR-005-07 — deterministic fallback. Pure function, no model needed."""
    scored = sorted(
        enumerate(branches),
        key=lambda t: (t[1].evidence.exit_code if t[1].evidence else 99,
                       t[1].evidence.elapsed if t[1].evidence else 1e9),
    )
    best = scored[0][0]
    return {
        "winner": best,
        "scores": [{"branch": i, "exit_code": b.evidence.exit_code if b.evidence else None}
                   for i, b in enumerate(branches)],
        "reason": f"branch {best} exited {branches[best].evidence.exit_code} fastest",
        "provider": "deterministic-fallback",
    }
