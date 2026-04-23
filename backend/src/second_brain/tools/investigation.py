"""Investigation agent tools for App Insights observability queries.

Uses the class-based tool pattern to bind LogsQueryClient references to @tool
functions. InvestigationTools provides 9 tools: trace_lifecycle, recent_errors,
system_health, usage_patterns, query_feedback_signals,
promote_to_golden_dataset, run_classifier_eval, run_admin_eval,
and get_eval_results.

Each tool returns JSON strings for the Investigation Agent to format into
human-readable answers. Tools never raise -- they catch exceptions and return
JSON error messages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

from agent_framework import tool
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.monitor.query.aio import LogsQueryClient
from pydantic import Field

from second_brain.api.eval import _eval_runs
from second_brain.eval.runner import run_admin_eval as _run_admin_eval
from second_brain.eval.runner import run_classifier_eval as _run_classifier_eval
from second_brain.models.documents import GoldenDatasetDocument
from second_brain.observability.queries import (
    query_capture_trace,
    query_enhanced_system_health,
    query_latest_capture_trace_id,
    query_recent_failures_filtered,
    query_usage_patterns,
)

if TYPE_CHECKING:
    from agent_framework.azure import AzureAIAgentClient

    from second_brain.db.cosmos import CosmosManager

logger = logging.getLogger(__name__)

# User-friendly time range strings -> (KQL duration literal, timedelta)
TIME_RANGE_MAP: dict[str, tuple[str, timedelta]] = {
    "1h": ("1h", timedelta(hours=1)),
    "6h": ("6h", timedelta(hours=6)),
    "24h": ("24h", timedelta(hours=24)),
    "3d": ("3d", timedelta(days=3)),
    "7d": ("7d", timedelta(days=7)),
}

# Feedback time range strings -> timedelta days
_FEEDBACK_TIME_MAP: dict[str, int] = {
    "24h": 1,
    "3d": 3,
    "7d": 7,
    "30d": 30,
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
        cosmos_manager: CosmosManager | None = None,
        classifier_client: AzureAIAgentClient | None = None,
        admin_client: AzureAIAgentClient | None = None,
    ) -> None:
        self._logs_client = logs_client
        self._workspace_id = workspace_id
        self._cosmos_manager = cosmos_manager
        self._classifier_client = classifier_client
        self._admin_client = admin_client

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

    # ------------------------------------------------------------------
    # Tool 5: query_feedback_signals
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def query_feedback_signals(
        self,
        signal_type: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by signal type: 'recategorize', "
                    "'hitl_bucket', 'errand_reroute', "
                    "'thumbs_up', 'thumbs_down'. "
                    "Pass null for all types."
                )
            ),
        ] = None,
        time_range: Annotated[
            str,
            Field(
                description=("Time range: '24h', '3d', '7d', '30d'. Defaults to '7d'.")
            ),
        ] = "7d",
        limit: Annotated[
            int,
            Field(description=("Maximum number of signals to return. Defaults to 20.")),
        ] = 20,
    ) -> str:
        """Query quality feedback signals from the Feedback database.

        Returns recent signals showing classification corrections,
        HITL resolutions, and explicit user ratings. Includes a
        misclassification summary with bucket transition counts
        when recategorize signals are present.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "query_feedback_signals called: signal_type=%s time_range=%s limit=%d",
            signal_type,
            time_range,
            limit,
            extra=log_extra,
        )

        try:
            if self._cosmos_manager is None:
                return json.dumps(
                    {"error": ("Feedback data unavailable (Cosmos not configured)")}
                )

            # Calculate cutoff
            days = _FEEDBACK_TIME_MAP.get(time_range, 7)
            cutoff = datetime.now(UTC) - timedelta(days=days)
            cutoff_str = cutoff.isoformat()

            # Build parameterized query
            query = (
                "SELECT * FROM c WHERE c.userId = @userId AND c.createdAt >= @cutoff"
            )
            parameters: list[dict[str, str]] = [
                {"name": "@userId", "value": "will"},
                {"name": "@cutoff", "value": cutoff_str},
            ]

            if signal_type is not None:
                query += " AND c.signalType = @signalType"
                parameters.append({"name": "@signalType", "value": signal_type})

            query += " ORDER BY c.createdAt DESC"

            container = self._cosmos_manager.get_container("Feedback")
            items_iter = container.query_items(
                query=query,
                parameters=parameters,
                partition_key="will",
            )

            # Collect up to limit results
            signals: list[dict] = []
            async for item in items_iter:
                signals.append(item)
                if len(signals) >= limit:
                    break

            # Build misclassification summary from recategorize
            transitions: Counter[str] = Counter()
            for sig in signals:
                if sig.get("signalType") == "recategorize" and sig.get(
                    "correctedBucket"
                ):
                    key = f"{sig['originalBucket']} -> {sig['correctedBucket']}"
                    transitions[key] += 1

            return json.dumps(
                {
                    "signals": signals,
                    "total": len(signals),
                    "misclassification_summary": dict(transitions),
                    "time_range": time_range,
                },
                default=str,
            )

        except Exception as exc:
            logger.error(
                "query_feedback_signals error: %s",
                exc,
                exc_info=True,
                extra=log_extra,
            )
            return json.dumps({"error": f"Failed to query feedback signals: {exc}"})

    # ------------------------------------------------------------------
    # Tool 6: promote_to_golden_dataset
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def promote_to_golden_dataset(
        self,
        signal_id: Annotated[
            str,
            Field(description=("The ID of the feedback signal to promote.")),
        ],
        confirm: Annotated[
            bool,
            Field(
                description=(
                    "Set to true to confirm promotion after "
                    "reviewing the preview. First call with "
                    "false to see the preview."
                )
            ),
        ] = False,
    ) -> str:
        """Promote a feedback signal to the golden evaluation dataset.

        Two-step flow: first call with confirm=false to preview,
        then call with confirm=true after user approves. Returns
        the signal details for review or the new golden dataset
        entry ID on confirmation.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "promote_to_golden_dataset called: signal_id=%s confirm=%s",
            signal_id,
            confirm,
            extra=log_extra,
        )

        try:
            if self._cosmos_manager is None:
                return json.dumps(
                    {"error": ("Golden dataset unavailable (Cosmos not configured)")}
                )

            feedback_container = self._cosmos_manager.get_container("Feedback")

            # Read the signal
            signal = await feedback_container.read_item(
                item=signal_id,
                partition_key="will",
            )

            if not confirm:
                # Preview mode -- show what would be promoted
                expected = signal.get("correctedBucket") or signal.get("originalBucket")
                return json.dumps(
                    {
                        "preview": True,
                        "signal_id": signal_id,
                        "captureText": signal.get("captureText"),
                        "originalBucket": signal.get("originalBucket"),
                        "correctedBucket": signal.get("correctedBucket"),
                        "expectedBucket": expected,
                        "signalType": signal.get("signalType"),
                        "message": (
                            "Promote this as a test case with "
                            f"expected bucket '{expected}'?"
                        ),
                    },
                    default=str,
                )

            # Confirm mode -- write to GoldenDataset
            expected_bucket = signal.get("correctedBucket") or signal.get(
                "originalBucket"
            )
            golden_doc = GoldenDatasetDocument(
                inputText=signal["captureText"],
                expectedBucket=expected_bucket,
                source="promoted_feedback",
                tags=["from_feedback", signal.get("signalType", "")],
            )

            golden_container = self._cosmos_manager.get_container("GoldenDataset")
            await golden_container.create_item(
                body=golden_doc.model_dump(mode="json"),
            )

            return json.dumps(
                {
                    "success": True,
                    "id": golden_doc.id,
                    "inputText": golden_doc.inputText,
                    "expectedBucket": golden_doc.expectedBucket,
                    "source": golden_doc.source,
                },
                default=str,
            )

        except CosmosResourceNotFoundError:
            return json.dumps({"error": f"Signal not found: {signal_id}"})
        except Exception as exc:
            logger.error(
                "promote_to_golden_dataset error: %s",
                exc,
                exc_info=True,
                extra=log_extra,
            )
            return json.dumps({"error": (f"Failed to promote signal: {exc}")})

    # ------------------------------------------------------------------
    # Tool 7: run_classifier_eval
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def run_classifier_eval(self) -> str:
        """Trigger a classifier evaluation run against the golden dataset.

        Starts a background eval run that sends each golden dataset
        entry through the Classifier agent and measures accuracy.
        Returns the run ID for status checking. The eval takes 3-5
        minutes for 50 cases. Check status with get_eval_results.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info("run_classifier_eval called", extra=log_extra)

        try:
            if self._classifier_client is None:
                return json.dumps({"error": "Classifier client not available"})
            if self._cosmos_manager is None:
                return json.dumps({"error": "Cosmos not configured"})

            # Single in-flight check
            for rid, run in _eval_runs.items():
                if (
                    run.get("eval_type") == "classifier"
                    and run.get("status") == "running"
                ):
                    return json.dumps(
                        {
                            "status": "already_running",
                            "run_id": rid,
                            "progress": run.get("progress", "unknown"),
                        }
                    )

            run_id = str(uuid4())
            _eval_runs[run_id] = {
                "status": "running",
                "eval_type": "classifier",
                "started_at": datetime.now(UTC).isoformat(),
            }
            asyncio.create_task(
                _run_classifier_eval(
                    run_id=run_id,
                    cosmos_manager=self._cosmos_manager,
                    classifier_client=self._classifier_client,
                    runs_dict=_eval_runs,
                )
            )
            return json.dumps(
                {
                    "status": "started",
                    "run_id": run_id,
                    "message": (
                        "Classifier eval started. Use get_eval_results "
                        "to check progress and see results when complete."
                    ),
                }
            )
        except Exception as exc:
            logger.error(
                "run_classifier_eval error: %s",
                exc,
                exc_info=True,
                extra=log_extra,
            )
            return json.dumps({"error": f"Failed to start classifier eval: {exc}"})

    # ------------------------------------------------------------------
    # Tool 8: run_admin_eval
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def run_admin_eval(
        self,
        routing_context: Annotated[
            str,
            Field(
                description=(
                    "Fixed routing context (destinations and affinity "
                    "rules) for deterministic eval. Required per D-13."
                )
            ),
        ],
    ) -> str:
        """Trigger an admin agent evaluation run against the golden dataset.

        Starts a background eval run that sends each golden dataset
        entry through the Admin agent with dry-run tools and measures
        routing accuracy. Returns the run ID for status checking.
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info("run_admin_eval called", extra=log_extra)

        try:
            if self._admin_client is None:
                return json.dumps({"error": "Admin client not available"})
            if self._cosmos_manager is None:
                return json.dumps({"error": "Cosmos not configured"})

            # Single in-flight check
            for rid, run in _eval_runs.items():
                if (
                    run.get("eval_type") == "admin_agent"
                    and run.get("status") == "running"
                ):
                    return json.dumps(
                        {
                            "status": "already_running",
                            "run_id": rid,
                            "progress": run.get("progress", "unknown"),
                        }
                    )

            run_id = str(uuid4())
            _eval_runs[run_id] = {
                "status": "running",
                "eval_type": "admin_agent",
                "started_at": datetime.now(UTC).isoformat(),
            }
            asyncio.create_task(
                _run_admin_eval(
                    run_id=run_id,
                    cosmos_manager=self._cosmos_manager,
                    admin_client=self._admin_client,
                    routing_context=routing_context,
                    runs_dict=_eval_runs,
                )
            )
            return json.dumps(
                {
                    "status": "started",
                    "run_id": run_id,
                    "message": (
                        "Admin eval started. Use get_eval_results "
                        "to check progress and see results when complete."
                    ),
                }
            )
        except Exception as exc:
            logger.error(
                "run_admin_eval error: %s",
                exc,
                exc_info=True,
                extra=log_extra,
            )
            return json.dumps({"error": f"Failed to start admin eval: {exc}"})

    # ------------------------------------------------------------------
    # Tool 9: get_eval_results
    # ------------------------------------------------------------------

    @tool(approval_mode="never_require")
    async def get_eval_results(
        self,
        eval_type: Annotated[
            str | None,
            Field(
                description=(
                    "Filter by eval type: 'classifier' or "
                    "'admin_agent'. Pass null for all types."
                )
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description=("Maximum number of results to return. Default 3.")),
        ] = 3,
    ) -> str:
        """Get recent eval results and any in-progress run status.

        Queries the EvalResults Cosmos container for completed eval
        results, and checks for any currently running evals. Returns
        accuracy tables and per-bucket breakdowns for the investigation
        agent to format as markdown (D-07).
        """
        log_extra: dict = {"component": "investigation_agent"}
        logger.info(
            "get_eval_results called: eval_type=%s limit=%d",
            eval_type,
            limit,
            extra=log_extra,
        )

        try:
            # Check for in-progress runs
            in_progress: list[dict] = []
            for rid, run in _eval_runs.items():
                if run.get("status") == "running" and (
                    eval_type is None or run.get("eval_type") == eval_type
                ):
                    in_progress.append(
                        {
                            "run_id": rid,
                            "eval_type": run.get("eval_type"),
                            "progress": run.get("progress", "unknown"),
                            "started_at": run.get("started_at"),
                        }
                    )

            # Query stored results from Cosmos
            stored_results: list[dict] = []
            if self._cosmos_manager is not None:
                try:
                    container = self._cosmos_manager.get_container("EvalResults")

                    query = "SELECT * FROM c WHERE c.userId = @userId"
                    parameters: list[dict[str, str]] = [
                        {"name": "@userId", "value": "will"},
                    ]

                    if eval_type is not None:
                        query += " AND c.evalType = @evalType"
                        parameters.append({"name": "@evalType", "value": eval_type})

                    query += " ORDER BY c.runTimestamp DESC"

                    async for item in container.query_items(
                        query=query,
                        parameters=parameters,
                    ):
                        stored_results.append(
                            {
                                "id": item["id"],
                                "evalType": item.get("evalType"),
                                "runTimestamp": item.get("runTimestamp"),
                                "datasetSize": item.get("datasetSize"),
                                "aggregateScores": item.get("aggregateScores"),
                                "modelDeployment": item.get("modelDeployment"),
                            }
                        )
                        if len(stored_results) >= limit:
                            break
                except Exception as cosmos_exc:
                    logger.warning(
                        "Failed to query eval results from Cosmos: %s",
                        cosmos_exc,
                        extra=log_extra,
                    )

            return json.dumps(
                {
                    "in_progress": in_progress,
                    "results": stored_results,
                    "count": len(stored_results),
                },
                default=str,
            )

        except Exception as exc:
            logger.error(
                "get_eval_results error: %s",
                exc,
                exc_info=True,
                extra=log_extra,
            )
            return json.dumps({"error": f"Failed to get eval results: {exc}"})
