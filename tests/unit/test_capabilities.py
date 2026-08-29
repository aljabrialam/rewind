"""tests/unit/test_capabilities.py — US1: an invented capability cannot be committed.

No network. Run: pytest tests/unit -q
Traces: FR-000-01, FR-000-01a, FR-000-01b, FR-000-02, FR-000-03, FR-000-04,
FR-000-06, NFR-000-01.
"""

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from rewind import capabilities as cap
from rewind.capabilities import CapabilityError, load_and_validate
from rewind.ports import Handle

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "rewind"

GOOD_MAP = """\
runtime_version   = "v0.207.0"
generated_at      = "2026-08-29T04:15:00Z"
account_cpu_total = 10
max_branches      = 3
classes = ["container", "vm"]

[[operation]]
name           = "spawn"
required_class = "container"
post_condition = "returns a sandbox that accepts `echo ok`"
experimental   = false
"""


def _write(tmp_path, body):
    p = tmp_path / "capability-map.toml"
    p.write_text(textwrap.dedent(body))
    return p


# --------------------------------------------------------------- T010: completeness

def test_map_loads_and_is_complete():
    """FR-000-01 — the real shipped map parses and every entry is complete."""
    c = load_and_validate(REPO / ".rewind" / "capability-map.toml")
    assert c.verified_ops == {"spawn", "run", "checkpoint", "branch", "destroy"}
    assert "fork" not in c.verified_ops                       # FR-000-01a, Art. XIII
    assert c.account_cpu_total == 10 and c.max_branches == 3
    for op in c.verified_ops:
        assert c.class_of[op] in c.classes
        assert c.post_condition[op].strip()                   # FR-000-01a


def test_missing_post_condition_rejected(tmp_path):
    """FR-000-01a — a non-error return is not enough; no post-condition => not verified."""
    p = _write(tmp_path, GOOD_MAP.replace(
        'post_condition = "returns a sandbox that accepts `echo ok`"\n', ""))
    with pytest.raises(CapabilityError, match="post_condition"):
        load_and_validate(p)


def test_missing_required_class_rejected(tmp_path):
    p = _write(tmp_path, GOOD_MAP.replace(
        'required_class = "container"\n', ""))
    with pytest.raises(CapabilityError, match="required_class"):
        load_and_validate(p)


def test_experimental_without_marker_rejected(tmp_path):
    """FR-000-01b — an experimental-flagged name must carry its exact marker."""
    p = _write(tmp_path, GOOD_MAP.replace(
        "experimental   = false\n", "experimental   = true\n"))
    with pytest.raises(CapabilityError, match="experimental_marker|experimental"):
        load_and_validate(p)


def test_missing_map_points_at_the_map(tmp_path):
    """Edge case — message points at the map, not the caller."""
    missing = tmp_path / "nope.toml"
    with pytest.raises(CapabilityError, match=str(missing)):
        load_and_validate(missing)


# ------------------------------------------------- T010: undeclared op fails at LOAD

def test_assert_declared_names_the_offender():
    with pytest.raises(CapabilityError, match="'bogus'"):
        cap.assert_declared(["spawn", "bogus"])


def test_undeclared_op_raises_on_import(tmp_path):
    """NFR-000-01 — the failure happens when the code is loaded, not at demo time."""
    bad = _write(tmp_path, GOOD_MAP)          # only declares `spawn`
    proc = subprocess.run(
        [sys.executable, "-c", "import rewind.ports"],
        env={"REWIND_CAPABILITY_MAP": str(bad), "PATH": ""},
        cwd=str(REPO / "src"),
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "CapabilityError" in proc.stderr
    # ports.py declares run/checkpoint/branch/destroy which this map omits
    assert "'run'" in proc.stderr or "'checkpoint'" in proc.stderr


# ----------------------------------------------------- T011: class mismatch, no call

def test_assert_class_rejects_wrong_class_without_a_call():
    """FR-000-04 — refused before any runtime call. assert_class is pure."""
    vm_handle = Handle(id="whatever", sandbox_class="vm")
    with pytest.raises(CapabilityError, match="requires a 'container'"):
        cap.assert_class("run", vm_handle)


def test_assert_class_allows_matching_class():
    cap.assert_class("run", Handle(id="x", sandbox_class="container"))   # no raise


# -------------------------------------------------------- T011: identifiers opaque

def test_identifier_is_opaque():
    """FR-000-06 — no function builds, parses, or mutates an id."""
    for mod in (cap, __import__("rewind.ports", fromlist=["x"])):
        for bad in ("parse_id", "make_id", "build_id", "encode_id", "decode_id"):
            assert not hasattr(mod, bad)
    weird = "sbx_::/=+ …\t漢字"
    assert Handle(id=weird).id == weird                     # carried verbatim


# ------------------------------------------------ T012: single SDK boundary

def test_no_sdk_import_outside_providers():
    """FR-000-02 — providers.py is the only module that imports the vendor SDK."""
    offenders = []
    for py in SRC.glob("*.py"):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(n == "daytona" or n.startswith("daytona.") for n in names):
                if py.name != "providers.py":
                    offenders.append(py.name)
    assert offenders == [], f"vendor SDK imported outside providers.py: {offenders}"
