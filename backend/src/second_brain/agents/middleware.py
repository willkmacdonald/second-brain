"""Agent middleware for Foundry Agent Service -- production observability layer.

Produces OTel spans for agent runs and tool calls with classification-specific
attributes (bucket, confidence, status, item_id). Token usage is automatically
tracked by the agent-framework SDK's enable_instrumentation() call in main.py.

Spans are exported to Application Insights via the Azure Monitor exporter
configured at startup, enabling structured queries across classifications.
"""

import logging
import time
from collections.abc import Awaitable, Callable

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
)
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("second_brain.agents")


class AuditAgentMiddleware(AgentMiddleware):
    """Produces an OTel span for each classifier agent run.

    Tracks agent name and duration as span attributes for Application Insights
    tracing. Debug-level logs retained as secondary output channel.
    """

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Create OTel span around agent run lifecycle."""
        with tracer.start_as_current_span("classifier_agent_run") as span:
            span.set_attribute("agent.name", "Classifier")
            start = time.monotonic()
            logger.debug("[Agent] Run started")

            await call_next()

            elapsed_ms = (time.monotonic() - start) * 1000
            span.set_attribute("agent.duration_ms", elapsed_ms)
            logger.debug("[Agent] Run completed in %.1fms", elapsed_ms)


class ToolTimingMiddleware(FunctionMiddleware):
    """Produces an OTel span per tool call with timing and classification attrs.

    When the tool is file_capture, extracts classification metadata (bucket,
    confidence, status, item_id) from the result and sets them as span attributes
    for structured querying in Application Insights.
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Create OTel span around tool call with classification attributes."""
        func_name = context.function.name

        with tracer.start_as_current_span(f"tool_{func_name}") as span:
            span.set_attribute("tool.name", func_name)
            start = time.monotonic()

            await call_next()

            elapsed_ms = (time.monotonic() - start) * 1000
            span.set_attribute("tool.duration_ms", elapsed_ms)
            logger.debug("[Tool] %s completed in %.1fms", func_name, elapsed_ms)

            # Extract classification-specific attributes from file_capture result
            if func_name == "file_capture" and context.result is not None:
                raw_result = context.result
                if hasattr(raw_result, "value"):
                    raw_result = raw_result.value
                if isinstance(raw_result, dict):
                    span.set_attribute(
                        "classification.bucket", raw_result.get("bucket", "")
                    )
                    span.set_attribute(
                        "classification.confidence",
                        raw_result.get("confidence", 0.0),
                    )
                    span.set_attribute(
                        "classification.status", raw_result.get("status", "")
                    )
                    span.set_attribute(
                        "classification.item_id", raw_result.get("item_id", "")
                    )

            # Track transcription success
            if func_name == "transcribe_audio" and context.result is not None:
                span.set_attribute("transcription.success", True)
