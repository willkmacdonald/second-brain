"""Unit tests for investigation_client: format_response and _handle_event.

These tests cover the deterministic formatting and event-dispatching logic.
They do NOT test fetch_api_key (Azure SDK) or stream_investigation (httpx)
-- those are verified by Layer 2 smoke tests against the deployed endpoint.
"""

from second_brain.investigation_client import (
    InvestigationResult,
    _handle_event,
    format_response,
)


class TestHandleEvent:
    """Test that _handle_event correctly accumulates SSE events."""

    def test_text_events_concatenate(self):
        """Multiple text events should concatenate into result.text."""
        result = InvestigationResult()
        _handle_event({"type": "text", "content": "Found "}, result)
        _handle_event({"type": "text", "content": "3 errors"}, result)
        _handle_event({"type": "text", "content": " today."}, result)
        assert result.text == "Found 3 errors today."


class TestFormatResponse:
    """Test that format_response builds correct stdout/stderr pairs."""

    def test_simple_text_only(self):
        """Text-only result with no tools and a new thread."""
        result = InvestigationResult(
            text="No errors found in the last 24h.",
            tools_called=[],
            thread_id="thread_abc123",
            elapsed_seconds=0.8,
            was_continued=False,
        )
        stdout, stderr = format_response(result)
        assert "No errors found in the last 24h." in stdout
        assert "no tools" in stdout
        assert "(new)" in stdout
        assert "0.8s" in stdout
        assert "[THREAD_ID: thread_abc123]" in stdout
        assert stderr == ""

    def test_tools_called_listed(self):
        """Tools should appear comma-separated in the status line."""
        result = InvestigationResult(
            text="Here are the results.",
            tools_called=["recent_errors", "system_health"],
            thread_id="thread_xyz",
            elapsed_seconds=3.2,
            was_continued=False,
        )
        stdout, stderr = format_response(result)
        assert "tools: recent_errors, system_health" in stdout

    def test_continued_thread_shows_continued(self):
        """When was_continued=True, status line should say (continued)."""
        result = InvestigationResult(
            text="Step 4 was the admin agent call.",
            tools_called=["trace_lifecycle"],
            thread_id="thread_abc123",
            elapsed_seconds=2.1,
            was_continued=True,
        )
        stdout, stderr = format_response(result)
        assert "(continued)" in stdout
        assert "(new)" not in stdout

    def test_error_goes_to_stderr(self):
        """When result.error is set, stderr should contain ERROR: prefix."""
        result = InvestigationResult(
            text="",
            error="HTTP 503: Investigation agent is unavailable.",
            elapsed_seconds=0.3,
        )
        stdout, stderr = format_response(result)
        assert "ERROR: HTTP 503" in stderr

    def test_thread_id_marker_present_when_thread_exists(self):
        """The [THREAD_ID: ...] machine-readable marker must be on stdout."""
        result = InvestigationResult(
            text="Some answer.",
            thread_id="thread_WiKg1AUU3zWRerCQPaNNF79V",
            elapsed_seconds=1.0,
            was_continued=False,
        )
        stdout, stderr = format_response(result)
        # Marker must be on its own line at the end
        lines = stdout.strip().split("\n")
        assert lines[-1] == "[THREAD_ID: thread_WiKg1AUU3zWRerCQPaNNF79V]"
