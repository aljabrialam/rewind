"""src/rewind/providers.py — the only file that imports the Daytona SDK."""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .ports import ExecResult, Handle, WORKSPACE


class DaytonaProvider:
    """Verified mechanism: create_snapshot() on the head, then create N from it.
    fork() exists but returns 422 on container-class sandboxes."""

    def __init__(self) -> None:
        from daytona import Daytona, DaytonaConfig

        self._d = Daytona(DaytonaConfig(api_key=os.environ["DAYTONA_API_KEY"]))
        self._auto_stop = int(os.environ.get("SANDBOX_AUTO_STOP_MINUTES", 2))
        self.calls: list[tuple[str, float]] = []          # FR-000-07

    def _timed(self, op: str, fn):
        t0 = time.time()
        try:
            return fn()
        finally:
            self.calls.append((op, time.time() - t0))

    def spawn(self) -> Handle:
        sb = self._timed("spawn", lambda: self._d.create())
        try:                                              # FR-000-08, best effort
            sb.set_autostop_interval(self._auto_stop)
        except Exception:
            pass
        sb.process.exec(f"mkdir -p {WORKSPACE}")
        return Handle(id=sb.id)

    def _sb(self, h: Handle):
        return self._d.get(h.id)

    def run(self, h: Handle, cmd: str) -> ExecResult:
        t0 = time.time()
        r = self._timed("run", lambda: self._sb(h).process.exec(f"cd {WORKSPACE} && {cmd}"))
        return ExecResult(
            exit_code=int(getattr(r, "exit_code", 0) or 0),
            stdout=str(getattr(r, "result", r) or ""),
            elapsed=time.time() - t0,
        )

    def checkpoint(self, h: Handle) -> str:
        name = f"cp-{uuid.uuid4().hex[:8]}"
        self._timed("checkpoint", lambda: self._sb(h).create_snapshot(name))
        return name

    def branch(self, snapshot: str, n: int) -> list[Handle]:
        from daytona import CreateSandboxFromSnapshotParams as P

        def one(_):
            sb = self._d.create(P(snapshot=snapshot))
            try:
                sb.set_autostop_interval(self._auto_stop)
            except Exception:
                pass
            return Handle(id=sb.id, snapshot=snapshot)

        with ThreadPoolExecutor(max_workers=n) as ex:     # FR-004-04
            return list(ex.map(one, range(n)))

    def destroy(self, h: Handle) -> None:
        try:
            self._timed("destroy", lambda: self._d.delete(self._sb(h)))
        except Exception:
            pass                                          # never let cleanup break a run


class FakeProvider:
    """No network, no credentials. Same behaviour, instant."""

    def __init__(self, latency: float = 0.0, fail_rate: float = 0.0) -> None:
        self.fs: dict[str, dict[str, str]] = {}
        self.snapshots: dict[str, dict[str, str]] = {}
        self.live: set[str] = set()
        self.latency, self.fail_rate = latency, fail_rate
        self._n = 0

    def _tick(self) -> None:
        if self.latency:
            time.sleep(self.latency)

    def spawn(self) -> Handle:
        self._tick()
        self._n += 1
        sid = f"fake-{self._n:04d}"
        self.fs[sid] = {}
        self.live.add(sid)
        return Handle(id=sid)

    def run(self, h: Handle, cmd: str) -> ExecResult:
        self._tick()
        import random

        if random.random() < self.fail_rate:
            return ExecResult(1, "simulated failure", 0.01)
        # toy semantics: `echo X >> f` appends, `cat f` reads
        store = self.fs.setdefault(h.id, {})
        if ">>" in cmd or ">" in cmd:
            body, path = cmd.split(">>" if ">>" in cmd else ">", 1)
            path = path.strip()
            val = body.replace("echo", "").strip()
            store[path] = (store.get(path, "") + "\n" + val).strip() if ">>" in cmd else val
            return ExecResult(0, "", 0.01)
        if cmd.startswith("cat "):
            return ExecResult(0, store.get(cmd[4:].strip(), ""), 0.01)
        return ExecResult(0, f"ran: {cmd}", 0.01)

    def checkpoint(self, h: Handle) -> str:
        self._tick()
        name = f"fake-cp-{uuid.uuid4().hex[:6]}"
        self.snapshots[name] = dict(self.fs.get(h.id, {}))
        return name

    def branch(self, snapshot: str, n: int) -> list[Handle]:
        out = []
        for _ in range(n):
            h = self.spawn()
            self.fs[h.id] = dict(self.snapshots[snapshot])   # children carry parent state
            h.snapshot = snapshot
            out.append(h)
        return out

    def destroy(self, h: Handle) -> None:
        self.live.discard(h.id)
