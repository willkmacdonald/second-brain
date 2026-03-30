"""End-to-end trace propagation tests for Phase 14.

Validates that a capture_trace_id set at the API layer propagates through
every hop in the pipeline:

  1. Capture endpoint (X-Trace-Id header extraction)
  2. Streaming adapter (OTel span attributes + ContextVar)
  3. Classifier tool (file_capture reads ContextVar, writes captureTraceId to Cosmos)
  4. Admin handoff (reads captureTraceId from inbox doc, sets span attribute)

Each test mocks the Foundry agent to emit realistic Content objects so the
adapter's call_id pairing logic runs end-to-end. No real Azure calls are made.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agent_framework import Content

from second_brain.processing.admin_handoff import process_admin_capture
from second_brain.streaming.adapter import (
    stream_text_capture,
    stream_voice_capture,
)
from second_brain.tools.classification import ClassifierTools, capture_trace_id_var


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TRACE_ID = "trace-e2e-test-abc-123"


def _make_mock_stream(contents_sequence: list[list[Content]], conversation_id="conv-1"):
    """Build a mock async streaming response from a sequence of Content lists.

    Each inner list becomes one ChatResponseUpdate yielded by the stream.
    """

    class MockUpdate:
        def __init__(self, contents, conv_id):
            self.contents = contents
            self.conversation_id = conv_id

    class MockStream:
        def __init__(self):
            self._updates = [
                MockUpdate(contents, conversation_id)
                for contents in contents_sequence
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._updates:
                raise StopAsyncIteration
            return self._updates.pop(0)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    return MockStream()


def _text_classify_stream(
    bucket: str = "Admin",
    confidence: float = 0.92,
    status: str = "classified",
    item_id: str = "inbox-trace-1",
):
    """Simulate a Classifier agent that calls file_capture once."""
    return _make_mock_stream([
        # Update 1: function_call
        [
            Content.from_function_call(
                "call-fc-1",
                "file_capture",
                arguments={
                    "text": "Add milk to the grocery list",
                    "bucket": bucket,
                    "confidence": confidence,
                    "status": status,
                    "title": "Grocery list",
                },
            ),
        ],
        # Update 2: function_result
        [
            Content.from_function_result(
                "call-fc-1",
                result=json.dumps({
                    "bucket": bucket,
                    "confidence": confidence,
                    "item_id": item_id,
                }),
            ),
        ],
    ])


def _voice_classify_stream(
    bucket: str = "Admin",
    confidence: float = 0.88,
    status: str = "classified",
    item_id: str = "inbox-voice-1",
):
    """Simulate a Classifier agent that calls transcribe_audio then file_capture."""
    return _make_mock_stream([
        # Update 1: transcribe_audio call
        [
            Content.from_function_call(
                "call-ta-1",
                "transcribe_audio",
                arguments={"blob_url": "https://blob/audio.m4a"},
            ),
        ],
        # Update 2: transcribe_audio result
        [
            Content.from_function_result(
                "call-ta-1",
                result=json.dumps({"raw": "Pick up eggs from the store"}),
            ),
        ],
        # Update 3: file_capture call
        [
            Content.from_function_call(
                "call-fc-1",
                "file_capture",
                arguments={
                    "text": "Pick up eggs from the store",
                    "bucket": bucket,
                    "confidence": confidence,
                    "status": status,
                    "title": "Eggs errand",
                },
            ),
        ],
        # Update 4: file_capture result
        [
            Content.from_function_result(
                "call-fc-1",
                result=json.dumps({
                    "bucket": bucket,
                    "confidence": confidence,
                    "item_id": item_id,
                }),
            ),
        ],
    ])


def _parse_sse_events(raw_events: list[str]) -> list[dict]:
    """Parse SSE-encoded strings into dicts."""
    parsed = []
    for raw in raw_events:
        if raw.startswith("data: "):
            json_str = raw[6:].strip()
            parsed.append(json.loads(json_str))
    return parsed


def _make_mock_tool(name: str = "add_errand_items", invocation_count: int = 0):
    """Create a mock tool with name and invocation_count attributes."""
    tool_fn = MagicMock()
    tool_fn.name = name
    tool_fn.invocation_count = invocation_count
    return tool_fn


# ---------------------------------------------------------------------------
# Text capture trace propagation
# ---------------------------------------------------------------------------


class TestTextCaptureTracePropagation:
    """Trace ID flows from adapter through ContextVar into SSE events."""

    async def test_trace_id_set_on_otel_span(self):
        """The adapter creates a span with capture.trace_id attribute."""
        client = MagicMock()
        client.get_response.return_value = _text_classify_stream()

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.streaming.adapter.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            events = []
            async for event in stream_text_capture(
                client=client,
                user_text="Add milk to the grocery list",
                tools=[],
                thread_id="thread-1",
                run_id="run-1",
                capture_trace_id=TRACE_ID,
            ):
                events.append(event)

        assert span_attrs.get("capture.trace_id") == TRACE_ID
        assert span_attrs.get("capture.type") == "text"

    async def test_trace_id_propagated_via_contextvar(self):
        """capture_trace_id_var is set during agent execution."""
        client = MagicMock()
        observed_trace_ids = []

        # Intercept what the ContextVar holds during streaming
        def _capturing_get_response(*args, **kwargs):
            observed_trace_ids.append(capture_trace_id_var.get())
            return _text_classify_stream()

        client.get_response = _capturing_get_response

        events = []
        async for event in stream_text_capture(
            client=client,
            user_text="Add milk to the grocery list",
            tools=[],
            thread_id="thread-1",
            run_id="run-1",
            capture_trace_id=TRACE_ID,
        ):
            events.append(event)

        assert TRACE_ID in observed_trace_ids

    async def test_contextvar_reset_after_stream(self):
        """capture_trace_id_var is reset to default after streaming completes."""
        client = MagicMock()
        client.get_response.return_value = _text_classify_stream()

        events = []
        async for event in stream_text_capture(
            client=client,
            user_text="test",
            tools=[],
            thread_id="t",
            run_id="r",
            capture_trace_id=TRACE_ID,
        ):
            events.append(event)

        # After the generator is exhausted, ContextVar should be reset
        assert capture_trace_id_var.get() == ""

    async def test_sse_event_sequence_complete(self):
        """Text capture produces correct SSE event sequence."""
        client = MagicMock()
        client.get_response.return_value = _text_classify_stream()

        events = []
        async for event in stream_text_capture(
            client=client,
            user_text="Add milk to the grocery list",
            tools=[],
            thread_id="thread-1",
            run_id="run-1",
            capture_trace_id=TRACE_ID,
        ):
            events.append(event)

        parsed = _parse_sse_events(events)
        types = [e["type"] for e in parsed]

        assert types == ["STEP_START", "STEP_END", "CLASSIFIED", "COMPLETE"]
        assert parsed[2]["value"]["bucket"] == "Admin"
        assert parsed[2]["value"]["confidence"] == 0.92

    async def test_classified_outcome_span_attributes(self):
        """Span records bucket, confidence, and outcome on successful classification."""
        client = MagicMock()
        client.get_response.return_value = _text_classify_stream(
            bucket="Ideas", confidence=0.78
        )

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.streaming.adapter.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            async for _ in stream_text_capture(
                client=client,
                user_text="What if we built a treehouse?",
                tools=[],
                thread_id="t",
                run_id="r",
                capture_trace_id=TRACE_ID,
            ):
                pass

        assert span_attrs["capture.outcome"] == "classified"
        assert span_attrs["capture.bucket"] == "Ideas"
        assert span_attrs["capture.confidence"] == 0.78


# ---------------------------------------------------------------------------
# Voice capture trace propagation
# ---------------------------------------------------------------------------


class TestVoiceCaptureTracePropagation:
    """Trace ID flows through voice capture: transcription -> classification."""

    async def test_trace_id_set_on_voice_span(self):
        """Voice capture span has capture.trace_id and capture.type='voice'."""
        client = MagicMock()
        client.get_response.return_value = _voice_classify_stream()

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.streaming.adapter.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            async for _ in stream_voice_capture(
                client=client,
                blob_url="https://blob/test-audio.m4a",
                tools=[],
                thread_id="thread-v1",
                run_id="run-v1",
                capture_trace_id=TRACE_ID,
            ):
                pass

        assert span_attrs["capture.trace_id"] == TRACE_ID
        assert span_attrs["capture.type"] == "voice"

    async def test_voice_sse_event_sequence(self):
        """Voice capture produces Processing step bracket with classification."""
        client = MagicMock()
        client.get_response.return_value = _voice_classify_stream()

        events = []
        async for event in stream_voice_capture(
            client=client,
            blob_url="https://blob/audio.m4a",
            tools=[],
            thread_id="thread-v1",
            run_id="run-v1",
            capture_trace_id=TRACE_ID,
        ):
            events.append(event)

        parsed = _parse_sse_events(events)
        types = [e["type"] for e in parsed]

        # Voice uses "Processing" step (not "Classifying")
        assert types == ["STEP_START", "STEP_END", "CLASSIFIED", "COMPLETE"]
        assert parsed[0]["stepName"] == "Processing"
        assert parsed[1]["stepName"] == "Processing"
        assert parsed[2]["value"]["bucket"] == "Admin"

    async def test_voice_contextvar_propagated(self):
        """capture_trace_id_var is set during voice capture agent execution."""
        client = MagicMock()
        observed = []

        def _spy(*args, **kwargs):
            observed.append(capture_trace_id_var.get())
            return _voice_classify_stream()

        client.get_response = _spy

        async for _ in stream_voice_capture(
            client=client,
            blob_url="https://blob/audio.m4a",
            tools=[],
            thread_id="t",
            run_id="r",
            capture_trace_id=TRACE_ID,
        ):
            pass

        assert TRACE_ID in observed


# ---------------------------------------------------------------------------
# Classifier tool trace propagation
# ---------------------------------------------------------------------------


class TestClassifierToolTracePropagation:
    """file_capture reads capture_trace_id_var and writes captureTraceId to Cosmos."""

    async def test_file_capture_writes_trace_id_to_inbox_doc(
        self, mock_cosmos_manager
    ):
        """Cosmos inbox document includes captureTraceId from ContextVar."""
        tools = ClassifierTools(mock_cosmos_manager, classification_threshold=0.6)

        # Simulate what the adapter does: set the ContextVar before tool call
        token = capture_trace_id_var.set(TRACE_ID)
        try:
            # Echo back the body so we can inspect it
            inbox_container = mock_cosmos_manager.get_container("Inbox")
            created_docs = []
            inbox_container.create_item = AsyncMock(
                side_effect=lambda body: created_docs.append(body)
            )

            # Also mock the bucket container
            admin_container = mock_cosmos_manager.get_container("Admin")
            admin_container.create_item = AsyncMock()

            result = await tools.file_capture(
                text="Buy milk from the store",
                bucket="Admin",
                confidence=0.85,
                status="classified",
                title="Grocery errand",
            )
        finally:
            capture_trace_id_var.reset(token)

        assert result["bucket"] == "Admin"
        assert result["item_id"]  # non-empty

        # Verify the inbox document written to Cosmos has captureTraceId
        assert len(created_docs) == 1
        assert created_docs[0]["captureTraceId"] == TRACE_ID

    async def test_file_capture_misunderstood_writes_trace_id(
        self, mock_cosmos_manager
    ):
        """Misunderstood captures also get captureTraceId on the inbox doc."""
        tools = ClassifierTools(mock_cosmos_manager)

        token = capture_trace_id_var.set(TRACE_ID)
        try:
            inbox_container = mock_cosmos_manager.get_container("Inbox")
            created_docs = []
            inbox_container.create_item = AsyncMock(
                side_effect=lambda body: created_docs.append(body)
            )

            result = await tools.file_capture(
                text="mumble mumble",
                bucket="Ideas",
                confidence=0.3,
                status="misunderstood",
                title="Unclear",
            )
        finally:
            capture_trace_id_var.reset(token)

        assert len(created_docs) == 1
        assert created_docs[0]["captureTraceId"] == TRACE_ID
        assert created_docs[0]["status"] == "misunderstood"

    async def test_file_capture_no_trace_id_skips_field(self, mock_cosmos_manager):
        """When trace ID is empty, captureTraceId is not written to the doc."""
        tools = ClassifierTools(mock_cosmos_manager)

        token = capture_trace_id_var.set("")
        try:
            inbox_container = mock_cosmos_manager.get_container("Inbox")
            created_docs = []
            inbox_container.create_item = AsyncMock(
                side_effect=lambda body: created_docs.append(body)
            )
            admin_container = mock_cosmos_manager.get_container("Admin")
            admin_container.create_item = AsyncMock()

            await tools.file_capture(
                text="test",
                bucket="Admin",
                confidence=0.9,
                status="classified",
                title="Test",
            )
        finally:
            capture_trace_id_var.reset(token)

        assert "captureTraceId" not in created_docs[0]


# ---------------------------------------------------------------------------
# Admin handoff trace propagation
# ---------------------------------------------------------------------------


class TestAdminHandoffTracePropagation:
    """Trace ID flows from inbox doc through Admin Agent processing."""

    async def test_admin_reads_trace_id_from_inbox_doc(self, mock_cosmos_manager):
        """process_admin_capture reads captureTraceId from the inbox document."""
        inbox_container = mock_cosmos_manager.get_container("Inbox")
        inbox_doc = {
            "id": "inbox-admin-1",
            "userId": "will",
            "rawText": "need cat litter",
            "captureTraceId": TRACE_ID,
            "adminProcessingStatus": None,
        }
        inbox_container.read_item = AsyncMock(return_value=inbox_doc.copy())

        admin_tool = _make_mock_tool("add_errand_items", invocation_count=0)

        admin_client = AsyncMock()
        response = MagicMock()
        response.text = "Added cat litter to pet store"

        async def _get_response(*args, **kwargs):
            admin_tool.invocation_count += 1
            return response

        admin_client.get_response = AsyncMock(side_effect=_get_response)

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.processing.admin_handoff.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            with patch(
                "second_brain.processing.admin_handoff.build_routing_context",
                new_callable=AsyncMock,
                return_value="Destinations: pet_store",
            ):
                await process_admin_capture(
                    admin_client=admin_client,
                    admin_tools=[admin_tool],
                    cosmos_manager=mock_cosmos_manager,
                    inbox_item_id="inbox-admin-1",
                    raw_text="need cat litter",
                    capture_trace_id="fallback-trace-id",
                )

        # Should use the trace ID from the inbox doc, not the fallback
        assert span_attrs.get("capture.trace_id") == TRACE_ID

    async def test_admin_falls_back_to_parameter_trace_id(
        self, mock_cosmos_manager
    ):
        """When inbox doc lacks captureTraceId, falls back to the parameter."""
        inbox_container = mock_cosmos_manager.get_container("Inbox")
        inbox_doc = {
            "id": "inbox-admin-2",
            "userId": "will",
            "rawText": "buy milk",
            "adminProcessingStatus": None,
            # No captureTraceId field
        }
        inbox_container.read_item = AsyncMock(return_value=inbox_doc.copy())

        admin_tool = _make_mock_tool("add_errand_items", invocation_count=0)
        admin_client = AsyncMock()
        response = MagicMock()
        response.text = "Added milk"

        async def _get_response(*args, **kwargs):
            admin_tool.invocation_count += 1
            return response

        admin_client.get_response = AsyncMock(side_effect=_get_response)

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.processing.admin_handoff.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            with patch(
                "second_brain.processing.admin_handoff.build_routing_context",
                new_callable=AsyncMock,
                return_value="Destinations: jewel",
            ):
                await process_admin_capture(
                    admin_client=admin_client,
                    admin_tools=[admin_tool],
                    cosmos_manager=mock_cosmos_manager,
                    inbox_item_id="inbox-admin-2",
                    raw_text="buy milk",
                    capture_trace_id="param-trace-id",
                )

        assert span_attrs.get("capture.trace_id") == "param-trace-id"


# ---------------------------------------------------------------------------
# Full pipeline: text capture -> classifier -> admin handoff
# ---------------------------------------------------------------------------


class TestFullPipelineTracePropagation:
    """End-to-end: trace ID flows from text capture through admin processing."""

    async def test_text_to_admin_trace_continuity(self, mock_cosmos_manager):
        """Trace ID set during text capture is available for admin handoff.

        Simulates the full flow:
        1. Text capture streams through classifier (sets ContextVar)
        2. file_capture tool writes captureTraceId to Cosmos inbox doc
        3. Admin handoff reads captureTraceId from inbox doc
        4. Admin span attributes include the same trace ID
        """
        # --- Phase 1: Text capture with classifier ---
        classifier_client = MagicMock()
        classifier_client.get_response.return_value = _text_classify_stream(
            bucket="Admin", confidence=0.92, item_id="inbox-pipeline-1"
        )

        # Set up Cosmos to capture what file_capture would write
        inbox_created_docs = []
        inbox_container = mock_cosmos_manager.get_container("Inbox")
        inbox_container.create_item = AsyncMock(
            side_effect=lambda body: inbox_created_docs.append(body)
        )
        admin_container = mock_cosmos_manager.get_container("Admin")
        admin_container.create_item = AsyncMock()

        # Collect SSE events
        sse_events = []
        async for event in stream_text_capture(
            client=classifier_client,
            user_text="Add milk to the grocery list",
            tools=[],
            thread_id="thread-pipe-1",
            run_id="run-pipe-1",
            cosmos_manager=mock_cosmos_manager,
            capture_trace_id=TRACE_ID,
        ):
            sse_events.append(event)

        # Verify SSE stream completed with CLASSIFIED
        parsed = _parse_sse_events(sse_events)
        types = [e["type"] for e in parsed]
        assert "CLASSIFIED" in types
        classified_event = next(e for e in parsed if e["type"] == "CLASSIFIED")
        assert classified_event["value"]["bucket"] == "Admin"

        # Verify ContextVar was reset
        assert capture_trace_id_var.get() == ""

        # --- Phase 2: Admin handoff reads trace from inbox doc ---
        # Simulate what Cosmos would return (the doc file_capture wrote)
        # In the real pipeline, the adapter reads the item_id from the
        # classified event and passes it to process_admin_capture
        inbox_doc_for_admin = {
            "id": "inbox-pipeline-1",
            "userId": "will",
            "rawText": "Add milk to the grocery list",
            "captureTraceId": TRACE_ID,
            "adminProcessingStatus": None,
        }
        inbox_container.read_item = AsyncMock(
            return_value=inbox_doc_for_admin.copy()
        )

        admin_tool = _make_mock_tool("add_errand_items", invocation_count=0)
        admin_client = AsyncMock()
        admin_response = MagicMock()
        admin_response.text = "Added milk to jewel"

        async def _admin_get_response(*args, **kwargs):
            admin_tool.invocation_count += 1
            return admin_response

        admin_client.get_response = AsyncMock(side_effect=_admin_get_response)

        admin_span_attrs = {}
        mock_admin_span = MagicMock()
        mock_admin_span.set_attribute = lambda k, v: admin_span_attrs.__setitem__(k, v)
        mock_admin_span.record_exception = MagicMock()

        with patch(
            "second_brain.processing.admin_handoff.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_admin_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            with patch(
                "second_brain.processing.admin_handoff.build_routing_context",
                new_callable=AsyncMock,
                return_value="Destinations: jewel",
            ):
                await process_admin_capture(
                    admin_client=admin_client,
                    admin_tools=[admin_tool],
                    cosmos_manager=mock_cosmos_manager,
                    inbox_item_id="inbox-pipeline-1",
                    raw_text="Add milk to the grocery list",
                    capture_trace_id=TRACE_ID,
                )

        # The admin span should carry the same trace ID end-to-end
        assert admin_span_attrs["capture.trace_id"] == TRACE_ID
        assert admin_span_attrs["admin.tool_invoked"] is True

    async def test_voice_to_admin_trace_continuity(self, mock_cosmos_manager):
        """Trace ID flows through voice capture -> transcription -> admin."""
        classifier_client = MagicMock()
        classifier_client.get_response.return_value = _voice_classify_stream(
            bucket="Admin", confidence=0.88, item_id="inbox-voice-pipe-1"
        )

        inbox_container = mock_cosmos_manager.get_container("Inbox")
        inbox_container.create_item = AsyncMock()
        admin_container = mock_cosmos_manager.get_container("Admin")
        admin_container.create_item = AsyncMock()

        # Collect SSE events from voice capture
        sse_events = []
        async for event in stream_voice_capture(
            client=classifier_client,
            blob_url="https://blob/voice-test.m4a",
            tools=[],
            thread_id="thread-vp-1",
            run_id="run-vp-1",
            cosmos_manager=mock_cosmos_manager,
            capture_trace_id=TRACE_ID,
        ):
            sse_events.append(event)

        parsed = _parse_sse_events(sse_events)
        types = [e["type"] for e in parsed]
        assert types == ["STEP_START", "STEP_END", "CLASSIFIED", "COMPLETE"]

        # Now simulate admin handoff with the same trace ID
        inbox_doc = {
            "id": "inbox-voice-pipe-1",
            "userId": "will",
            "rawText": "Pick up eggs from the store",
            "captureTraceId": TRACE_ID,
            "adminProcessingStatus": None,
        }
        inbox_container.read_item = AsyncMock(return_value=inbox_doc.copy())

        admin_tool = _make_mock_tool("add_errand_items", invocation_count=0)
        admin_client = AsyncMock()
        admin_response = MagicMock()
        admin_response.text = "Added eggs to grocery"

        async def _get_resp(*a, **kw):
            admin_tool.invocation_count += 1
            return admin_response

        admin_client.get_response = AsyncMock(side_effect=_get_resp)

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.processing.admin_handoff.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            with patch(
                "second_brain.processing.admin_handoff.build_routing_context",
                new_callable=AsyncMock,
                return_value="Destinations: grocery",
            ):
                await process_admin_capture(
                    admin_client=admin_client,
                    admin_tools=[admin_tool],
                    cosmos_manager=mock_cosmos_manager,
                    inbox_item_id="inbox-voice-pipe-1",
                    raw_text="Pick up eggs from the store",
                    capture_trace_id=TRACE_ID,
                )

        assert span_attrs["capture.trace_id"] == TRACE_ID


# ---------------------------------------------------------------------------
# Error paths: trace ID survives failures
# ---------------------------------------------------------------------------


class TestTraceIdSurvivesErrors:
    """Trace ID is present on spans and logs even when things go wrong."""

    async def test_trace_id_on_error_span(self):
        """When the agent raises, the span still has capture.trace_id."""
        client = MagicMock()
        client.get_response.side_effect = RuntimeError("Agent exploded")

        span_attrs = {}
        mock_span = MagicMock()
        mock_span.set_attribute = lambda k, v: span_attrs.__setitem__(k, v)
        mock_span.record_exception = MagicMock()

        with patch(
            "second_brain.streaming.adapter.tracer.start_as_current_span"
        ) as mock_tracer:
            mock_tracer.return_value.__enter__ = lambda s: mock_span
            mock_tracer.return_value.__exit__ = lambda s, *a: None

            events = []
            async for event in stream_text_capture(
                client=client,
                user_text="This will fail",
                tools=[],
                thread_id="t",
                run_id="r",
                capture_trace_id=TRACE_ID,
            ):
                events.append(event)

        # Trace ID was set on the span before the error
        assert span_attrs["capture.trace_id"] == TRACE_ID

        # Error was recorded on the span
        mock_span.record_exception.assert_called_once()

        # SSE stream still produces ERROR + COMPLETE
        parsed = _parse_sse_events(events)
        types = [e["type"] for e in parsed]
        assert "ERROR" in types
        assert "COMPLETE" in types

    async def test_contextvar_reset_after_error(self):
        """ContextVar is cleaned up even when the stream errors."""
        client = MagicMock()
        client.get_response.side_effect = RuntimeError("boom")

        events = []
        async for event in stream_text_capture(
            client=client,
            user_text="fail",
            tools=[],
            thread_id="t",
            run_id="r",
            capture_trace_id=TRACE_ID,
        ):
            events.append(event)

        # ContextVar must be reset to prevent trace ID leaking to next request
        assert capture_trace_id_var.get() == ""

    async def test_safety_net_misunderstood_preserves_trace_id(
        self, mock_cosmos_manager
    ):
        """When agent skips file_capture, safety net writes captureTraceId."""
        client = MagicMock()
        # Agent returns no tool calls -- just text reasoning
        client.get_response.return_value = _make_mock_stream([
            [MagicMock(type="text", text="I'm not sure what to do")],
        ])

        inbox_container = mock_cosmos_manager.get_container("Inbox")
        created_docs = []
        inbox_container.create_item = AsyncMock(
            side_effect=lambda body: created_docs.append(body)
        )

        events = []
        async for event in stream_text_capture(
            client=client,
            user_text="unclear mumbling",
            tools=[],
            thread_id="thread-sn",
            run_id="run-sn",
            cosmos_manager=mock_cosmos_manager,
            capture_trace_id=TRACE_ID,
        ):
            events.append(event)

        parsed = _parse_sse_events(events)
        types = [e["type"] for e in parsed]

        # Safety net produces MISUNDERSTOOD
        assert "MISUNDERSTOOD" in types

        # The safety-net Cosmos write includes captureTraceId
        assert len(created_docs) == 1
        assert created_docs[0]["captureTraceId"] == TRACE_ID
