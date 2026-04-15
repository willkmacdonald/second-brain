"""Tests for spine Pydantic models."""

import pytest
from pydantic import ValidationError

from second_brain.spine.models import (
    IngestEvent,
    LivenessPayload,
    ReadinessPayload,
    ResponseEnvelope,
    SegmentStatusResponse,
    StatusBoardResponse,
    WorkloadPayload,
)


def test_liveness_event_parses() -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "liveness",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {"instance_id": "abc-123"},
        }
    )
    assert event.root.event_type == "liveness"
    assert isinstance(event.root.payload, LivenessPayload)
    assert event.root.payload.instance_id == "abc-123"


def test_readiness_event_parses() -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "readiness",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {"checks": [{"name": "cosmos", "status": "ok"}]},
        }
    )
    assert event.root.event_type == "readiness"
    assert isinstance(event.root.payload, ReadinessPayload)
    assert event.root.payload.checks[0].name == "cosmos"


def test_workload_event_parses() -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "workload",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {
                "operation": "POST /api/capture",
                "outcome": "success",
                "duration_ms": 234,
                "correlation_kind": "capture",
                "correlation_id": "trace-1",
            },
        }
    )
    assert event.root.event_type == "workload"
    assert isinstance(event.root.payload, WorkloadPayload)
    assert event.root.payload.outcome == "success"
    assert event.root.payload.duration_ms == 234


def test_workload_failure_includes_error_class() -> None:
    event = IngestEvent.model_validate(
        {
            "segment_id": "backend_api",
            "event_type": "workload",
            "timestamp": "2026-04-14T12:00:00Z",
            "payload": {
                "operation": "POST /api/capture",
                "outcome": "failure",
                "duration_ms": 50,
                "correlation_kind": "capture",
                "correlation_id": "trace-2",
                "error_class": "HttpResponseError",
            },
        }
    )
    assert event.root.payload.error_class == "HttpResponseError"


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        IngestEvent.model_validate(
            {
                "segment_id": "backend_api",
                "event_type": "garbage",
                "timestamp": "2026-04-14T12:00:00Z",
                "payload": {},
            }
        )


def test_status_response_envelope_present() -> None:
    response = StatusBoardResponse(
        segments=[
            SegmentStatusResponse(
                id="backend_api",
                name="Backend API",
                status="green",
                headline="Healthy",
                last_updated="2026-04-14T12:00:00Z",
                freshness_seconds=12,
                host_segment=None,
                rollup={
                    "suppressed": False,
                    "suppressed_by": None,
                    "raw_status": "green",
                },
            )
        ],
        envelope=ResponseEnvelope(
            generated_at="2026-04-14T12:00:00Z",
            freshness_seconds=12,
            partial_sources=[],
            query_latency_ms=15,
        ),
    )
    serialized = response.model_dump()
    assert "envelope" in serialized
    assert "generated_at" in serialized["envelope"]
