"""Round-trip parser tests for observability Pydantic models.

Exercises the _empty_to_none validator contract on TraceRecord and
FailureRecord. These tests pin the behaviour introduced in Task 7 of
Phase 1 (AppExceptions native fields) and would have caught the
regression where `message: str` (non-optional) rejected None produced
by the validator when given an empty-string input.
"""

from second_brain.observability.models import FailureRecord, TraceRecord

# ---------------------------------------------------------------------------
# FailureRecord
# ---------------------------------------------------------------------------


def test_failure_record_accepts_empty_message_via_validator() -> None:
    """Empty message string is normalised to None by the validator.

    Trigger path: queries.py uses str(row.get("Message", "")) which
    produces "" when the KQL column is absent. The validator must convert
    that to None, and the field must accept None.
    """
    record = FailureRecord(
        timestamp="2026-01-01T00:00:00Z", item_type="Exception", message=""
    )
    assert record.message is None


def test_failure_record_accepts_whitespace_message_via_validator() -> None:
    """Whitespace-only message is also normalised to None."""
    record = FailureRecord(
        timestamp="2026-01-01T00:00:00Z", item_type="Exception", message="   "
    )
    assert record.message is None


def test_failure_record_normalizes_empty_new_fields() -> None:
    """All four AppExceptions native fields normalise empty strings to None."""
    record = FailureRecord(
        timestamp="2026-01-01T00:00:00Z",
        item_type="Exception",
        outer_message="",
        outer_type="",
        innermost_message="",
        details="",
    )
    assert record.outer_message is None
    assert record.outer_type is None
    assert record.innermost_message is None
    assert record.details is None


def test_failure_record_preserves_non_empty_fields() -> None:
    """Non-empty values survive the validator unchanged."""
    record = FailureRecord(
        timestamp="2026-01-01T00:00:00Z",
        item_type="Exception",
        message="Something went wrong",
        outer_message="System.Exception: outer",
        outer_type="System.Exception",
        innermost_message="inner cause",
        details='{"stack": "..."}',
    )
    assert record.message == "Something went wrong"
    assert record.outer_message == "System.Exception: outer"
    assert record.outer_type == "System.Exception"
    assert record.innermost_message == "inner cause"
    assert record.details == '{"stack": "..."}'


def test_failure_record_preserves_component_and_trace_id() -> None:
    """Pre-existing validator behaviour for component/capture_trace_id is not regressed.

    Pins the Phase 17.1 fix: empty component and trace ID normalise to None,
    and non-empty values are preserved.
    """
    empty_record = FailureRecord(
        timestamp="2026-01-01T00:00:00Z",
        item_type="AppTrace",
        component="",
        capture_trace_id="",
    )
    assert empty_record.component is None
    assert empty_record.capture_trace_id is None
    assert empty_record.capture_trace_id_short is None

    full_record = FailureRecord(
        timestamp="2026-01-01T00:00:00Z",
        item_type="AppTrace",
        component="capture_flow",
        capture_trace_id="abcdef1234567890",
    )
    assert full_record.component == "capture_flow"
    assert full_record.capture_trace_id == "abcdef1234567890"
    assert full_record.capture_trace_id_short == "abcdef12"


# ---------------------------------------------------------------------------
# TraceRecord
# ---------------------------------------------------------------------------


def test_trace_record_accepts_empty_message_via_validator() -> None:
    """Same validator contract as FailureRecord applies to TraceRecord."""
    record = TraceRecord(
        timestamp="2026-01-01T00:00:00Z", item_type="AppTrace", message=""
    )
    assert record.message is None


def test_trace_record_accepts_whitespace_message_via_validator() -> None:
    """Whitespace-only message is also normalised to None on TraceRecord."""
    record = TraceRecord(
        timestamp="2026-01-01T00:00:00Z", item_type="AppTrace", message="  \t "
    )
    assert record.message is None


def test_trace_record_normalizes_empty_new_fields() -> None:
    """All four AppExceptions native fields normalise empty strings to None.

    Mirrors test_failure_record_normalizes_empty_new_fields for symmetry.
    """
    record = TraceRecord(
        timestamp="2026-01-01T00:00:00Z",
        item_type="AppTrace",
        outer_message="",
        outer_type="",
        innermost_message="",
        details="",
    )
    assert record.outer_message is None
    assert record.outer_type is None
    assert record.innermost_message is None
    assert record.details is None


def test_trace_record_preserves_non_empty_fields() -> None:
    """Non-empty values on TraceRecord survive the validator unchanged."""
    record = TraceRecord(
        timestamp="2026-01-01T00:00:00Z",
        item_type="AppTrace",
        message="Capture started",
        outer_message="Outer",
        outer_type="System.IO.Exception",
        innermost_message="File not found",
        details='{"path": "/tmp/x"}',
        component="capture_flow",
        capture_trace_id="deadbeef00000000",
    )
    assert record.message == "Capture started"
    assert record.outer_message == "Outer"
    assert record.outer_type == "System.IO.Exception"
    assert record.innermost_message == "File not found"
    assert record.details == '{"path": "/tmp/x"}'
    assert record.component == "capture_flow"
    assert record.capture_trace_id == "deadbeef00000000"


def test_trace_record_accepts_omitted_message() -> None:
    """message omitted entirely defaults to None (field default)."""
    record = TraceRecord(timestamp="2026-01-01T00:00:00Z", item_type="AppTrace")
    assert record.message is None


def test_failure_record_accepts_omitted_message() -> None:
    """message omitted entirely defaults to None (field default)."""
    record = FailureRecord(timestamp="2026-01-01T00:00:00Z", item_type="AppTrace")
    assert record.message is None
