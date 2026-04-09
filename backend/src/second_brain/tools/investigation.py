"""Investigation agent tools for App Insights observability queries.

Uses the class-based tool pattern to bind LogsQueryClient references to @tool
functions. InvestigationTools provides 4 tools: trace_lifecycle, recent_errors,
system_health, and usage_patterns.

Each tool returns JSON strings for the Investigation Agent to format into
human-readable answers. Tools never raise -- they catch exceptions and return
JSON error messages.
"""

import json
import logging
from datetime import timedelta
from typing import Annotated

from agent_framework import tool
from azure.monitor.query.aio import LogsQueryClient
from pydantic import Field

from second_brain.observability.queries import (
    query_capture_trace,
    query_enhanced_system_health,
    query_latest_capture_trace_id,
    query_recent_failures_filtered,
    query_usage_patterns,
)

logger = logging.getLogger(__name__)

# User-friendly time range strings -> (KQL duration literal, timedelta)
TIME_RANGE_MAP: dict[str, tuple[str, timedelta]] = {
    "1h": ("1h", timedelta(hours=1)),
    "6h": ("6h", timedelta(hours=6)),
    "24h": ("24h", timedelta(hours=24)),
    "3d": ("3d", timedelta(days=3)),
    "7d": ("7d", timedelta(days=7)),
}

# Allowed group_by values for usage_patterns
_ALLOWED_GROUP_BY = frozenset({"day", "hour", "bucket", "destination"})

# Maximum rows returned by recent_errors. Mirrored in the Foundry portal
# instructions; keep both in sync.
_RESULT_LIMIT = 10


def _validate_time_range(time_range: str, default: str = "24h") -> str:
    """Return validated time_range key, falling back to default if invalid."""
    if time_range in TIME_RANGE_MAP:
        return time_range
    logger.warning(
        "Invalid time_range '%s', defaulting to '%s'",
        time_range,
        default,
        extra={"component": "investigation_agent"},
    )
    return default


class InvestigationTools:
    """Investigation tools bound to LogsQueryClient for App Insights queries.

    Each @tool function wraps a query from the observability module with
    parameterized time windows and returns structured JSON data for the
    assistant to format into human-readable answers.
    """

    def __init__(
        self,
        logs_client: LogsQueryClient,
        workspace_id: str,
    ) -> None:
        self._logs_client = logs_client
        self._workspace_id = workspace_id

    # ------------------------------------------------------------------
    # Tool 1: trace_lifecycle
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def trace_lifecycle(
        self,
        trace_id: Annotated[
            str | None,
            Field(
                description=(
                    "Capture trace ID (UUID) to look up. "
                    "Pass null/None to trace the most recent capture."
                )
            ),
        ] = None,
    ) -> str:
        """Trace a specific capture through its full lifecycle.

        Returns the ordered sequence of log entries for a capture trace ID,
        showing how the capture flowed through classification, filing, and
        admin processing. Pass null to look up the most recent capture.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "trace_lifecycle called: trace_id=%s",
            trace_id,
            extra=log_extra,
        )

        try:
            # If no trace_id, look up the most recent capture
            if not trace_id:
                trace_id = await query_latest_capture_trace_id(
                    self._logs_client, self._workspace_id
                )
                if not trace_id:
                    return json.dumps(
                        {"error": "No recent captures found in the last 24 hours."}
                    )

            records = await query_capture_trace(
                self._logs_client, self._workspace_id, trace_id
            )

            if not records:
                return json.dumps(
                    {
                        "error": f"No trace data found for trace ID {trace_id}.",
                        "suggestion": (
                            "Try widening the time range or check if the "
                            "trace ID is correct."
                        ),
                    }
                )

            return json.dumps(
                [r.model_dump() for r in records],
                default=str,
            )

        except Exception as exc:
            logger.error(
                "trace_lifecycle error: %s", exc, exc_info=True, extra=log_extra
            )
            return json.dumps({"error": f"Failed to query trace lifecycle: {exc}"})

    # ------------------------------------------------------------------
    # Tool 2: recent_errors
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def recent_errors(
        self,
        time_range: Annotated[
            str,
            Field(
                description=(
                    "Time range to query: '1h', '6h', '24h', '3d', or '7d'. "
                    "Defaults to '24h'."
                )
            ),
        ] = "24h",
        component: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by component name (e.g., 'classifier', "
                    "'admin_agent'). Pass null for all components."
                )
            ),
        ] = None,
    ) -> str:
        """Query recent errors and failures from App Insights.

        Returns Error- and Critical-level log entries (Azure SeverityLevel
        >= 3) with optional component filtering. Results are capped at 10
        most recent entries; the response includes total_count so the agent
        can report 'showing N of M' when truncated.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "recent_errors called: time_range=%s component=%s",
            time_range,
            component,
            extra=log_extra,
        )

        try:
            time_range = _validate_time_range(time_range, "24h")
            _kql_duration, td = TIME_RANGE_MAP[time_range]

            result = await query_recent_failures_filtered(
                self._logs_client,
                self._workspace_id,
                component=component,
                severity="error",
                limit=_RESULT_LIMIT,
                timespan=td,
            )

            return json.dumps(
                {
                    "total_count": result.total_count,
                    "returned_count": result.returned_count,
                    "truncated": result.truncated,
                    "time_range": time_range,
                    "component_filter": component,
                    "severity": "error_or_critical",
                    "errors": [r.model_dump() for r in result.records],
                },
                default=str,
            )

        except Exception as exc:
            logger.error("recent_errors error: %s", exc, exc_info=True, extra=log_extra)
            return json.dumps({"error": f"Failed to query recent errors: {exc}"})

    # ------------------------------------------------------------------
    # Tool 3: system_health
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def system_health(
        self,
        time_range: Annotated[
            str,
            Field(
                description=(
                    "Time range to query: '1h', '6h', '24h', '3d', or '7d'. "
                    "Defaults to '24h'."
                )
            ),
        ] = "24h",
    ) -> str:
        """Check system health metrics and error trends.

        Returns capture counts, success rate, latency percentiles
        (P95/P99), and trend comparison against the previous period
        of equal length.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "system_health called: time_range=%s",
            time_range,
            extra=log_extra,
        )

        try:
            time_range = _validate_time_range(time_range, "24h")
            kql_duration, td = TIME_RANGE_MAP[time_range]

            summary = await query_enhanced_system_health(
                self._logs_client,
                self._workspace_id,
                time_range_kql=kql_duration,
                timespan=td * 2,
            )

            return json.dumps(summary.model_dump(), default=str)

        except Exception as exc:
            logger.error("system_health error: %s", exc, exc_info=True, extra=log_extra)
            return json.dumps({"error": f"Failed to query system health: {exc}"})

    # ------------------------------------------------------------------
    # Tool 4: usage_patterns
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def usage_patterns(
        self,
        time_range: Annotated[
            str,
            Field(
                description=(
                    "Time range to query: '1h', '6h', '24h', '3d', or '7d'. "
                    "Defaults to '7d'."
                )
            ),
        ] = "7d",
        group_by: Annotated[
            str,
            Field(
                description=(
                    "Grouping dimension: 'day', 'hour', 'bucket', "
                    "or 'destination'. Defaults to 'day'."
                )
            ),
        ] = "day",
    ) -> str:
        """Analyze capture usage patterns.

        Groups captures by time period, bucket, or destination.
        Returns counts per group for understanding usage trends
        and distribution across categories.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "usage_patterns called: time_range=%s group_by=%s",
            time_range,
            group_by,
            extra=log_extra,
        )

        try:
            time_range = _validate_time_range(time_range, "7d")
            kql_duration, td = TIME_RANGE_MAP[time_range]

            if group_by not in _ALLOWED_GROUP_BY:
                logger.warning(
                    "Invalid group_by '%s', defaulting to 'day'",
                    group_by,
                    extra=log_extra,
                )
                group_by = "day"

            records = await query_usage_patterns(
                self._logs_client,
                self._workspace_id,
                group_by=group_by,
                time_range_kql=kql_duration,
                timespan=td,
            )

            return json.dumps(
                {
                    "time_range": time_range,
                    "group_by": group_by,
                    "patterns": [r.model_dump() for r in records],
                },
                default=str,
            )

        except Exception as exc:
            logger.error(
                "usage_patterns error: %s", exc, exc_info=True, extra=log_extra
            )
            return json.dumps({"error": f"Failed to query usage patterns: {exc}"})
