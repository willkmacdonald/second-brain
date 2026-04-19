"""Tests for the spine-aware SSE stream wrapper."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.stream_wrapper import spine_stream_wrapper


async def _fake_stream():
    yield "data: {}\n\n"
    yield "data: {}\n\n"


async def _failing_stream():
    yield "data: {}\n\n"
    raise RuntimeError("stream broke")


@pytest.mark.asyncio
async def test_wrapper_emits_success_on_normal_completion() -> None:
    repo = AsyncMock()
    events = []
    async for event in spine_stream_wrapper(
        _fake_stream(),
        repo=repo,
        segment_id="classifier",
        operation="classify",
        capture_trace_id="trace-1",
    ):
        events.append(event)
    assert len(events) == 2
    repo.record_event.assert_called_once()
    emitted = repo.record_event.call_args.args[0]
    # SPIKE-MEMO §5.1 — wrapper now wraps in IngestEvent(root=...).
    assert emitted.root.payload.outcome == "success"
    assert emitted.root.segment_id == "classifier"


@pytest.mark.asyncio
async def test_wrapper_emits_failure_on_exception() -> None:
    repo = AsyncMock()
    with pytest.raises(RuntimeError, match="stream broke"):
        async for _ in spine_stream_wrapper(
            _failing_stream(),
            repo=repo,
            segment_id="classifier",
            operation="classify",
        ):
            pass
    emitted = repo.record_event.call_args.args[0]
    assert emitted.root.payload.outcome == "failure"
    assert emitted.root.payload.error_class == "RuntimeError"


@pytest.mark.asyncio
async def test_wrapper_records_duration() -> None:
    repo = AsyncMock()
    async for _ in spine_stream_wrapper(
        _fake_stream(),
        repo=repo,
        segment_id="investigation",
        operation="answer_question",
    ):
        pass
    emitted = repo.record_event.call_args.args[0]
    assert emitted.root.payload.duration_ms >= 0
