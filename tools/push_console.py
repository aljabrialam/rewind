"""push_console.py — send fixtures/tree.json to the deployed console (spec 009).

Best-effort. Runs only when both env vars are set; any failure prints one line
and exits 0 so the local demo is never affected (FR-009-09).

    export REWIND_CONSOLE_ENDPOINT="https://<deploy>/api/fixture"
    export REWIND_CONSOLE_TOKEN="<shared secret>"
    python tools/push_console.py [path/to/tree.json]

demo.py calls push() directly after it writes the fixture.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request

DEFAULT_PATH = "fixtures/tree.json"
TIMEOUT_S = 5


def push(path: str = DEFAULT_PATH) -> bool:
    """POST the fixture at `path` to REWIND_CONSOLE_ENDPOINT. Returns True on a
    2xx, False otherwise. Never raises for an expected failure (missing env,
    missing file, network, non-2xx)."""
    endpoint = os.environ.get("REWIND_CONSOLE_ENDPOINT")
    token = os.environ.get("REWIND_CONSOLE_TOKEN")
    if not endpoint or not token:
        print("  console push skipped: REWIND_CONSOLE_ENDPOINT / REWIND_CONSOLE_TOKEN not set")
        return False

    try:
        with open(path, "rb") as f:
            body = f.read()
    except OSError as e:
        print(f"  console push skipped: cannot read {path} ({e})")
        return False

    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"content-type": "application/json", "x-rewind-token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            print(f"  console push → {endpoint} ({resp.status})")
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        print(f"  console push failed: HTTP {e.code} {e.reason}")
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"  console push failed: {e}")
        return False


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    raise SystemExit(0 if push(arg) else 0)  # always 0 — best-effort
