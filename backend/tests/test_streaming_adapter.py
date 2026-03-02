"""Unit tests for SSE encoding, event constructors, and call_id pairing.

Tests the streaming/sse.py module which provides the wire format for
AG-UI SSE events consumed by the mobile Expo app, plus adapter.py's
call_id-based pairing logic for batched tool calls.
"""

import json

from agent_framework import Content

from second_brain.streaming.adapter import _parse_args, _parse_result
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

    def test_classified_event_single_no_extra_fields(self) -> None:
        """Single-bucket classified_event must NOT include buckets/itemIds keys."""
        event = classified_event("item-123", "Admin", 0.85)
        assert "buckets" not in event["value"]
        assert "itemIds" not in event["value"]

    def test_classified_event_multi_bucket(self) -> None:
        """Multi-bucket classified_event includes buckets and itemIds arrays."""
        event = classified_event(
            "id-1", "Admin", 0.85,
            buckets=["Admin", "Ideas"],
            item_ids=["id-1", "id-2"],
        )
        assert event == {
            "type": "CLASSIFIED",
            "value": {
                "inboxItemId": "id-1",
                "bucket": "Admin",
                "confidence": 0.85,
                "buckets": ["Admin", "Ideas"],
                "itemIds": ["id-1", "id-2"],
            },
        }

    def test_classified_event_buckets_only(self) -> None:
        """When only buckets is provided (no item_ids), only buckets appears."""
        event = classified_event(
            "id-1", "Admin", 0.85,
            buckets=["Admin", "Ideas"],
        )
        assert event["value"]["buckets"] == ["Admin", "Ideas"]
        assert "itemIds" not in event["value"]

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


class TestCallIdPairing:
    """Verify call_id attribute availability on Content objects.

    The adapter's pending_calls dict relies on call_id being present on
    both function_call and function_result Content objects. These tests
    confirm the SDK contract that makes the fix possible.
    """

    def test_function_call_has_call_id(self) -> None:
        """function_call Content exposes call_id attribute."""
        content = Content.from_function_call(
            "call-abc-123",
            "file_capture",
            arguments={"bucket": "Admin", "confidence": 0.9},
        )
        assert content.type == "function_call"
        assert content.call_id == "call-abc-123"
        assert content.name == "file_capture"

    def test_function_result_has_call_id(self) -> None:
        """function_result Content exposes call_id matching its function_call."""
        content = Content.from_function_result(
            "call-abc-123",
            result={"bucket": "Admin", "item_id": "item-1"},
        )
        assert content.type == "function_result"
        assert content.call_id == "call-abc-123"

    def test_two_function_calls_have_distinct_call_ids(self) -> None:
        """Multiple function_call Contents maintain distinct call_ids."""
        fc1 = Content.from_function_call(
            "call-1",
            "file_capture",
            arguments={"bucket": "Admin", "text": "need milk"},
        )
        fc2 = Content.from_function_call(
            "call-2",
            "file_capture",
            arguments={"bucket": "People", "text": "call the vet"},
        )
        assert fc1.call_id != fc2.call_id
        assert fc1.call_id == "call-1"
        assert fc2.call_id == "call-2"

    def test_pending_calls_pattern_pairs_correctly(self) -> None:
        """Simulate the adapter's pending_calls dict pairing logic.

        This replicates the exact pattern used in stream_text_capture:
        1. Two function_calls arrive (simulating batched SDK update)
        2. Two function_results arrive (simulating batched SDK update)
        3. Each result is paired with its call via call_id
        """
        # Simulate: two function_call contents in one update
        pending_calls: dict[str, dict] = {}
        fc1 = Content.from_function_call(
            "call-1",
            "file_capture",
            arguments={
                "bucket": "Admin",
                "text": "need milk",
                "confidence": 0.9,
                "status": "classified",
            },
        )
        fc2 = Content.from_function_call(
            "call-2",
            "file_capture",
            arguments={
                "bucket": "People",
                "text": "call the vet",
                "confidence": 0.8,
                "status": "classified",
            },
        )
        for fc in [fc1, fc2]:
            call_id = getattr(fc, "call_id", None)
            name = getattr(fc, "name", None)
            if call_id and name:
                pending_calls[call_id] = {
                    "name": name,
                    "args": _parse_args(getattr(fc, "arguments", {})),
                }

        assert len(pending_calls) == 2
        assert "call-1" in pending_calls
        assert "call-2" in pending_calls
        assert pending_calls["call-1"]["args"]["text"] == "need milk"
        assert pending_calls["call-2"]["args"]["text"] == "call the vet"

        # Simulate: two function_result contents in one update
        file_capture_results: list[dict] = []
        fr1 = Content.from_function_result(
            "call-1",
            result='{"bucket": "Admin", "item_id": "item-1", "confidence": 0.9}',
        )
        fr2 = Content.from_function_result(
            "call-2",
            result='{"bucket": "People", "item_id": "item-2", "confidence": 0.8}',
        )
        for fr in [fr1, fr2]:
            call_id = getattr(fr, "call_id", None)
            if call_id and call_id in pending_calls:
                call_info = pending_calls.pop(call_id)
                if call_info["name"] == "file_capture":
                    parsed = _parse_result(getattr(fr, "result", None))
                    if parsed is not None:
                        merged = {**call_info["args"], **parsed}
                        file_capture_results.append(merged)

        assert len(file_capture_results) == 2
        # First result: args from call-1, result from call-1
        assert file_capture_results[0]["text"] == "need milk"
        assert file_capture_results[0]["item_id"] == "item-1"
        assert file_capture_results[0]["bucket"] == "Admin"
        # Second result: args from call-2, result from call-2
        assert file_capture_results[1]["text"] == "call the vet"
        assert file_capture_results[1]["item_id"] == "item-2"
        assert file_capture_results[1]["bucket"] == "People"
        # pending_calls should be empty after processing
        assert len(pending_calls) == 0
