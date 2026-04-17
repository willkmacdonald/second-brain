"""Tests for the agent workload-emission helper."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.agent_emitter import emit_agent_workload


@pytest.mark.asyncio
async def test_emit_agent_workload_with_capture_correlation() -> None:
    repo = AsyncMock()
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="success",
        duration_ms=234,
        capture_trace_id="trace-1",
        run_id="run-abc",
        thread_id="thr-xyz",
    )
    repo.record_event.assert_called_once()
    event = repo.record_event.call_args.args[0]
    assert event.segment_id == "classifier"
    assert event.event_type == "workload"
    assert event.payload.correlation_kind == "capture"
    assert event.payload.correlation_id == "trace-1"


@pytest.mark.asyncio
async def test_emit_agent_workload_thread_correlation_when_no_capture() -> None:
    repo = AsyncMock()
    await emit_agent_workload(
        repo=repo,
        segment_id="investigation",
        operation="answer_question",
        outcome="success",
        duration_ms=4000,
        capture_trace_id=None,
        run_id="run-abc",
        thread_id="thr-xyz",
    )
    event = repo.record_event.call_args.args[0]
    assert event.payload.correlation_kind == "thread"
    assert event.payload.correlation_id == "thr-xyz"


@pytest.mark.asyncio
async def test_emit_agent_workload_failure_includes_error_class() -> None:
    repo = AsyncMock()
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="failure",
        duration_ms=100,
        capture_trace_id="trace-1",
        run_id="run-abc",
        thread_id=None,
        error_class="HttpResponseError",
    )
    event = repo.record_event.call_args.args[0]
    assert event.payload.error_class == "HttpResponseError"


@pytest.mark.asyncio
async def test_emit_agent_workload_never_raises_on_repo_failure() -> None:
    repo = AsyncMock()
    repo.record_event.side_effect = RuntimeError("cosmos down")
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="success",
        duration_ms=10,
        capture_trace_id="trace-1",
        run_id=None,
        thread_id=None,
    )
