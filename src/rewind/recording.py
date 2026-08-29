"""src/rewind/recording.py — capture live behaviour, replay it offline.

`RecordingProvider` wraps the live port, runs every declared operation for real,
and writes one JSON fixture per call. `ReplayProvider` serves those fixtures with
no network. Fixtures may only be produced this way — hand-authored fixtures are
prohibited (spec NFR-000-03), so every file carries `recorded_at` and
`runtime_version` provenance.

Nothing here imports a vendor SDK; the live work is delegated to whatever
provider is passed in.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import capabilities
from .ports import ExecResult, Handle

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "daytona"


# --------------------------------------------------------------------- serialization


def _dump_result(value):
    if isinstance(value, Handle):
        return {"__type__": "Handle", **value.__dict__}
    if isinstance(value, ExecResult):
        return {"__type__": "ExecResult", "exit_code": value.exit_code,
                "stdout": value.stdout, "elapsed": value.elapsed}
    if isinstance(value, list):
        return [_dump_result(v) for v in value]
    return {"__type__": "value", "value": value}


def _load_result(blob):
    if isinstance(blob, list):
        return [_load_result(b) for b in blob]
    t = blob.get("__type__")
    if t == "Handle":
        data = {k: v for k, v in blob.items() if k != "__type__"}
        return Handle(**data)
    if t == "ExecResult":
        return ExecResult(blob["exit_code"], blob["stdout"], blob.get("elapsed", 0.0))
    return blob.get("value")


# ------------------------------------------------------------------ RecordingProvider


class RecordingProvider:
    """Delegates every declared operation to `inner`, then writes a fixture."""

    def __init__(self, inner, fixtures_dir: Path | str = FIXTURES_DIR) -> None:
        self._inner = inner
        self._dir = Path(fixtures_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._seq: dict[str, int] = {}

    def _record(self, op: str, args: dict, fn):
        capabilities.assert_declared([op])
        t0 = time.time()
        error = None
        result = None
        try:
            result = fn()
            return result
        except Exception as e:                       # noqa: BLE001 - provenance capture
            error = {"type": type(e).__name__, "message": str(e),
                     "error_class": getattr(e, "error_class", None)}
            raise
        finally:
            self._seq[op] = self._seq.get(op, 0) + 1
            path = self._dir / f"{op}-{self._seq[op]:03d}.json"
            path.write_text(json.dumps({
                "operation": op,
                "args": args,
                "result": _dump_result(result) if error is None else None,
                "error": error,
                "elapsed": round(time.time() - t0, 4),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "runtime_version": capabilities.RUNTIME_VERSION,
            }, indent=2))

    def spawn(self) -> Handle:
        return self._record("spawn", {}, self._inner.spawn)

    def run(self, h: Handle, cmd: str) -> ExecResult:
        return self._record("run", {"id": h.id, "cmd": cmd}, lambda: self._inner.run(h, cmd))

    def checkpoint(self, h: Handle) -> str:
        return self._record("checkpoint", {"id": h.id}, lambda: self._inner.checkpoint(h))

    def branch(self, snapshot: str, n: int) -> list[Handle]:
        return self._record("branch", {"snapshot": snapshot, "n": n},
                            lambda: self._inner.branch(snapshot, n))

    def destroy(self, h: Handle) -> None:
        return self._record("destroy", {"id": h.id}, lambda: self._inner.destroy(h))


# -------------------------------------------------------------------- ReplayProvider


class ReplayProvider:
    """Serves recorded fixtures in recorded order, per operation. No network."""

    def __init__(self, fixtures_dir: Path | str = FIXTURES_DIR) -> None:
        self._dir = Path(fixtures_dir)
        self._queues: dict[str, list[dict]] = {}
        for f in sorted(self._dir.glob("*.json")):
            blob = json.loads(f.read_text())
            self._queues.setdefault(blob["operation"], []).append(blob)

    def _next(self, op: str):
        q = self._queues.get(op)
        if not q:
            raise LookupError(f"no recorded fixture for {op!r} in {self._dir}")
        blob = q.pop(0)
        if blob["error"]:
            err = RuntimeError(blob["error"]["message"])
            setattr(err, "error_class", blob["error"].get("error_class"))
            raise err
        return _load_result(blob["result"])

    def spawn(self) -> Handle:
        return self._next("spawn")

    def run(self, h: Handle, cmd: str) -> ExecResult:
        return self._next("run")

    def checkpoint(self, h: Handle) -> str:
        return self._next("checkpoint")

    def branch(self, snapshot: str, n: int) -> list[Handle]:
        return self._next("branch")

    def destroy(self, h: Handle) -> None:
        return self._next("destroy")
