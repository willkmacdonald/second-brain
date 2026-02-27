"""Unit tests for SSE encoding and event constructors.

Tests the streaming/sse.py module which provides the wire format for
AG-UI SSE events consumed by the mobile Expo app. Does NOT test the
async generator functions (adapter.py) -- those require mocked Foundry
clients and are integration test territory.
"""

import json

from second_brain.streaming.sse import (
    classified_event,
    complete_event,
    encode_sse,
    error_event,
    misunderstood_event,
    step_end_event,
    step_start_event,
    unresolved_event,
)


class TestEncodeSSE:
    """Test the SSE wire format encoder."""

    def test_format_basic_dict(self) -> None:
        """encode_sse produces 'data: {json}\\n\\n' format."""
        result = encode_sse({"type": "TEST"})
        assert result == 'data: {"type": "TEST"}\n\n'

    def test_format_starts_with_data_prefix(self) -> None:
        """SSE lines must start with 'data: '."""
        result = encode_sse({"key": "value"})
        assert result.startswith("data: ")

    def test_format_ends_with_double_newline(self) -> None:
        """SSE events must end with \\n\\n for proper event separation."""
        result = encode_sse({"key": "value"})
        assert result.endswith("\n\n")

    def test_payload_is_valid_json(self) -> None:
        """The data between 'data: ' and '\\n\\n' must be valid JSON."""
        result = encode_sse({"nested": {"a": 1}})
        json_str = result.removeprefix("data: ").rstrip("\n")
        parsed = json.loads(json_str)
        assert parsed == {"nested": {"a": 1}}

    def test_no_event_field(self) -> None:
        """SSE output must NOT contain an 'event:' field.

        react-native-sse defaults to 'message' event type when no
        event field is present. Adding one would break the mobile client.
        """
        result = encode_sse({"type": "TEST"})
        assert "event:" not in result


class TestEventConstructors:
    """Test that event constructor functions produce correct dict structures."""

    def test_step_start_event(self) -> None:
        event = step_start_event("Classifying")
        assert event == {"type": "STEP_START", "stepName": "Classifying"}

    def test_step_end_event(self) -> None:
        event = step_end_event("Classifying")
        assert event == {"type": "STEP_END", "stepName": "Classifying"}

    def test_classified_event(self) -> None:
        event = classified_event("item-123", "Admin", 0.85)
        assert event == {
            "type": "CLASSIFIED",
            "value": {
                "inboxItemId": "item-123",
                "bucket": "Admin",
                "confidence": 0.85,
            },
        }

    def test_misunderstood_event(self) -> None:
        event = misunderstood_event("thread-1", "item-456", "Could you clarify?")
        assert event == {
            "type": "MISUNDERSTOOD",
            "value": {
                "threadId": "thread-1",
                "inboxItemId": "item-456",
                "questionText": "Could you clarify?",
            },
        }

    def test_unresolved_event(self) -> None:
        event = unresolved_event("item-789")
        assert event == {
            "type": "UNRESOLVED",
            "value": {
                "inboxItemId": "item-789",
            },
        }

    def test_complete_event(self) -> None:
        event = complete_event("thread-1", "run-42")
        assert event == {
            "type": "COMPLETE",
            "threadId": "thread-1",
            "runId": "run-42",
        }

    def test_error_event(self) -> None:
        event = error_event("Agent timed out")
        assert event == {
            "type": "ERROR",
            "message": "Agent timed out",
        }


class TestEventTypeNames:
    """Verify event type names match the Phase 8 contract.

    These names replaced the old AG-UI/v1 names:
      STEP_STARTED -> STEP_START
      STEP_FINISHED -> STEP_END
      RUN_FINISHED -> COMPLETE
      RUN_ERROR -> ERROR
      CUSTOM(CLASSIFIED) -> CLASSIFIED (top-level)
      CUSTOM(MISUNDERSTOOD) -> MISUNDERSTOOD (top-level)
      CUSTOM(UNRESOLVED) -> UNRESOLVED (top-level)
    """

    def test_step_start_not_started(self) -> None:
        """Must be STEP_START, not STEP_STARTED."""
        assert step_start_event("x")["type"] == "STEP_START"

    def test_step_end_not_finished(self) -> None:
        """Must be STEP_END, not STEP_FINISHED."""
        assert step_end_event("x")["type"] == "STEP_END"

    def test_complete_not_run_finished(self) -> None:
        """Must be COMPLETE, not RUN_FINISHED."""
        assert complete_event("t", "r")["type"] == "COMPLETE"

    def test_error_not_run_error(self) -> None:
        """Must be ERROR, not RUN_ERROR."""
        assert error_event("e")["type"] == "ERROR"

    def test_classified_is_top_level(self) -> None:
        """CLASSIFIED must be a top-level type, not wrapped in CUSTOM."""
        event = classified_event("id", "Admin", 0.9)
        assert event["type"] == "CLASSIFIED"
        assert "name" not in event  # No CUSTOM wrapper

    def test_misunderstood_is_top_level(self) -> None:
        """MISUNDERSTOOD must be a top-level type, not wrapped in CUSTOM."""
        event = misunderstood_event("t", "id", "q")
        assert event["type"] == "MISUNDERSTOOD"
        assert "name" not in event

    def test_unresolved_is_top_level(self) -> None:
        """UNRESOLVED must be a top-level type, not wrapped in CUSTOM."""
        event = unresolved_event("id")
        assert event["type"] == "UNRESOLVED"
        assert "name" not in event
