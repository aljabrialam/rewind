"""src/rewind/ports.py — the seam. Nothing downstream imports the Daytona SDK."""

from dataclasses import dataclass, field
from typing import Protocol

WORKSPACE = "/home/daytona/work"          # verified: /work is not writable


@dataclass
class Handle:
    id: str
    parent_id: str | None = None
    snapshot: str | None = None           # the checkpoint this was created from


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class Checkpoint:
    """FR-001-01..07 — a node in the run tree."""
    index: int
    step_id: str
    instruction: str
    parent_id: str | None
    sandbox_id: str | None = None
    snapshot: str | None = None
    evidence: ExecResult | None = None
    rationale: str = ""
    state: str = "live"                   # live | released | unreachable
    children: list[str] = field(default_factory=list)


class SandboxProvider(Protocol):
    def spawn(self) -> Handle: ...
    def run(self, h: Handle, cmd: str) -> ExecResult: ...
    def checkpoint(self, h: Handle) -> str: ...          # snapshot name
    def branch(self, snapshot: str, n: int) -> list[Handle]: ...
    def destroy(self, h: Handle) -> None: ...


class LLMClient(Protocol):
    def complete(self, prompt: str, schema: dict) -> dict: ...
