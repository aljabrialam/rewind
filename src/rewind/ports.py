"""src/rewind/ports.py — the seam. Nothing downstream imports the Daytona SDK.

Importing this module validates the sandbox capability contract: if the code
below declares a lifecycle operation that the verified capability map does not
contain, `capabilities.assert_declared` raises `CapabilityError` here, at load
time (spec FR-000-02, FR-000-03, NFR-000-01).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Mapping, Protocol

from . import capabilities

WORKSPACE = "/home/daytona/work"          # verified: /work is not writable

# The lifecycle operations this seam exposes. Every name here MUST be in the
# verified capability map — checked at the bottom of this module.
PORT_OPERATIONS: tuple[str, ...] = ("spawn", "run", "checkpoint", "branch", "destroy")

SandboxClass = Literal["container", "vm"]
ErrorClass = Literal["retryable", "capacity", "terminal"]


@dataclass
class Handle:
    id: str
    parent_id: str | None = None
    snapshot: str | None = None           # the checkpoint this was created from
    sandbox_class: str | None = None      # tagged at creation for assert_class (FR-000-04)
    state: str = "creating"               # creating | ready | failed | released | leaked


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


@dataclass
class CallRecord:
    """FR-000-07 — one entry per runtime call, retained for the session."""
    operation: str
    outcome: str                          # "ok" | "error"
    elapsed_seconds: float
    error_class: ErrorClass | None = None
    waited_seconds: float = 0.0           # time in a bounded readiness/ceiling wait
    retries: int = 0                      # bounded-retry attempts consumed


class RuntimeCallError(RuntimeError):
    """A failed runtime call, carrying its classification (spec FR-000-10)."""

    def __init__(self, message: str, error_class: ErrorClass):
        super().__init__(message)
        self.error_class: ErrorClass = error_class


@dataclass
class UnconfirmedDestroyLeak:
    """FR-000-09 — a sandbox whose destruction could not be confirmed. Keeps a
    concurrency permit held until a later sweep confirms it is gone."""
    sandbox_id: str
    retries_attempted: int
    first_seen: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    still_counts: bool = True


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
    state: str = "live"                   # live | released | unreachable  (spec 001 FR-001-08)
    children: list[str] = field(default_factory=list)
    halt_reason: str | None = None        # "step-failed" | "step-bound" (spec 002 FR-002-06/07)
    created_at: str = field(              # spec 001 FR-001-06 — display + tie-break only
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    terminal: str | None = None           # "succeeded" | "failed" | "abandoned" (spec 001 FR-001-09)
    verdict: dict | None = None           # spec 005 FR-005-06 — write-once critic verdict record (parent only)

    @property
    def outcome(self) -> str:
        """FR-002-04 — derived from evidence ONLY, never from rationale."""
        return "ok" if (self.evidence is not None and self.evidence.ok) else "failed"


class SandboxProvider(Protocol):
    def spawn(self) -> Handle: ...
    def run(self, h: Handle, cmd: str) -> ExecResult: ...
    def checkpoint(self, h: Handle) -> str: ...          # snapshot name
    def branch(self, snapshot: str, n: int) -> list[Handle]: ...
    def destroy(self, h: Handle) -> None: ...


class ReasoningPort(Protocol):
    """The reasoning seam (spec 002). Returns a raw mapping; `reasoning.validate`
    is the single gate that accepts or rejects it."""
    def next_instruction(self, context: str) -> Mapping: ...


LLMClient = ReasoningPort            # backward-compatible alias


# --- capability contract: fail at import if the seam over-reaches the map -------
capabilities.assert_declared(PORT_OPERATIONS)
