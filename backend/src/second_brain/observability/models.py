"""Pydantic models for App Insights query results."""

from pydantic import BaseModel


class QueryResult(BaseModel):
    """Generic wrapper for Log Analytics query results.

    Holds parsed table data and flags whether the server returned a partial
    result (timeout or row-limit hit).
    """

    tables: list[list[dict]]
    is_partial: bool = False
    partial_error: str | None = None


class TraceRecord(BaseModel):
    """A single row from the capture-trace query."""

    timestamp: str
    item_type: str
    severity_level: int | None = None
    message: str
    component: str | None = None
    capture_trace_id: str | None = None


class FailureRecord(BaseModel):
    """A single row from the recent-failures query."""

    timestamp: str
    item_type: str
    severity_level: int | None = None
    message: str
    component: str | None = None
    capture_trace_id: str | None = None


class HealthSummary(BaseModel):
    """Aggregated system health metrics for a time window."""

    capture_count: int = 0
    success_rate: float | None = None
    error_count: int = 0
    avg_duration_ms: float | None = None
    admin_processing_count: int = 0


class AdminAuditRecord(BaseModel):
    """A single row from the admin-agent audit query."""

    timestamp: str
    severity_level: int | None = None
    message: str
    capture_trace_id: str | None = None
    component: str | None = None


class EnhancedHealthSummary(BaseModel):
    """System health with P95/P99 latency and trend comparison."""

    capture_count: int = 0
    success_rate: float | None = None
    error_count: int = 0
    avg_duration_ms: float | None = None
    p95_duration_ms: float | None = None
    p99_duration_ms: float | None = None
    admin_processing_count: int = 0
    # Previous period for trend comparison
    prev_capture_count: int = 0
    prev_error_count: int = 0


class UsagePatternRecord(BaseModel):
    """A single row from a usage pattern query."""

    label: str  # time bin, bucket name, or destination name
    count: int = 0
