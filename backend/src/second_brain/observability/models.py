"""Pydantic models for App Insights query results."""

from pydantic import BaseModel, computed_field, field_validator


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

    @field_validator("component", "capture_trace_id", mode="before")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        """Normalize empty strings to None.

        Same fix as FailureRecord -- applied here for symmetry so
        trace_lifecycle output is consistent with recent_errors.
        """
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v


class FailureRecord(BaseModel):
    """A single row from the recent-failures query."""

    timestamp: str
    item_type: str
    severity_level: int | None = None
    message: str
    component: str | None = None
    capture_trace_id: str | None = None

    @field_validator("component", "capture_trace_id", mode="before")
    @classmethod
    def _empty_to_none(cls, v: str | None) -> str | None:
        """Normalize empty strings to None.

        KQL's tostring(Properties.<missing_field>) returns "" not null.
        Without this validator, the agent receives "component": "" and
        renders blank table cells, which users mistake for broken data.
        """
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        return v

    @computed_field
    @property
    def capture_trace_id_short(self) -> str | None:
        """First 8 chars of the trace ID, or None if absent.

        The agent renders this in the Trace ID table column to keep
        the table layout compact. The full ID is rendered separately
        in a footer line for Phase 18 mobile-tap compatibility.
        """
        if self.capture_trace_id is None:
            return None
        return self.capture_trace_id[:8]


class FailureQueryResult(BaseModel):
    """Result wrapper for recent_failures queries with total count metadata.

    Allows the recent_errors tool to report 'showing N of M' when results
    are capped, instead of silently dropping rows past the limit.
    """

    total_count: int  # true total before the take N cap
    returned_count: int  # actual rows returned (<= total_count)
    truncated: bool  # True if returned_count < total_count
    records: list[FailureRecord]


class HealthSummary(BaseModel):
    """Aggregated system health metrics for a time window."""

    capture_count: int = 0
    success_rate: float | None = None
    error_count: int = 0
    failed_capture_count: int = 0
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
