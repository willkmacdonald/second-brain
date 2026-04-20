"""Unit tests for CaptureTraceSpanProcessor.

Verifies the SpanProcessor that injects capture_trace_id from the
ContextVar onto every OTel span created during a capture request.
"""

from unittest.mock import MagicMock

import pytest

from second_brain.observability.span_processor import CaptureTraceSpanProcessor
from second_brain.tools.classification import capture_trace_id_var


@pytest.fixture()
def processor() -> CaptureTraceSpanProcessor:
    """Return a fresh CaptureTraceSpanProcessor instance."""
    return CaptureTraceSpanProcessor()


@pytest.fixture()
def mock_span() -> MagicMock:
    """Return a mock span with is_recording() returning True."""
    span = MagicMock()
    span.is_recording.return_value = True
    return span


@pytest.fixture(autouse=True)
def _reset_contextvar():
    """Reset capture_trace_id_var to default after each test."""
    token = capture_trace_id_var.set("")
    yield
    capture_trace_id_var.reset(token)


class TestOnStart:
    """Tests for CaptureTraceSpanProcessor.on_start behaviour."""

    def test_sets_attribute_when_contextvar_has_value(
        self,
        processor: CaptureTraceSpanProcessor,
        mock_span: MagicMock,
    ) -> None:
        """Span gets capture.trace_id when ContextVar is set."""
        capture_trace_id_var.set("trace-abc-123")
        processor.on_start(mock_span)
        mock_span.set_attribute.assert_called_once_with(
            "capture.trace_id", "trace-abc-123"
        )

    def test_skips_when_contextvar_empty(
        self,
        processor: CaptureTraceSpanProcessor,
        mock_span: MagicMock,
    ) -> None:
        """Span is NOT tagged when ContextVar is empty string (default)."""
        # ContextVar is "" (default) from autouse fixture
        processor.on_start(mock_span)
        mock_span.set_attribute.assert_not_called()

    def test_skips_when_contextvar_reset_to_default(
        self,
        processor: CaptureTraceSpanProcessor,
        mock_span: MagicMock,
    ) -> None:
        """Span is NOT tagged after ContextVar is explicitly reset."""
        token = capture_trace_id_var.set("trace-xyz")
        capture_trace_id_var.reset(token)
        processor.on_start(mock_span)
        mock_span.set_attribute.assert_not_called()


class TestOnEnd:
    """Tests for CaptureTraceSpanProcessor.on_end behaviour."""

    def test_on_end_is_noop(
        self,
        processor: CaptureTraceSpanProcessor,
        mock_span: MagicMock,
    ) -> None:
        """on_end does not modify the span."""
        processor.on_end(mock_span)
        mock_span.set_attribute.assert_not_called()


class TestLifecycleMethods:
    """Tests for shutdown and force_flush."""

    def test_shutdown_is_noop(self, processor: CaptureTraceSpanProcessor) -> None:
        """shutdown() completes without error."""
        processor.shutdown()  # Should not raise

    def test_force_flush_returns_true(
        self, processor: CaptureTraceSpanProcessor
    ) -> None:
        """force_flush() returns True (nothing to flush)."""
        assert processor.force_flush() is True


class TestRegistration:
    """Static verification that CaptureTraceSpanProcessor is registered."""

    def test_processor_registered_in_main(self) -> None:
        """main.py passes CaptureTraceSpanProcessor to configure_azure_monitor."""
        from pathlib import Path

        # Read main.py source directly
        main_path = Path(__file__).parent.parent / "src" / "second_brain" / "main.py"
        source = main_path.read_text()
        assert "CaptureTraceSpanProcessor" in source, (
            "main.py must import and register CaptureTraceSpanProcessor"
        )
        assert "span_processors" in source, (
            "main.py must pass span_processors to configure_azure_monitor"
        )
