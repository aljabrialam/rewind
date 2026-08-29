"""src/rewind/reasoning.py — the reasoning seam.

One port for asking a reasoning agent for the next instruction, a fixture-replay
implementation for offline/rehearsed runs, and a live implementation that is the
only module allowed to import a reasoning vendor SDK (Constitution Article IV,
mirroring how `providers.py` isolates `daytona`).

The port returns a raw mapping; `validate()` is the single gate that accepts or
rejects it, so a live response and a replayed one are judged identically
(spec FR-002-01).
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "reasoning"


# --------------------------------------------------------------------------- schema


class SchemaError(ValueError):
    """A reasoning response that does not conform to the declared schema."""


@dataclass(frozen=True)
class Instruction:
    """The validated unit of work: a command to run and the agent's reason."""
    instruction: str
    rationale: str


def validate(payload: Mapping) -> Instruction:
    """The gate. Accept only a mapping with a non-empty string `instruction` and
    a non-empty string `rationale`; unknown keys are ignored (not rejected)."""
    if not isinstance(payload, Mapping):
        raise SchemaError(f"reasoning response must be a mapping, got {type(payload).__name__}")

    if "instruction" not in payload:
        raise SchemaError("reasoning response missing required key 'instruction'")
    instr = payload["instruction"]
    if not isinstance(instr, str):
        raise SchemaError(f"'instruction' must be a string, got {type(instr).__name__}")
    if not instr.strip():
        raise SchemaError("'instruction' must not be empty")

    if "rationale" not in payload:
        raise SchemaError("reasoning response missing required key 'rationale'")
    rat = payload["rationale"]
    if not isinstance(rat, str):
        raise SchemaError(f"'rationale' must be a string, got {type(rat).__name__}")
    if not rat.strip():
        raise SchemaError("'rationale' must not be empty")

    return Instruction(instruction=instr, rationale=rat)


# ------------------------------------------------------------------- verdict schema
# spec 005 — the critic's structured response. Same rejection MECHANISM as
# `validate` (a SchemaError subclass), different fields.


class VerdictSchemaError(SchemaError):
    """A critic verdict that does not conform to the required structure."""


@dataclass(frozen=True)
class Verdict:
    chosen: str
    scores: dict           # branch id -> float
    reason: str
    reason_unsupported: bool = False


_EVIDENCE_WORDS = ("exit", "output", "stdout", "elapsed")


def validate_verdict(payload: Mapping, branch_ids) -> Verdict:
    """Gate for FR-005-02/03. `branch_ids` is the set of branches the critic must
    score and choose from. Any structural failure raises VerdictSchemaError; the
    caller catches it and falls back (FR-005-07)."""
    ids = list(branch_ids)
    if not isinstance(payload, Mapping):
        raise VerdictSchemaError(f"verdict must be a mapping, got {type(payload).__name__}")

    chosen = payload.get("chosen")
    if not isinstance(chosen, str) or not chosen:
        raise VerdictSchemaError("verdict 'chosen' must be a non-empty string")
    if chosen not in ids:
        raise VerdictSchemaError(f"verdict 'chosen' {chosen!r} is not one of the branches {ids}")

    raw = payload.get("scores")
    scores: dict = {}
    if isinstance(raw, Mapping):
        src = dict(raw)
    elif isinstance(raw, list):                       # [{branch, score}] -> {branch: score}
        src = {}
        for row in raw:
            if isinstance(row, Mapping) and "branch" in row and "score" in row:
                src[row["branch"]] = row["score"]
    else:
        raise VerdictSchemaError("verdict 'scores' must be a mapping or a list of {branch, score}")
    for bid in ids:
        if bid not in src:
            raise VerdictSchemaError(f"verdict 'scores' omits a score for branch {bid!r}")
        try:
            scores[bid] = float(src[bid])
        except (TypeError, ValueError):
            raise VerdictSchemaError(f"verdict score for {bid!r} is not numeric: {src[bid]!r}")

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise VerdictSchemaError("verdict 'reason' must be a non-empty string")

    low = reason.lower()
    cites = (any(w in low for w in _EVIDENCE_WORDS)
             or any(len(bid) >= 4 and bid in reason for bid in ids))
    return Verdict(chosen=chosen, scores=scores, reason=reason, reason_unsupported=not cites)


# ----------------------------------------------------------------------------- port


class ReasoningPort(Protocol):
    def next_instruction(self, context: str) -> Mapping: ...


# ------------------------------------------------------------------- replay + record


class ReplayReasoner:
    """Serves recorded reasoning fixtures in ascending `seq`. No network."""

    def __init__(self, fixtures_dir: Path | str = FIXTURES_DIR) -> None:
        self._dir = Path(fixtures_dir)
        blobs = []
        for f in sorted(self._dir.glob("*.json")):
            blobs.append(json.loads(f.read_text()))
        blobs.sort(key=lambda b: b.get("seq", 0))
        self._queue: list[dict] = blobs
        self._i = 0

    def next_instruction(self, context: str) -> Mapping:
        if self._i >= len(self._queue):
            raise LookupError(
                f"ReplayReasoner exhausted after {len(self._queue)} fixtures in {self._dir}")
        blob = self._queue[self._i]
        self._i += 1
        return blob["response"]


class RecordingReasoner:
    """Wraps a reasoning port, delegates, writes a provenance-stamped fixture per
    call. The only sanctioned way to produce a reasoning fixture (Article VI)."""

    def __init__(self, inner: ReasoningPort, fixtures_dir: Path | str = FIXTURES_DIR) -> None:
        self._inner = inner
        self._dir = Path(fixtures_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    def next_instruction(self, context: str) -> Mapping:
        resp = self._inner.next_instruction(context)
        self._seq += 1
        (self._dir / f"{self._seq:03d}.json").write_text(json.dumps({
            "seq": self._seq,
            "context": context,
            "response": dict(resp),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "model": getattr(self._inner, "model", os.environ.get("LLM_MODEL", "unknown")),
        }, indent=2))
        return resp


class LiveReasoner:
    """The only module member that talks to a reasoning vendor. OpenAI-compatible
    chat completion; returns the raw parsed JSON object (unvalidated)."""

    def __init__(self, *, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None) -> None:
        from openai import OpenAI  # sole reasoning-vendor import

        # spec 008 — each arg defaults to its LLM_* env var, so the no-arg call
        # (the primary provider) is unchanged and an alternate endpoint is a
        # parameterised construction.
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self._client = OpenAI(
            api_key=api_key or os.environ["LLM_API_KEY"],
            base_url=(base_url or os.environ.get("LLM_BASE_URL")) or None,
        )

    def next_instruction(self, context: str) -> Mapping:
        rsp = self._client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "You drive one shell step at a time. Reply with a JSON object "
                    '{"instruction": "<shell command>", "rationale": "<why>"}.')},
                {"role": "user", "content": context},
            ],
        )
        return json.loads(rsp.choices[0].message.content)


# ------------------------------------------------------------- alternate endpoint
# spec 008 — route a reasoning role to a self-hosted endpoint by configuration,
# through this same port, with automatic fallback to the primary. Article VIII:
# additive, deletable with zero impact — nothing else imports these.


def verdict_ids_from_bundle(context: str) -> list[str]:
    """The branch ids Engine._evidence_bundle writes into the critic's context."""
    return re.findall(r"branch (\S+) \|", context or "")


class RoutedReasoner:
    """A ReasoningPort that tries `alternate` first within `bound`, validates its
    response with the same rule as the primary's, and falls back to `primary` on
    timeout, error, or a non-conforming response. `last_served_by` names which
    endpoint answered the most recent call (spec 008 FR-008-02/04/05)."""

    def __init__(self, alternate, primary, *, bound: float,
                 validate: "Callable[[Mapping, str], None] | None" = None) -> None:
        self._alternate = alternate
        self._primary = primary
        self._bound = bound
        self._validate = validate
        self.last_served_by: str = "primary"

    def next_instruction(self, context: str) -> Mapping:
        ex = ThreadPoolExecutor(max_workers=1)
        fut = ex.submit(self._alternate.next_instruction, context)
        try:
            raw = fut.result(timeout=self._bound)
            if self._validate is not None:
                self._validate(raw, context)            # FR-008-03 — same schema, may raise
            ex.shutdown(wait=False)
            self.last_served_by = "alternate"
            return raw
        except Exception:                               # noqa: BLE001 — timeout / error / rejected
            ex.shutdown(wait=False, cancel_futures=True)   # never join a hung alternate
            self.last_served_by = "primary"
            return self._primary.next_instruction(context)


def critic_reasoner():
    """The critic reasoning port. Routed to CRITIC_BASE_URL/CRITIC_MODEL when both
    are set (FR-008-01); otherwise the plain primary — identical to before this
    feature (FR-008-07)."""
    from . import capabilities

    primary = LiveReasoner()
    alt_url = os.environ.get("CRITIC_BASE_URL")
    alt_model = os.environ.get("CRITIC_MODEL")
    if not (alt_url and alt_model):
        return primary

    alternate = LiveReasoner(
        base_url=alt_url, model=alt_model,
        api_key=os.environ.get("CRITIC_API_KEY") or os.environ.get("LLM_API_KEY"),
    )
    return RoutedReasoner(
        alternate, primary, bound=capabilities.ALT_WAIT,
        validate=lambda raw, ctx: validate_verdict(raw, verdict_ids_from_bundle(ctx)),
    )
