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
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Load backend/.env so LOG_ANALYTICS_WORKSPACE_ID (and any future shared vars)
# come from the same place the backend reads them. Runs at import time, before
# Azure clients are constructed.
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

from azure.identity.aio import DefaultAzureCredential  # noqa: E402
from azure.monitor.query.aio import LogsQueryClient  # noqa: E402
from mcp.server.fastmcp import Context, FastMCP  # noqa: E402
from mcp.server.session import ServerSession  # noqa: E402

from second_brain.observability.queries import (  # noqa: E402
    execute_kql,
    query_enhanced_system_health,
    query_latest_capture_trace_id,
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
# Spine client
# ---------------------------------------------------------------------------

SPINE_BASE_URL = os.environ.get("SPINE_BASE_URL", "https://brain.willmacdonald.com")
SPINE_API_KEY = os.environ.get("SPINE_API_KEY", "")


async def _spine_call(
    path: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Call the spine API and return the JSON response.

    Raises httpx.HTTPStatusError on non-2xx responses so callers can catch
    and surface a structured error dict.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SPINE_BASE_URL}{path}",
            params=params,
            headers={"Authorization": f"Bearer {SPINE_API_KEY}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


async def _spine_post(path: str, json_body: dict[str, Any]) -> dict[str, Any]:
    """POST to the spine API and return the JSON response."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SPINE_BASE_URL}{path}",
            json=json_body,
            headers={"Authorization": f"Bearer {SPINE_API_KEY}"},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]


def _time_range_to_seconds(time_range: str) -> int:
    """Convert a TIME_RANGE_MAP key to an integer number of seconds.

    Falls back to 3600 (1h) for unknown keys so callers never pass 0 to the
    spine API (a falsy guard that was a known footgun in Phase 1 web work).
    """
    entry = TIME_RANGE_MAP.get(time_range)
    if entry is None:
        return 3600
    _, td = entry
    return max(1, int(td.total_seconds()))


# ---------------------------------------------------------------------------
# Spine response transformers
# ---------------------------------------------------------------------------


def _transform_recent_errors_from_spine(
    spine_data: dict[str, Any],
    time_range: str,
    component: str | None,
) -> dict[str, Any]:
    """Project a spine backend_api segment detail into the recent_errors shape.

    The spine response has:
      data.app_exceptions: list of raw App Insights exception dicts

    We project this into the same envelope that the legacy path returns so
    callers see a consistent shape regardless of which path was used.
    """
    data = spine_data.get("data", {})
    exceptions: list[dict[str, Any]] = data.get("app_exceptions", [])

    # Apply optional component filter (spine returns all; legacy filtered at query time)
    if component:
        exceptions = [
            e
            for e in exceptions
            if component.lower() in str(e.get("component", "")).lower()
            or component.lower()
            in str(e.get("properties", {}).get("component", "")).lower()
        ]

    truncated = len(exceptions) > RESULT_LIMIT
    errors_slice = exceptions[:RESULT_LIMIT]

    return {
        "total_count": len(exceptions),
        "returned_count": len(errors_slice),
        "truncated": truncated,
        "time_range": time_range,
        "component_filter": component,
        "errors": errors_slice,
    }


def _transform_trace_lifecycle_from_spine(
    spine_data: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    """Project a spine correlation response into the trace_lifecycle shape.

    The spine /correlation/capture/{id} endpoint returns a list of CorrelationEvent
    records (one per segment that saw the trace). The legacy path returns raw App
    Insights log entries ordered by time.
    """
    events_raw: list[dict[str, Any]] = spine_data.get("events", [])

    # Map spine CorrelationEvent fields → legacy TraceEvent-compatible dict
    events = [
        {
            "timestamp": e.get("timestamp"),
            "segment_id": e.get("segment_id"),
            "status": e.get("status"),
            "message": e.get("headline", ""),
            # Legacy fields that spine doesn't provide -- filled with sentinels
            "severity": None,
            "component": e.get("segment_id"),
            "trace_id": trace_id,
        }
        for e in events_raw
    ]

    total_events = len(events)
    truncated = total_events > RESULT_LIMIT
    events_slice = events[-RESULT_LIMIT:] if truncated else events

    return {
        "events": events_slice,
        "total_events": total_events,
        "truncated": truncated,
        "note": (
            f"Kept last {RESULT_LIMIT} events to preserve terminal outcome"
            if truncated
            else None
        ),
    }


def _transform_admin_audit_from_spine(
    spine_data: dict[str, Any],
) -> dict[str, Any]:
    """Project a spine admin segment detail into the admin_audit shape.

    The admin segment uses FoundryAgentAdapter which returns:
      data.agent_runs: list of agent run span dicts

    Legacy admin_audit returns AuditRecord model dicts with timestamp, operation,
    outcome, duration_ms, etc. We project the available span fields into that shape.
    """
    data = spine_data.get("data", {})
    agent_runs: list[dict[str, Any]] = data.get("agent_runs", [])

    events = [
        {
            "timestamp": run.get("timestamp"),
            "operation": run.get("operation", run.get("name", "unknown")),
            "outcome": run.get("outcome", run.get("status", "unknown")),
            "duration_ms": run.get("duration_ms", run.get("durationMs")),
            "agent_id": run.get("agent_id"),
            "thread_id": run.get("thread_id"),
            "run_id": run.get("run_id"),
        }
        for run in agent_runs
    ]

    total_events = len(events)
    truncated = total_events > RESULT_LIMIT

    return {
        "events": events[:RESULT_LIMIT],
        "total_events": total_events,
        "truncated": truncated,
    }


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
    workspace_id = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "")
    if not workspace_id:
        logger.warning(
            "LOG_ANALYTICS_WORKSPACE_ID not set in backend/.env -- tools will return errors"
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
            "message": "LOG_ANALYTICS_WORKSPACE_ID not set in backend/.env",
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

    Returns the ordered sequence of spine CorrelationEvents showing
    classification, filing, and admin processing. Pass null to look up
    the most recent capture.

    Args:
        trace_id: Capture trace ID (UUID). Pass null to trace the most
            recent capture.
    """
    try:
        # Spine correlation requires a concrete trace_id. The "most recent"
        # lookup still reads App Insights because spine has no "give me the
        # latest capture" endpoint.
        if not trace_id:
            app = _get_app(ctx)
            if err := _check_config(app):
                return err
            trace_id = await query_latest_capture_trace_id(
                app.logs_client, app.workspace_id
            )
            if not trace_id:
                return {
                    "error": True,
                    "message": "No recent captures found in the last 24 hours",
                    "type": "no_data",
                }

        spine_data = await _spine_call(f"/api/spine/correlation/capture/{trace_id}")
        return _transform_trace_lifecycle_from_spine(spine_data, trace_id)

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
    """Query recent errors and failures from the backend_api spine segment.

    Returns the exceptions surfaced by the backend_api segment within the
    requested window, with optional component filtering.

    Args:
        time_range: Time range to query: '1h', '6h', '24h', '3d', or '7d'.
        component: Filter by component name (e.g., 'classifier',
            'admin_agent'). Pass null for all components.
    """
    try:
        seconds = _time_range_to_seconds(time_range)
        spine_data = await _spine_call(
            "/api/spine/segment/backend_api",
            params={"time_range_seconds": seconds},
        )
        return _transform_recent_errors_from_spine(spine_data, time_range, component)
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

    This tool is permanently served from the legacy App Insights path.
    The spine /status endpoint tracks segment traffic lights, not ops
    metrics, so there is no spine equivalent to cut over to.

    Args:
        time_range: Time range to query: '1h', '6h', '24h', '3d', or '7d'.
    """
    return await _legacy_system_health(time_range, ctx)


async def _legacy_system_health(
    time_range: str,
    ctx: Context[ServerSession, AppContext],
) -> dict:
    """Original App Insights implementation of system_health."""
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
# NOTE: Legacy-only. Spine does not expose usage groupings (by day/hour/bucket/
# destination). This tool will remain on the App Insights direct-query path
# permanently unless the spine gains a dedicated usage aggregation endpoint.
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
    """Query Admin Agent activity from the admin spine segment.

    Shows processing events, successes, and failures.
    """
    try:
        spine_data = await _spine_call("/api/spine/segment/admin")
        return _transform_admin_audit_from_spine(spine_data)
    except Exception as exc:
        logger.error("admin_audit failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Tool 6: run_kql
# NOTE: Legacy-only permanently. Raw KQL has no spine equivalent -- the spine
# system is a structured overlay on top of App Insights, not a query proxy.
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
# Tool 7: audit_correlation
# ---------------------------------------------------------------------------


@mcp.tool()
async def audit_correlation(
    correlation_kind: str,
    correlation_id: str | None = None,
    sample_size: int = 5,
    time_range_seconds: int = 86400,
    ctx: Context[ServerSession, AppContext] = None,
) -> dict:
    """Audit whether spine events for a correlation_id (or a sample of recent
    ones) line up with what native sources actually saw.

    Use when the user asks whether observability is working, whether a specific
    trace was captured correctly, or whether segments are accurately reflecting
    their domain. Returns per-trace verdicts plus an aggregate roll-up.

    Args:
        correlation_kind: One of 'capture', 'thread', 'request', 'crud'.
        correlation_id: Audit a specific ID. If null, samples the N most-recent
            correlation_ids of this kind from the last `time_range_seconds`.
        sample_size: Number of traces to sample when correlation_id is null
            (1-20). Ignored otherwise.
        time_range_seconds: Window for sampling and native-source lookups
            (60 to 604800 = 1 minute to 7 days).
    """
    try:
        body: dict[str, Any] = {
            "correlation_kind": correlation_kind,
            "sample_size": sample_size,
            "time_range_seconds": time_range_seconds,
        }
        if correlation_id:
            body["correlation_id"] = correlation_id
        return await _spine_post("/api/spine/audit/correlation", body)
    except Exception as exc:
        logger.error("audit_correlation failed: %s", exc, exc_info=True)
        return {"error": True, "message": str(exc), "type": type(exc).__name__}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
