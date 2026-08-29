"""src/rewind/providers.py — the only file that imports the Daytona SDK.

Two implementations of the sandbox port:
  * DaytonaProvider — live, sole SDK boundary
  * FakeProvider    — no network, no credentials, same contract

Both enforce the capability contract per call (class check), bound every wait and
retry with a declared value, attach stop + delete intervals to every sandbox,
count live sandboxes against the verified ceiling, and classify every failure.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from . import capabilities
from .ports import (
    CallRecord,
    ErrorClass,
    ExecResult,
    Handle,
    RuntimeCallError,
    UnconfirmedDestroyLeak,
    WORKSPACE,
)

_CONTAINER = "container"          # the only class the verified map supports today


# --------------------------------------------------------------------- classification


def classify(exc: Exception) -> ErrorClass:
    """Map a runtime failure to exactly one class
    (specs/000-sandbox-capability-contract/contracts/error-classification.md).
    Account-quota and transient-capacity both -> capacity; an undecidable
    capacity-or-terminal failure -> capacity (spec FR-000-10)."""
    if isinstance(exc, RuntimeCallError):
        return exc.error_class

    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    msg = str(exc).lower()
    name = type(exc).__name__.lower()

    # 1-3 transient
    if isinstance(exc, (ConnectionError, TimeoutError)) or "timeout" in name or "timeout" in msg:
        return "retryable"
    if any(w in msg for w in ("connection reset", "connection refused", "remotedisconnected",
                              "temporarily unavailable", "try again")):
        return "retryable"
    if status in (502, 503, 504):
        return "retryable"
    if any(w in msg for w in ("not ready", "still starting", "initializing", "warming up")):
        return "retryable"
    # 4 rate limit (not quota)
    if status == 429 and "quota" not in msg:
        return "retryable"
    # 5 capacity / quota
    if status == 402 or any(w in msg for w in ("quota", "concurrenc", "cpu limit", "capacity",
                                               "no capacity", "insufficient resources",
                                               "too many sandboxes")):
        return "capacity"
    # 6 auth
    if status in (401, 403) or any(w in msg for w in ("unauthorized", "forbidden",
                                                      "invalid api key", "expired")):
        return "terminal"
    # 7-8 bad request
    if status in (400, 404, 409, 422) or any(w in msg for w in ("not supported", "unknown",
                                                                "invalid", "no such")):
        return "terminal"
    if status is not None and 400 <= status < 500:
        return "terminal"
    # 9 other 5xx
    if status is not None and 500 <= status < 600:
        return "retryable"
    # 10 ambiguous -> capacity, never terminal
    return "capacity"


# ---------------------------------------------------------------------- live provider


class DaytonaProvider:
    """Verified mechanism: create_snapshot() on the head, then create N from it.
    fork() exists but returns 422 on container-class sandboxes and is not declared."""

    def __init__(self) -> None:
        from daytona import Daytona, DaytonaConfig

        self._d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
        self._stop_min = capabilities.AUTO_STOP_MIN
        self._delete_min = capabilities.AUTO_DELETE_MIN
        self._sem = threading.BoundedSemaphore(capabilities.CEILING)
        self._live: set[str] = set()
        self.calls: list[CallRecord] = []                 # FR-000-07
        self.leaks: list[UnconfirmedDestroyLeak] = []     # FR-000-09

    # -- bookkeeping -------------------------------------------------------------
    @property
    def live_count(self) -> int:
        return len(self._live) + sum(1 for lk in self.leaks if lk.still_counts)

    def _record(self, op, outcome, elapsed, error_class=None, waited=0.0, retries=0):
        self.calls.append(CallRecord(op, outcome, round(elapsed, 4),
                                     error_class, round(waited, 4), retries))

    def _acquire_slot(self) -> float:
        """FR-000-11 — block for a bounded wait, then fail `capacity`."""
        t0 = time.time()
        if not self._sem.acquire(timeout=capabilities.SLOT_WAIT):
            raise RuntimeCallError(
                f"concurrency ceiling {capabilities.CEILING} reached; no slot in "
                f"{capabilities.SLOT_WAIT}s", "capacity")
        return time.time() - t0

    def _release_slot(self) -> None:
        try:
            self._sem.release()
        except ValueError:
            pass

    def _await_ready(self, sb) -> None:
        """FR-000-08a — do not hand back a sandbox until it accepts a command."""
        deadline = time.time() + capabilities.READINESS_WAIT
        last = None
        while time.time() < deadline:
            try:
                r = sb.process.exec("echo ok")
                if int(getattr(r, "exit_code", 0) or 0) == 0:
                    return
            except Exception as e:                        # noqa: BLE001
                last = e
            time.sleep(0.5)
        raise RuntimeCallError(f"sandbox {getattr(sb, 'id', '?')} not ready in "
                               f"{capabilities.READINESS_WAIT}s ({last})", "retryable")

    def _attach_intervals(self, sb) -> None:
        """FR-000-08 — required, not best-effort."""
        sb.set_autostop_interval(self._stop_min)
        try:
            sb.set_autodelete_interval(self._delete_min)
        except AttributeError:
            sb.set_auto_delete_interval(self._delete_min)

    # -- lifecycle ------------------------------------------------------------
    def spawn(self) -> Handle:
        waited = self._acquire_slot()
        t0 = time.time()
        sb = None
        try:
            sb = self._d.create()
            self._attach_intervals(sb)
            self._await_ready(sb)
            sb.process.exec(f"mkdir -p {WORKSPACE}")
            self._live.add(sb.id)
            self._record("spawn", "ok", time.time() - t0, waited=waited)
            return Handle(id=sb.id, sandbox_class=_CONTAINER, state="ready")
        except Exception as e:                            # noqa: BLE001
            if sb is not None:                            # FR-000-09 destroy the half-born
                self._blind_destroy(sb)
            self._release_slot()
            self._record("spawn", "error", time.time() - t0, classify(e), waited=waited)
            raise

    def _sb(self, h: Handle):
        return self._d.get(h.id)

    def run(self, h: Handle, cmd: str) -> ExecResult:
        capabilities.assert_class("run", h)               # FR-000-04, before any call
        t0 = time.time()
        try:
            r = self._sb(h).process.exec(f"cd {WORKSPACE} && {cmd}")
        except Exception as e:                            # noqa: BLE001
            self._record("run", "error", time.time() - t0, classify(e))
            raise RuntimeCallError(str(e), classify(e)) from e
        self._record("run", "ok", time.time() - t0)
        return ExecResult(
            exit_code=int(getattr(r, "exit_code", 0) or 0),
            stdout=str(getattr(r, "result", r) or ""),
            elapsed=time.time() - t0,
        )

    def checkpoint(self, h: Handle) -> str:
        capabilities.assert_class("checkpoint", h)        # FR-000-04
        name = f"cp-{uuid.uuid4().hex[:8]}"
        t0 = time.time()
        try:
            self._sb(h).create_snapshot(name)
        except Exception as e:                            # noqa: BLE001
            self._record("checkpoint", "error", time.time() - t0, classify(e))
            raise RuntimeCallError(str(e), classify(e)) from e
        self._record("checkpoint", "ok", time.time() - t0)
        return name

    def branch(self, snapshot: str, n: int) -> list[Handle]:
        from daytona import CreateSandboxFromSnapshotParams as P

        if n > capabilities.MAX_BRANCHES:
            raise RuntimeCallError(
                f"branch n={n} exceeds verified max_branches "
                f"{capabilities.MAX_BRANCHES}", "terminal")

        made: list[Handle] = []
        capped: RuntimeCallError | None = None

        def one(_):
            waited = self._acquire_slot()                 # may raise capacity
            t0 = time.time()
            sb = None
            try:
                sb = self._d.create(P(snapshot=snapshot))
                self._attach_intervals(sb)
                self._await_ready(sb)
                self._live.add(sb.id)
                self._record("branch", "ok", time.time() - t0, waited=waited)
                return Handle(id=sb.id, snapshot=snapshot,
                              sandbox_class=_CONTAINER, state="ready")
            except Exception as e:                        # noqa: BLE001
                if sb is not None:
                    self._blind_destroy(sb)
                self._release_slot()
                self._record("branch", "error", time.time() - t0, classify(e), waited=waited)
                raise

        with ThreadPoolExecutor(max_workers=max(1, n)) as ex:
            for res in ex.map(lambda i: _safe(one, i), range(n)):
                if isinstance(res, Handle):
                    made.append(res)
                elif isinstance(res, RuntimeCallError) and res.error_class == "capacity":
                    capped = res                          # keep siblings, remember the cap
                elif isinstance(res, Exception):
                    raise res

        if capped and not made:
            raise capped
        return made                                       # partial fan-out preserved

    def _blind_destroy(self, sb) -> None:
        try:
            self._d.delete(sb)
        except Exception:                                 # noqa: BLE001
            pass

    def destroy(self, h: Handle) -> None:
        capabilities.assert_class("destroy", h)           # FR-000-04
        t0 = time.time()
        for attempt in range(1, capabilities.DESTROY_RETRIES + 1):
            try:
                self._d.delete(self._sb(h))
                self._live.discard(h.id)
                self._release_slot()
                self._record("destroy", "ok", time.time() - t0, retries=attempt - 1)
                return
            except Exception as e:                        # noqa: BLE001
                last = e
                if attempt < capabilities.DESTROY_RETRIES:
                    time.sleep(capabilities.DESTROY_RETRY_GAP)
        self._live.discard(h.id)                          # the leak, not `_live`, now counts it
        leak = UnconfirmedDestroyLeak(h.id, capabilities.DESTROY_RETRIES)
        self.leaks.append(leak)                           # FR-000-09 — still counts, permit held
        h.state = "leaked"
        self._record("destroy", "error", time.time() - t0, "terminal",
                     retries=capabilities.DESTROY_RETRIES)
        raise RuntimeCallError(f"destroy of {h.id} unconfirmed after "
                               f"{capabilities.DESTROY_RETRIES} attempts ({last})", "terminal")


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception as e:                                # noqa: BLE001
        return e


# ---------------------------------------------------------------------- fake provider


class FakeProvider:
    """No network, no credentials. Models the same contract, instantly."""

    def __init__(self, latency: float = 0.0, fail_rate: float = 0.0, *,
                 ceiling: int | None = None, slot_wait: float | None = None,
                 never_ready: bool = False, destroy_fails_times: int = 0,
                 destroy_always_fails: bool = False) -> None:
        self.fs: dict[str, dict[str, str]] = {}
        self.snapshots: dict[str, dict[str, str]] = {}
        self.live: set[str] = set()
        self.leaks: list[UnconfirmedDestroyLeak] = []
        self.calls: list[CallRecord] = []
        self.stop_interval: dict[str, int] = {}
        self.delete_interval: dict[str, int] = {}
        self.latency, self.fail_rate = latency, fail_rate
        self._ceiling = capabilities.CEILING if ceiling is None else ceiling
        self._slot_wait = capabilities.SLOT_WAIT if slot_wait is None else slot_wait
        self._never_ready = never_ready
        self._destroy_fails_left = (10**9 if destroy_always_fails else destroy_fails_times)
        self._n = 0

    # -- bookkeeping -----------------------------------------------------------
    @property
    def live_count(self) -> int:
        return len(self.live) + sum(1 for lk in self.leaks if lk.still_counts)

    def _record(self, op, outcome, elapsed=0.01, error_class=None, waited=0.0, retries=0):
        self.calls.append(CallRecord(op, outcome, elapsed, error_class, waited, retries))

    def _tick(self) -> None:
        if self.latency:
            time.sleep(self.latency)

    def _acquire_slot(self) -> float:
        if self.live_count >= self._ceiling:
            time.sleep(min(self._slot_wait, 0.05))       # nothing frees in a sync fake
            raise RuntimeCallError(
                f"concurrency ceiling {self._ceiling} reached", "capacity")
        return 0.0

    def _new_sandbox(self, snapshot: str | None = None) -> Handle:
        op = "spawn" if snapshot is None else "branch"
        try:
            waited = self._acquire_slot()
        except RuntimeCallError as e:
            self._record(op, "error", error_class=e.error_class)
            raise
        self._tick()
        self._n += 1
        sid = f"fake-{self._n:04d}"
        if self._never_ready:                             # FR-000-08a
            self._record(op, "error", error_class="retryable", waited=waited)
            raise RuntimeCallError(f"{sid} never became command-ready", "retryable")
        self.fs[sid] = dict(self.snapshots[snapshot]) if snapshot else {}
        self.live.add(sid)
        self.stop_interval[sid] = capabilities.AUTO_STOP_MIN
        self.delete_interval[sid] = capabilities.AUTO_DELETE_MIN
        self._record(op, "ok", waited=waited)
        return Handle(id=sid, snapshot=snapshot, sandbox_class=_CONTAINER, state="ready")

    # -- lifecycle ----------------------------------------------------------
    def spawn(self) -> Handle:
        return self._new_sandbox()

    def run(self, h: Handle, cmd: str) -> ExecResult:
        capabilities.assert_class("run", h)              # same guard as the live port
        self._tick()
        import random

        if random.random() < self.fail_rate:
            self._record("run", "ok", error_class=None)  # nonzero exit is evidence, not a runtime error
            return ExecResult(1, "simulated failure", 0.01)
        store = self.fs.setdefault(h.id, {})
        if ">>" in cmd or ">" in cmd:
            body, path = cmd.split(">>" if ">>" in cmd else ">", 1)
            path = path.strip()
            val = body.replace("echo", "").strip()
            store[path] = (store.get(path, "") + "\n" + val).strip() if ">>" in cmd else val
            self._record("run", "ok")
            return ExecResult(0, "", 0.01)
        if cmd.startswith("cat "):
            self._record("run", "ok")
            return ExecResult(0, store.get(cmd[4:].strip(), ""), 0.01)
        self._record("run", "ok")
        return ExecResult(0, f"ran: {cmd}", 0.01)

    def checkpoint(self, h: Handle) -> str:
        capabilities.assert_class("checkpoint", h)
        self._tick()
        name = f"fake-cp-{uuid.uuid4().hex[:6]}"
        self.snapshots[name] = dict(self.fs.get(h.id, {}))
        self._record("checkpoint", "ok")
        return name

    def branch(self, snapshot: str, n: int) -> list[Handle]:
        if n > capabilities.MAX_BRANCHES:
            raise RuntimeCallError(
                f"branch n={n} exceeds verified max_branches {capabilities.MAX_BRANCHES}",
                "terminal")
        out: list[Handle] = []
        for _ in range(n):
            try:
                out.append(self._new_sandbox(snapshot))
            except RuntimeCallError as e:
                if e.error_class == "capacity" and out:
                    break                                # keep siblings (clarification Q1)
                raise
        return out

    def destroy(self, h: Handle) -> None:
        capabilities.assert_class("destroy", h)
        for attempt in range(1, capabilities.DESTROY_RETRIES + 1):
            if self._destroy_fails_left > 0:
                self._destroy_fails_left -= 1
                if attempt < capabilities.DESTROY_RETRIES:
                    continue
                self.live.discard(h.id)                   # the leak now counts it, once
                leak = UnconfirmedDestroyLeak(h.id, capabilities.DESTROY_RETRIES)
                self.leaks.append(leak)                   # FR-000-09
                h.state = "leaked"
                self._record("destroy", "error", error_class="terminal",
                             retries=capabilities.DESTROY_RETRIES)
                raise RuntimeCallError(
                    f"destroy of {h.id} unconfirmed after "
                    f"{capabilities.DESTROY_RETRIES} attempts", "terminal")
            self.live.discard(h.id)
            self._record("destroy", "ok", retries=attempt - 1)
            return
