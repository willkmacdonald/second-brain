"""Tests for the agent workload-emission helper."""

from unittest.mock import AsyncMock

import pytest

from second_brain.spine.agent_emitter import emit_agent_workload


class _RootAccessingSpineRepo:
    """Fake SpineRepository whose record_event calls `event.root`.

    Mirrors production `SpineRepository.record_event` faithfully so the
    Pydantic RootModel shape bug (SPIKE-MEMO §5.1) surfaces at test
    time. AsyncMock-based tests below bypass this accessor and miss
    the defect.
    """

    def __init__(self) -> None:
        self.events_recorded: list = []
        self.received_types: list[type] = []

    async def record_event(self, event) -> None:  # noqa: ANN001
        self.received_types.append(type(event))
        inner = event.root  # raises AttributeError on raw _WorkloadEvent
        self.events_recorded.append(inner)


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
    # SPIKE-MEMO §5.1 — emit_agent_workload wraps in IngestEvent(root=...).
    assert event.root.segment_id == "classifier"
    assert event.root.event_type == "workload"
    assert event.root.payload.correlation_kind == "capture"
    assert event.root.payload.correlation_id == "trace-1"


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
    assert event.root.payload.correlation_kind == "thread"
    assert event.root.payload.correlation_id == "thr-xyz"


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
    assert event.root.payload.error_class == "HttpResponseError"


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


# ---------------------------------------------------------------------------
# Phase 19.2 SPIKE-MEMO §5.1 regression tests
#
# The AsyncMock-based tests above silently passed despite the
# production shape bug because they never exercise `event.root`. These
# tests use `_RootAccessingSpineRepo` (mirrors real SpineRepository)
# to surface the defect.
# ---------------------------------------------------------------------------


from second_brain.spine.models import IngestEvent  # noqa: E402


@pytest.mark.asyncio
async def test_emit_agent_workload_passes_ingest_event_to_record_event() -> None:
    """SPIKE-MEMO §5.1 — record_event must receive IngestEvent, not raw _WorkloadEvent.

    RED before the wrap fix lands at agent_emitter.py:63 (fake raises
    AttributeError the same way production does).
    """
    repo = _RootAccessingSpineRepo()
    await emit_agent_workload(
        repo=repo,
        segment_id="classifier",
        operation="classify",
        outcome="success",
        duration_ms=100,
        capture_trace_id="trace-wrap-1",
        run_id=None,
        thread_id=None,
    )
    # After the fix: record_event received an IngestEvent, and inner
    # root is the workload with the correlation tag threaded through.
    assert repo.received_types == [IngestEvent], (
        f"record_event must receive IngestEvent; got {repo.received_types}"
    )
    assert len(repo.events_recorded) == 1
    assert repo.events_recorded[0].payload.correlation_id == "trace-wrap-1"


@pytest.mark.asyncio
async def test_emit_agent_workload_admin_segment_lands_in_fake_repo() -> None:
    """SPIKE-MEMO §5.1 — admin emits via the same helper; inherits the fix.

    RED before the wrap fix. After fix: event lands with capture
    correlation exactly like classifier.
    """
    repo = _RootAccessingSpineRepo()
    await emit_agent_workload(
        repo=repo,
        segment_id="admin",
        operation="process_capture",
        outcome="success",
        duration_ms=2500,
        capture_trace_id="trace-admin-xyz",
        run_id=None,
        thread_id=None,
    )
    assert len(repo.events_recorded) == 1
    inner = repo.events_recorded[0]
    assert inner.segment_id == "admin"
    assert inner.payload.correlation_kind == "capture"
    assert inner.payload.correlation_id == "trace-admin-xyz"
