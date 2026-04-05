"""Async query functions for App Insights via Log Analytics workspace."""

import logging
from datetime import timedelta

from azure.monitor.query import LogsQueryStatus
from azure.monitor.query.aio import LogsQueryClient

from second_brain.observability.kql_templates import (
    ADMIN_AUDIT_LOG,
    CAPTURE_TRACE,
    RECENT_FAILURES,
    SYSTEM_HEALTH,
)
from second_brain.observability.models import (
    AdminAuditRecord,
    FailureRecord,
    HealthSummary,
    QueryResult,
    TraceRecord,
)

logger = logging.getLogger(__name__)


async def execute_kql(
    client: LogsQueryClient,
    workspace_id: str,
    query: str,
    timespan: timedelta = timedelta(hours=24),
) -> QueryResult:
    """Execute a KQL query against a Log Analytics workspace.

    Detects partial results (server timeout or row-limit hit) and flags
    them in the returned QueryResult.
    """
    response = await client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=timespan,
        server_timeout=60,
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
