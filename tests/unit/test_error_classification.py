"""tests/unit/test_error_classification.py — US4: every failure gets exactly one class.

No network. Traces: FR-000-10, FR-000-07, SC-006.
Decision table: specs/000-sandbox-capability-contract/contracts/error-classification.md
"""

import pytest

from rewind.ports import CallRecord, RuntimeCallError
from rewind.providers import FakeProvider, classify


class _HttpError(Exception):
    def __init__(self, status, message=""):
        super().__init__(message or f"HTTP {status}")
        self.status = status


def test_transient_is_retryable():
    assert classify(TimeoutError("read timed out")) == "retryable"
    assert classify(ConnectionError("connection reset by peer")) == "retryable"
    assert classify(_HttpError(503)) == "retryable"
    assert classify(_HttpError(500, "internal error")) == "retryable"
    assert classify(Exception("sandbox still starting, not ready")) == "retryable"
    assert classify(_HttpError(429, "rate limit exceeded")) == "retryable"


def test_quota_and_capacity_are_capacity():
    assert classify(_HttpError(402, "payment required")) == "capacity"
    assert classify(Exception("account quota exceeded")) == "capacity"
    assert classify(Exception("insufficient resources: cpu limit")) == "capacity"
    assert classify(Exception("too many sandboxes")) == "capacity"
    assert classify(_HttpError(429, "quota exhausted")) == "capacity"   # quota beats rate-limit


def test_bad_request_is_terminal():
    assert classify(_HttpError(422, "not supported for this sandbox")) == "terminal"
    assert classify(_HttpError(400, "invalid argument")) == "terminal"
    assert classify(_HttpError(404, "no such sandbox")) == "terminal"
    assert classify(_HttpError(401, "invalid api key")) == "terminal"
    assert classify(_HttpError(403, "forbidden")) == "terminal"


def test_ambiguous_defaults_to_capacity_never_terminal():
    """FR-000-10 — an undecidable failure is capacity, so a caller backs off
    instead of treating a transient limit as a bug."""
    assert classify(Exception("something opaque happened")) == "capacity"
    assert classify(RuntimeError("")) == "capacity"


def test_runtime_call_error_keeps_its_class():
    assert classify(RuntimeCallError("no slot", "capacity")) == "capacity"
    assert classify(RuntimeCallError("bad", "terminal")) == "terminal"


def test_classification_on_record():
    """FR-000-07 / SC-006 — a failed call's record carries exactly one class."""
    p = FakeProvider(ceiling=1, slot_wait=0.01)
    p.spawn()
    with pytest.raises(RuntimeCallError):
        p.spawn()
    errs = [c for c in p.calls if c.outcome == "error"]
    assert errs and all(isinstance(c, CallRecord) for c in errs)
    assert errs[-1].error_class == "capacity"
    assert errs[-1].error_class in ("retryable", "capacity", "terminal")


def test_call_record_fields_present():
    """FR-000-07 — operation, outcome, elapsed on every record; waited/retries where a bound applied."""
    p = FakeProvider()
    h = p.spawn()
    p.run(h, "echo hi > f")
    p.destroy(h)
    assert {c.operation for c in p.calls} >= {"spawn", "run", "destroy"}
    for c in p.calls:
        assert c.operation and c.outcome in ("ok", "error")
        assert c.elapsed_seconds >= 0
        assert c.waited_seconds >= 0 and c.retries >= 0
