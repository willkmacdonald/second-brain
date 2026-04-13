"""MCP server exposing App Insights telemetry tools for Claude Code.

Wraps the existing second_brain.observability query functions as MCP tools,
accessible via stdio transport. Uses DefaultAzureCredential (local az login)
for authentication -- no API keys needed.

IMPORTANT: All logging goes to stderr. Stdout is reserved for JSON-RPC
messages (stdio transport protocol).
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta

from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from second_brain.observability.queries import (
    execute_kql,
    query_admin_audit,
    query_capture_trace,
    query_enhanced_system_health,
    query_latest_capture_trace_id,
    query_recent_failures_filtered,
    query_usage_patterns,
)

# ---------------------------------------------------------------------------
# Logging -- CRITICAL: all output to stderr, never stdout
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("second-brain-mcp")


# ---------------------------------------------------------------------------
# Constants (mirror backend/src/second_brain/tools/investigation.py)
# ---------------------------------------------------------------------------

TIME_RANGE_MAP: dict[str, tuple[str, timedelta]] = {
    "1h": ("1h", timedelta(hours=1)),
    "6h": ("6h", timedelta(hours=6)),
    "24h": ("24h", timedelta(hours=24)),
    "3d": ("3d", timedelta(days=3)),
    "7d": ("7d", timedelta(days=7)),
}

RESULT_LIMIT = 20  # Higher than agent's 10 -- Claude Code has more screen space

ALLOWED_GROUP_BY = frozenset({"day", "hour", "bucket", "destination"})


# ---------------------------------------------------------------------------
# Lifespan -- Azure credential and LogsQueryClient lifecycle
# ---------------------------------------------------------------------------


@dataclass
class AppContext:
    """Shared state initialized at server startup."""

    logs_client: LogsQueryClient
    workspace_id: str
    credential: DefaultAzureCredential


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize Azure clients at startup, tear down on shutdown."""
    workspace_id = os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
    if not workspace_id:
        logger.warning(
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID not set -- tools will return errors"
        )

    credential = DefaultAzureCredential()
    logs_client = LogsQueryClient(credential=credential)
    logger.info(
        "MCP server started (workspace_id=%s)",
        workspace_id[:8] + "..." if workspace_id else "UNSET",
    )
    try:
        yield AppContext(
            logs_client=logs_client,
            workspace_id=workspace_id,
            credential=credential,
        )
    finally:
        await logs_client.close()
        await credential.close()
        logger.info("MCP server shutdown -- clients closed")


# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------

mcp = FastMCP("second-brain-telemetry", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_app(ctx: Context[ServerSession, AppContext]) -> AppContext:
    """Extract the AppContext from the MCP Context."""
    return ctx.request_context.lifespan_context


def _check_config(app: AppContext) -> dict | None:
    """Return error dict if workspace_id is missing, else None."""
    if not app.workspace_id:
        return {
            "error": True,
            "message": "AZURE_LOG_ANALYTICS_WORKSPACE_ID not configured",
            "type": "config_error",
        }
    return None


# ---------------------------------------------------------------------------
# Tool 1: trace_lifecycle
# ---------------------------------------------------------------------------


@mcp.tool()
async def trace_lifecycle(
    trace_id: str | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Trace a specific capture through its full lifecycle.

    Returns the ordered sequence of log entries showing classification,
    filing, and admin processing. Pass null to look up the most recent
    capture.

    Args:
        trace_id: Capture trace ID (UUID). Pass null to trace the most
            recent capture.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        # If no trace_id, look up the most recent capture
        if not trace_id:
            trace_id = await query_latest_capture_trace_id(
                app.logs_client, app.workspace_id
            )
            if not trace_id:
                return {
                    "error": True,
                    "message": "No recent captures found in the last 24 hours",
                    "type": "no_data",
                }

        records = await query_capture_trace(app.logs_client, app.workspace_id, trace_id)

        if not records:
            return {
                "error": True,
                "message": f"No trace data found for trace ID {trace_id}",
                "type": "no_data",
            }

        # Truncation: keep LAST N records (terminal event is at the end)
        total_events = len(records)
        truncated = total_events > RESULT_LIMIT
        if truncated:
            records_slice = records[-RESULT_LIMIT:]
        else:
            records_slice = records

        return {
            "events": [r.model_dump() for r in records_slice],
            "total_events": total_events,
            "truncated": truncated,
            "note": (
                f"Kept last {RESULT_LIMIT} events to preserve terminal outcome"
                if truncated
                else None
            ),
        }

    except Exception as exc:
        logger.error("trace_lifecycle failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Tool 2: recent_errors
# ---------------------------------------------------------------------------


@mcp.tool()
async def recent_errors(
    time_range: str = "24h",
    component: str | None = None,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Query recent errors and failures from App Insights.

    Returns Error-level and Critical-level log entries with optional
    component filtering.

    Args:
        time_range: Time range to query: '1h', '6h', '24h', '3d', or '7d'.
        component: Filter by component name (e.g., 'classifier',
            'admin_agent'). Pass null for all components.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        _kql_duration, td = TIME_RANGE_MAP.get(time_range, TIME_RANGE_MAP["24h"])

        result = await query_recent_failures_filtered(
            app.logs_client,
            app.workspace_id,
            component=component,
            severity="error",
            limit=RESULT_LIMIT,
            timespan=td,
        )

        return {
            "total_count": result.total_count,
            "returned_count": result.returned_count,
            "truncated": result.truncated,
            "time_range": time_range,
            "component_filter": component,
            "errors": [r.model_dump() for r in result.records],
        }

    except Exception as exc:
        logger.error("recent_errors failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Tool 3: system_health
# ---------------------------------------------------------------------------


@mcp.tool()
async def system_health(
    time_range: str = "24h",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Check system health metrics including capture counts, success rate,
    latency percentiles (P95/P99), and trend comparison against the
    previous period.

    Args:
        time_range: Time range to query: '1h', '6h', '24h', '3d', or '7d'.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        kql_duration, td = TIME_RANGE_MAP.get(time_range, TIME_RANGE_MAP["24h"])

        summary = await query_enhanced_system_health(
            app.logs_client,
            app.workspace_id,
            time_range_kql=kql_duration,
            timespan=td * 2,
        )

        return summary.model_dump()

    except Exception as exc:
        logger.error("system_health failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Tool 4: usage_patterns
# ---------------------------------------------------------------------------


@mcp.tool()
async def usage_patterns(
    time_range: str = "7d",
    group_by: str = "day",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Analyze capture usage patterns grouped by time period, bucket,
    or destination.

    Args:
        time_range: Time range to query: '1h', '6h', '24h', '3d', or '7d'.
        group_by: Grouping dimension: 'day', 'hour', 'bucket', or
            'destination'.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        kql_duration, td = TIME_RANGE_MAP.get(time_range, TIME_RANGE_MAP["7d"])

        if group_by not in ALLOWED_GROUP_BY:
            logger.warning("Invalid group_by '%s', defaulting to 'day'", group_by)
            group_by = "day"

        records = await query_usage_patterns(
            app.logs_client,
            app.workspace_id,
            group_by=group_by,
            time_range_kql=kql_duration,
            timespan=td,
        )

        total_patterns = len(records)
        truncated = total_patterns > RESULT_LIMIT

        return {
            "time_range": time_range,
            "group_by": group_by,
            "patterns": [r.model_dump() for r in records[:RESULT_LIMIT]],
            "total_patterns": total_patterns,
            "truncated": truncated,
        }

    except Exception as exc:
        logger.error("usage_patterns failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Tool 5: admin_audit
# ---------------------------------------------------------------------------


@mcp.tool()
async def admin_audit(
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Query Admin Agent activity logs from the last 24 hours.

    Shows processing events, successes, and failures.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        records = await query_admin_audit(app.logs_client, app.workspace_id)

        total_events = len(records)
        truncated = total_events > RESULT_LIMIT

        return {
            "events": [r.model_dump() for r in records[:RESULT_LIMIT]],
            "total_events": total_events,
            "truncated": truncated,
        }

    except Exception as exc:
        logger.error("admin_audit failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Tool 6: run_kql
# ---------------------------------------------------------------------------


@mcp.tool()
async def run_kql(
    query: str,
    time_range: str = "24h",
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Execute a raw KQL query against the App Insights Log Analytics workspace.

    Use for ad-hoc queries not covered by the other tools.
    Log Analytics is read-only -- no risk of data modification.

    Args:
        query: KQL query string to execute.
        time_range: Time window: '1h', '6h', '24h', '3d', or '7d'.
    """
    app = _get_app(ctx)
    if err := _check_config(app):
        return err
    try:
        _, td = TIME_RANGE_MAP.get(time_range, TIME_RANGE_MAP["24h"])

        result = await execute_kql(
            app.logs_client, app.workspace_id, query, timespan=td
        )

        return {
            "tables": result.tables,
            "is_partial": result.is_partial,
            "partial_error": result.partial_error,
        }

    except Exception as exc:
        logger.error("run_kql failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
