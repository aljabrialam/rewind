"""tests/conftest.py — keep the default run offline.

`pytest` alone runs only the base layer (Constitution Article VI). The `live`
marker is deselected by `addopts` in pyproject.toml; this hook is the belt to
that suspenders — if someone runs `pytest -m live` without credentials, the
live tests skip instead of erroring on a missing key.
"""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("DAYTONA_API_KEY"):
        return
    skip_live = pytest.mark.skip(reason="DAYTONA_API_KEY not set — live tests skipped")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
