"""Async query functions for App Insights via Log Analytics workspace."""

import logging
from datetime import timedelta

from azure.monitor.query import LogsQueryStatus
from azure.monitor.query.aio import LogsQueryClient

from second_brain.observability.kql_templates import (
    ADMIN_AUDIT_LOG,
    CAPTURE_TRACE,
    LATEST_CAPTURE_TRACE_ID,
    RECENT_FAILURES,
    RECENT_FAILURES_FILTERED,
    SYSTEM_HEALTH,
    SYSTEM_HEALTH_ENHANCED,
    USAGE_PATTERNS_BY_BUCKET,
    USAGE_PATTERNS_BY_DESTINATION,
    USAGE_PATTERNS_BY_PERIOD,
)
from second_brain.observability.models import (
    AdminAuditRecord,
    EnhancedHealthSummary,
    FailureRecord,
    HealthSummary,
    QueryResult,
    TraceRecord,
    UsagePatternRecord,
)

logger = logging.getLogger(__name__)


async def execute_kql(
    client: LogsQueryClient,
    workspace_id: str,
    query: str,
    timespan: timedelta = timedelta(hours=24),
    server_timeout: int = 60,
) -> QueryResult:
    """Execute a KQL query against a Log Analytics workspace.

    Detects partial results (server timeout or row-limit hit) and flags
    them in the returned QueryResult.

    Args:
        client: Log Analytics query client.
        workspace_id: Log Analytics workspace ID.
        query: KQL query string.
        timespan: Time window for the query.
        server_timeout: Server-side timeout in seconds (default 60).
            Investigation Agent queries use 30 to leave headroom under
            the 60-second agent timeout.
    """
    response = await client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=timespan,
        server_timeout=server_timeout,
    )

    if response.status == LogsQueryStatus.SUCCESS:
        tables: list[list[dict]] = []
        for table in response.tables:
            columns = [col.name for col in table.columns]
            rows = [dict(zip(columns, row, strict=True)) for row in table.rows]
            tables.append(rows)
        return QueryResult(tables=tables, is_partial=False)

    if response.status == LogsQueryStatus.PARTIAL:
        logger.warning(
            "Partial query result -- server may have timed out or hit row limit"
        )
        tables = []
        if response.partial_data:
            for table in response.partial_data:
                columns = [col.name for col in table.columns]
                rows = [dict(zip(columns, row, strict=True)) for row in table.rows]
                tables.append(rows)
        return QueryResult(
            tables=tables,
            is_partial=True,
            partial_error=str(response.partial_error)
            if response.partial_error
            else None,
        )

    # Unexpected status -- treat as empty
    logger.error("Unexpected query status: %s", response.status)
    return QueryResult(tables=[], is_partial=False)


async def query_capture_trace(
    client: LogsQueryClient,
    workspace_id: str,
    trace_id: str,
) -> list[TraceRecord]:
    """Trace a specific capture through its full lifecycle."""
    query = CAPTURE_TRACE.format(trace_id=trace_id)
    result = await execute_kql(client, workspace_id, query)

    if not result.tables or not result.tables[0]:
        return []

    records: list[TraceRecord] = []
    for row in result.tables[0]:
        records.append(
            TraceRecord(
                timestamp=str(row.get("timestamp", "")),
                item_type=str(row.get("ItemType", "")),
                severity_level=row.get("severityLevel"),
                message=str(row.get("Message", "")),
                component=row.get("Component"),
                capture_trace_id=row.get("CaptureTraceId"),
            )
        )
    return records


async def query_recent_failures(
    client: LogsQueryClient,
    workspace_id: str,
) -> list[FailureRecord]:
    """Return ERROR-level logs and unhandled exceptions from the last 24h."""
    result = await execute_kql(client, workspace_id, RECENT_FAILURES)

    if not result.tables or not result.tables[0]:
        return []

    records: list[FailureRecord] = []
    for row in result.tables[0]:
        records.append(
            FailureRecord(
                timestamp=str(row.get("timestamp", "")),
                item_type=str(row.get("ItemType", "")),
                severity_level=row.get("severityLevel"),
                message=str(row.get("Message", "")),
                component=row.get("Component"),
                capture_trace_id=row.get("CaptureTraceId"),
            )
        )
    return records


async def query_system_health(
    client: LogsQueryClient,
    workspace_id: str,
) -> HealthSummary:
    """Return aggregated system health metrics for the last 24h."""
    result = await execute_kql(client, workspace_id, SYSTEM_HEALTH)

    if not result.tables or not result.tables[0]:
        return HealthSummary()

    row = result.tables[0][0]
    capture_count = int(row.get("capture_count", 0) or 0)
    successful = int(row.get("successful_count", 0) or 0)
    success_rate: float | None = None
    if capture_count > 0:
        success_rate = round(100.0 * successful / capture_count, 1)

    return HealthSummary(
        capture_count=capture_count,
        success_rate=success_rate,
        error_count=int(row.get("error_log_count", 0) or 0),
        avg_duration_ms=row.get("avg_duration_ms"),
        admin_processing_count=int(row.get("admin_processing_count", 0) or 0),
    )


async def query_admin_audit(
    client: LogsQueryClient,
    workspace_id: str,
) -> list[AdminAuditRecord]:
    """Return Admin Agent activity logs from the last 24h."""
    result = await execute_kql(client, workspace_id, ADMIN_AUDIT_LOG)

    if not result.tables or not result.tables[0]:
        return []

    records: list[AdminAuditRecord] = []
    for row in result.tables[0]:
        records.append(
            AdminAuditRecord(
                timestamp=str(row.get("timestamp", "")),
                severity_level=row.get("severityLevel"),
                message=str(row.get("Message", "")),
                capture_trace_id=row.get("CaptureTraceId"),
                component=row.get("Component"),
            )
        )
    return records


# ---------------------------------------------------------------------------
# New query functions for Phase 17 Investigation Agent
# ---------------------------------------------------------------------------

# Severity string to KQL severity level mapping
_SEVERITY_MAP: dict[str, int] = {
    "warning": 3,
    "error": 4,
}


async def query_latest_capture_trace_id(
    client: LogsQueryClient,
    workspace_id: str,
    timespan: timedelta = timedelta(hours=24),
) -> str | None:
    """Return the most recent capture trace ID, or None if no captures found."""
    result = await execute_kql(
        client,
        workspace_id,
        LATEST_CAPTURE_TRACE_ID,
        timespan=timespan,
        server_timeout=30,
    )

    if not result.tables or not result.tables[0]:
        return None

    row = result.tables[0][0]
    trace_id = row.get("trace_id")
    if trace_id and str(trace_id).strip():
        return str(trace_id).strip()
    return None


async def query_enhanced_system_health(
    client: LogsQueryClient,
    workspace_id: str,
    time_range_kql: str = "24h",
    timespan: timedelta | None = None,
) -> EnhancedHealthSummary:
    """Return system health with P95/P99 latency and trend comparison.

    Args:
        client: Log Analytics query client.
        workspace_id: Log Analytics workspace ID.
        time_range_kql: KQL duration literal (e.g., "24h", "7d") for the
            template's {time_range} parameter.
        timespan: Total timespan for the execute_kql call. Should be 2x
            the time_range to cover both current and previous periods.
            Defaults to 2x the parsed time_range.
    """
    query = SYSTEM_HEALTH_ENHANCED.format(time_range=time_range_kql)

    # Default timespan to 2x time_range if not explicitly provided
    if timespan is None:
        timespan = _parse_kql_duration(time_range_kql) * 2

    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timespan,
        server_timeout=30,
    )

    if not result.tables or not result.tables[0]:
        return EnhancedHealthSummary()

    row = result.tables[0][0]
    capture_count = int(row.get("capture_count", 0) or 0)
    successful = int(row.get("successful_count", 0) or 0)
    success_rate: float | None = None
    if capture_count > 0:
        success_rate = round(100.0 * successful / capture_count, 1)

    return EnhancedHealthSummary(
        capture_count=capture_count,
        success_rate=success_rate,
        error_count=int(row.get("error_count", 0) or 0),
        avg_duration_ms=row.get("avg_duration_ms"),
        p95_duration_ms=row.get("p95_duration_ms"),
        p99_duration_ms=row.get("p99_duration_ms"),
        admin_processing_count=int(row.get("admin_processing_count", 0) or 0),
        prev_capture_count=int(row.get("prev_capture_count", 0) or 0),
        prev_error_count=int(row.get("prev_error_count", 0) or 0),
    )


async def query_recent_failures_filtered(
    client: LogsQueryClient,
    workspace_id: str,
    component: str | None = None,
    severity: str = "error",
    limit: int = 10,
    timespan: timedelta = timedelta(hours=24),
) -> list[FailureRecord]:
    """Return recent failures with optional component filter and severity level.

    Args:
        client: Log Analytics query client.
        workspace_id: Log Analytics workspace ID.
        component: Filter by component name (e.g., "classifier", "admin_agent").
            None for all components.
        severity: Minimum severity: "warning" (level 3) or "error" (level 4).
        limit: Maximum number of rows to return (default 10).
        timespan: Time window for the query.
    """
    severity_level = _SEVERITY_MAP.get(severity, 4)

    # Build component filter clause
    component_filter = ""
    if component:
        component_filter = (
            f'| where tostring(customDimensions.component) == "{component}"\n'
        )

    query = RECENT_FAILURES_FILTERED.format(
        component_filter=component_filter,
        severity_filter=severity_level,
        limit=limit,
    )

    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timespan,
        server_timeout=30,
    )

    if not result.tables or not result.tables[0]:
        return []

    records: list[FailureRecord] = []
    for row in result.tables[0]:
        records.append(
            FailureRecord(
                timestamp=str(row.get("timestamp", "")),
                item_type=str(row.get("ItemType", "")),
                severity_level=row.get("severityLevel"),
                message=str(row.get("Message", "")),
                component=row.get("Component"),
                capture_trace_id=row.get("CaptureTraceId"),
            )
        )
    return records


async def query_usage_patterns(
    client: LogsQueryClient,
    workspace_id: str,
    group_by: str = "day",
    time_range_kql: str = "7d",
    timespan: timedelta | None = None,
) -> list[UsagePatternRecord]:
    """Return usage pattern records grouped by the specified dimension.

    Args:
        client: Log Analytics query client.
        workspace_id: Log Analytics workspace ID.
        group_by: Grouping dimension -- "day", "hour", "bucket", or "destination".
        time_range_kql: KQL duration literal for time-based queries.
        timespan: Time window for the execute_kql call. Defaults to the
            parsed time_range_kql value.
    """
    if timespan is None:
        timespan = _parse_kql_duration(time_range_kql)

    if group_by == "day":
        query = USAGE_PATTERNS_BY_PERIOD.format(bin_size="1d")
    elif group_by == "hour":
        query = USAGE_PATTERNS_BY_PERIOD.format(bin_size="1h")
    elif group_by == "bucket":
        query = USAGE_PATTERNS_BY_BUCKET
    elif group_by == "destination":
        query = USAGE_PATTERNS_BY_DESTINATION
    else:
        logger.warning("Unknown group_by value: %s, defaulting to 'day'", group_by)
        query = USAGE_PATTERNS_BY_PERIOD.format(bin_size="1d")

    result = await execute_kql(
        client,
        workspace_id,
        query,
        timespan=timespan,
        server_timeout=30,
    )

    if not result.tables or not result.tables[0]:
        return []

    records: list[UsagePatternRecord] = []
    for row in result.tables[0]:
        # Determine the label column based on group_by
        if group_by in ("day", "hour"):
            label = str(row.get("timestamp", ""))
            count = int(row.get("capture_count", 0) or 0)
        elif group_by == "bucket":
            label = str(row.get("bucket", ""))
            count = int(row.get("count_", 0) or 0)
        elif group_by == "destination":
            label = str(row.get("destination", ""))
            count = int(row.get("count_", 0) or 0)
        else:
            label = str(row.get("timestamp", ""))
            count = int(row.get("capture_count", 0) or 0)

        records.append(UsagePatternRecord(label=label, count=count))
    return records


def _parse_kql_duration(kql_duration: str) -> timedelta:
    """Parse a KQL duration literal (e.g., '24h', '7d') into a timedelta."""
    _duration_map: dict[str, timedelta] = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
    }
    result = _duration_map.get(kql_duration)
    if result is not None:
        return result
    logger.warning("Unknown KQL duration '%s', defaulting to 24h", kql_duration)
    return timedelta(hours=24)
