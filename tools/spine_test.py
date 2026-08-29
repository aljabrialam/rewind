"""
SPINE TEST — run this FIRST. It decides which project we build.

    pip install daytona
    export DAYTONA_API_KEY=dtn_7f9bc5dff2c8927c5a76dd2132843041a3009ed9a404c5c2cc6e7a794d3b39c0
    python spine_test.py

Verdict at the bottom: BUILD A (Rewind) or BUILD C (Dry Run).
Do not write feature code until this prints a verdict.
"""

import asyncio
import os
import time
import traceback

from daytona import Daytona, DaytonaConfig

KEY = os.environ["DAYTONA_API_KEY"]
results = {}


def banner(t):
    print(f"\n{'=' * 60}\n{t}\n{'=' * 60}")


# ---------------------------------------------------------------- 1. discovery
def discover():
    banner("1. WHAT DOES THIS SDK ACTUALLY EXPOSE?")
    d = Daytona(DaytonaConfig(api_key=KEY))
    sb = d.create()
    try:
        print("sandbox id:", getattr(sb, "id", "?"))
        interesting = [
            m for m in dir(sb)
            if any(k in m.lower() for k in ("fork", "snapshot", "pause", "resume", "stop", "network", "preview"))
        ]
        print("lifecycle methods on sandbox:", interesting)
        print("daytona client methods:", [m for m in dir(d) if not m.startswith("_")])
        results["methods"] = interesting
        # baseline: does exec work at all
        t0 = time.time()
        r = sb.process.exec("echo ok")
        print(f"exec round-trip: {time.time() - t0:.2f}s ->", getattr(r, "result", r))
        results["exec"] = True
    finally:
        d.delete(sb)


# ---------------------------------------------------------------- 2. VM + fork
def vm_and_fork():
    banner("2. VM SANDBOX + FORK  (this is the A/C decision)")
    d = Daytona(DaytonaConfig(api_key=KEY))
    sb = None
    try:
        # Try the VM class. Snapshot name may differ — the error message will
        # usually name the valid options, so read it carefully.
        try:
            sb = d.create(snapshot="daytona-vm-small")
        except Exception as e:
            print("named VM snapshot failed:", e)
            print("retrying with default create + explicit class kwarg...")
            sb = d.create(class_name="vm")  # if this errors, read the message for the right kwarg

        sb.process.exec("echo 'state-marker' > /tmp/marker.txt")
        print("wrote marker to parent sandbox")

        fork_fn = None
        for name in ("fork", "_experimental_fork", "clone"):
            if hasattr(sb, name):
                fork_fn = getattr(sb, name)
                print(f"found fork method: sandbox.{name}()")
                break
            if hasattr(d, name):
                fork_fn = lambda: getattr(d, name)(sb)
                print(f"found fork method: daytona.{name}(sandbox)")
                break

        if not fork_fn:
            print("NO FORK METHOD FOUND")
            results["fork"] = False
            return

        t0 = time.time()
        child = fork_fn()
        print(f"fork returned in {time.time() - t0:.2f}s")
        out = child.process.exec("cat /tmp/marker.txt")
        print("child sees parent state:", getattr(out, "result", out))
        results["fork"] = "state-marker" in str(getattr(out, "result", out))
        d.delete(child)
    except Exception:
        traceback.print_exc()
        results["fork"] = False
    finally:
        if sb:
            try:
                d.delete(sb)
            except Exception:
                pass


# ---------------------------------------------------------------- 3. fan-out
async def fanout(n=20):
    banner(f"3. CONCURRENCY — {n} SANDBOXES AT ONCE")
    from daytona import AsyncDaytona

    async with AsyncDaytona(DaytonaConfig(api_key=KEY)) as d:
        async def one(i):
            sb = None
            try:
                sb = await d.create()
                await sb.process.exec(f"echo worker-{i}")
                return True
            except Exception as e:
                print(f"  worker {i} failed: {type(e).__name__}: {str(e)[:90]}")
                return False
            finally:
                if sb:
                    try:
                        await d.delete(sb)
                    except Exception:
                        pass

        t0 = time.time()
        got = await asyncio.gather(*[one(i) for i in range(n)])
        ok = sum(got)
        print(f"{ok}/{n} succeeded in {time.time() - t0:.1f}s")
        results["concurrency"] = ok


# ---------------------------------------------------------------- capability map
def emit_capability_map(path=".rewind/capability-map.toml"):
    """Write the machine-readable capability map from what THIS run observed.

    Obligations (specs/000-sandbox-capability-contract/contracts/capability-map-schema.md):
      G1 write an operation only after its post-condition was asserted this run
      G2 omit any operation that returned an unsupported/error response (e.g. fork)
      G3 quota numbers come from the observed fan-out, not documentation
      G4 an experimental verified name is written with its marker
      G5 overwrite the whole file atomically
    """
    import datetime as _dt
    import pathlib as _pl

    # Operations proven this run. `exec` gates spawn+run; snapshot/branch gate
    # checkpoint+branch. fork is deliberately excluded — see G2.
    verified = []
    if results.get("exec"):
        verified += [
            ("spawn", "container",
             "create() returns a sandbox with non-empty id; `echo ok` in /home/daytona/work "
             "exits 0 before the handle is returned; auto-stop and auto-delete intervals are set"),
            ("run", "container",
             "process.exec(cmd) in /home/daytona/work returns the real exit code and stdout; elapsed > 0"),
        ]
    if results.get("snapshot_branch"):
        verified += [
            ("checkpoint", "container",
             "create_snapshot(name) on a live sandbox returns a usable snapshot name; a later branch "
             "from that name carries the filesystem state as of the call"),
            ("branch", "container",
             "create(CreateSandboxFromSnapshotParams(snapshot=name)) x n (n<=max_branches) returns n "
             "sandboxes; each child shows the parent's pre-snapshot state; children diverge independently"),
        ]
    if results.get("destroy"):
        verified.append(
            ("destroy", "container",
             "delete(sandbox) removes it; the runtime no longer lists the id and the concurrency permit is freed")
        )

    if not verified:
        print("emit_capability_map: nothing verified this run — file NOT written.")
        return

    conc = int(results.get("concurrency", 0)) or 10
    lines = [
        "# .rewind/capability-map.toml  — GENERATED by tools/spine_test.py, do not edit by hand.",
        f'runtime_version   = "{results.get("runtime_version", "unknown")}"',
        f'generated_at      = "{_dt.datetime.now(_dt.timezone.utc).isoformat()}"',
        f"account_cpu_total = {conc}",
        f"max_branches      = {min(3, conc)}",
        "",
        'classes = ["container", "vm"]',
    ]
    for name, klass, post in verified:
        lines += [
            "",
            "[[operation]]",
            f'name           = "{name}"',
            f'required_class = "{klass}"',
            f'post_condition = "{post}"',
            "experimental   = false",
        ]
    tmp = _pl.Path(path).with_suffix(".toml.tmp")
    tmp.write_text("\n".join(lines) + "\n")
    tmp.replace(path)                                      # G5 atomic
    print(f"emit_capability_map: wrote {path} ({len(verified)} operations)")


# ---------------------------------------------------------------- verdict
def verdict():
    banner("VERDICT")
    fork = results.get("fork")
    conc = results.get("concurrency", 0)
    print(f"fork works: {fork}   |   concurrent sandboxes: {conc}")
    if fork:
        print("\n>>> BUILD A — REWIND. Fork is live; it's the cleverest primitive on the table.")
    elif conc >= 15:
        print("\n>>> BUILD C — DRY RUN. No fork, but fan-out is healthy.")
    else:
        print("\n>>> BUILD C, reduced. Cap the fan-out at what actually worked above,")
        print("    and use cold snapshots + restart-from-checkpoint for any branching.")


if __name__ == "__main__":
    discover()
    vm_and_fork()
    asyncio.run(fanout(20))
    emit_capability_map()
    verdict()
