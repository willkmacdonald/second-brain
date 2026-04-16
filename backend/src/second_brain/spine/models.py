"""Pydantic models for the spine: ingest events, status responses, envelope."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, RootModel

STALE_FRESHNESS_SECONDS = 999_999
"""Sentinel freshness value meaning 'no data available' — used in status responses."""


# ---------------------------------------------------------------------------
# Ingest event payloads (discriminated by event_type)
# ---------------------------------------------------------------------------


class LivenessPayload(BaseModel):
    """Liveness signal: 'I exist and my process is up.'"""

    instance_id: str


class ReadinessCheck(BaseModel):
    """Single readiness probe result."""

    name: str
    status: Literal["ok", "failing"]
    detail: str | None = None


class ReadinessPayload(BaseModel):
    """Readiness signal: 'My dependencies are reachable.'"""

    checks: list[ReadinessCheck]


class WorkloadPayload(BaseModel):
    """Workload signal: 'I just finished an operation; here is how it went.'"""

    operation: str
    outcome: Literal["success", "failure", "degraded"]
    duration_ms: int
    correlation_kind: Literal["capture", "thread", "request", "crud"] | None = None
    correlation_id: str | None = None
    error_class: str | None = None


# ---------------------------------------------------------------------------
# Discriminated IngestEvent
# ---------------------------------------------------------------------------


class _LivenessEvent(BaseModel):
    segment_id: str
    event_type: Literal["liveness"]
    timestamp: datetime
    payload: LivenessPayload


class _ReadinessEvent(BaseModel):
    segment_id: str
    event_type: Literal["readiness"]
    timestamp: datetime
    payload: ReadinessPayload


class _WorkloadEvent(BaseModel):
    segment_id: str
    event_type: Literal["workload"]
    timestamp: datetime
    payload: WorkloadPayload


class IngestEvent(
    RootModel[
        Annotated[
            _LivenessEvent | _ReadinessEvent | _WorkloadEvent,
            Field(discriminator="event_type"),
        ]
    ]
):
    """Discriminated ingest event from any segment.

    Callers parse with `IngestEvent.model_validate(d)` and read the concrete
    variant via `.root`.
    """


# ---------------------------------------------------------------------------
# Status responses
# ---------------------------------------------------------------------------


SegmentStatus = Literal["green", "yellow", "red", "stale"]


class RollupInfo(BaseModel):
    """Rollup annotation on a segment status."""

    suppressed: bool
    suppressed_by: str | None
    raw_status: SegmentStatus


class SegmentStatusResponse(BaseModel):
    """Single segment tile in the status board."""

    id: str
    name: str
    status: SegmentStatus
    headline: str
    last_updated: datetime
    freshness_seconds: int
    host_segment: str | None
    rollup: RollupInfo


class ResponseEnvelope(BaseModel):
    """Delivery metadata included on every spine response."""

    generated_at: datetime
    freshness_seconds: int
    partial_sources: list[str] = Field(default_factory=list)
    query_latency_ms: int
    native_url: str | None = None
    cursor: str | None = None


class StatusBoardResponse(BaseModel):
    """Response shape for GET /api/spine/status."""

    segments: list[SegmentStatusResponse]
    envelope: ResponseEnvelope


# ---------------------------------------------------------------------------
# Correlation responses
# ---------------------------------------------------------------------------


CorrelationKind = Literal["capture", "thread", "request", "crud"]


class CorrelationEvent(BaseModel):
    """One segment's appearance in a correlation timeline."""

    segment_id: str
    timestamp: datetime
    status: SegmentStatus
    headline: str


class CorrelationResponse(BaseModel):
    """Response shape for GET /api/spine/correlation/{kind}/{id}."""

    correlation_kind: CorrelationKind
    correlation_id: str
    events: list[CorrelationEvent]
    envelope: ResponseEnvelope


# ---------------------------------------------------------------------------
# Segment detail responses
# ---------------------------------------------------------------------------


class SegmentDetailResponse(BaseModel):
    """Response shape for GET /api/spine/segment/{id}.

    `data` is intentionally a free-form dict because each segment returns
    its native shape. The `data` MUST include a `schema` field that the
    web UI uses to dispatch to the correct renderer.
    """

    data: dict[str, Any]
    envelope: ResponseEnvelope


def parse_cosmos_ts(s: str) -> datetime:
    """Parse an ISO timestamp returned by Cosmos (tolerates 'Z' suffix)."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
