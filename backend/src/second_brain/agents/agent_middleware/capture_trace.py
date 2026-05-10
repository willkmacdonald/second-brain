"""Capture-trace middleware for the GA agent-framework.

Per design D-07a (layered tagging strategy):
- This module's middleware tags framework-emitted invoke_agent / execute_tool
  spans with capture.trace_id at source.
- observability/span_processor.py is RETAINED to tag non-framework spans
  (Azure SDK AppDependencies, Cosmos, AppExceptions).
- The old agents/middleware.py (AuditAgentMiddleware + ToolTimingMiddleware)
  is replaced by these classes and deleted in plan 24-18.

Per F-17: middleware MUST act on the framework's current span via
trace.get_current_span().set_attribute(...). It MUST NOT create parallel
spans via the OTel tracer's "start as current span" wrapper (the legacy
RC anti-pattern in agents/middleware.py).

Per P1-3: this module lives at agents/agent_middleware/ (NOT agents/middleware/)
to avoid shadowing the legacy module-style file agents/middleware.py during
the migration window. After 24-18 deletes the legacy file, plan 24-18 may
optionally rename this package to agents/middleware/ for tidiness.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable, Callable

from agent_framework import (
    AgentContext,
    AgentMiddleware,
    FunctionInvocationContext,
    FunctionMiddleware,
)
from opentelemetry import trace

from second_brain.tools.classification import capture_trace_id_var

logger = logging.getLogger(__name__)


class CaptureTraceAgentMiddleware(AgentMiddleware):
    """Tag the framework-emitted invoke_agent span with capture.trace_id.

    Reads the per-request capture_trace_id_var ContextVar populated by
    api/capture.py. Sets the span attribute on the CURRENT span -- the
    framework's invoke_agent span is the current span at this point.
    """

    async def process(
        self,
        context: AgentContext,  # noqa: ARG002 — required by AgentMiddleware ABC; reserved for future use
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        trace_id = capture_trace_id_var.get("")
        if trace_id:
            trace.get_current_span().set_attribute("capture.trace_id", trace_id)
        await call_next()


class CaptureTraceFunctionMiddleware(FunctionMiddleware):
    """Tag the framework-emitted execute_tool span with capture.trace_id
    AND lift classification/transcription result attributes onto the span.

    Lifted attribute extractors (file_capture and transcribe_audio) come
    from the soon-to-be-deleted ToolTimingMiddleware (lines 82-104 of
    agents/middleware.py). The legacy RC duration attributes that the
    deleted ToolTimingMiddleware set on every tool span are intentionally
    NOT carried over -- the framework already emits duration via gen_ai
    semantic conventions, so duplicating them would be dead weight.
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        trace_id = capture_trace_id_var.get("")
        span = trace.get_current_span()
        if trace_id:
            span.set_attribute("capture.trace_id", trace_id)

        await call_next()

        # After the tool runs, lift classification.* / transcription.* attributes
        # from the result onto the current span. Tool name lives on
        # context.function.name (GA shape).
        try:
            func_name = getattr(getattr(context, "function", None), "name", "") or ""
            result = getattr(context, "result", None)
        except Exception:
            func_name = ""
            result = None

        # Some FunctionInvocationContext implementations wrap the raw result
        # in a value-bearing object (legacy ToolTimingMiddleware did this);
        # mirror that defensiveness here so dict-shaped results from
        # file_capture are reachable regardless of wrapper shape.
        if result is not None and hasattr(result, "value"):
            result = result.value

        if not result:
            return

        if func_name == "file_capture" and isinstance(result, dict):
            if "bucket" in result:
                span.set_attribute("classification.bucket", str(result["bucket"]))
            if "confidence" in result:
                with contextlib.suppress(TypeError, ValueError):
                    span.set_attribute(
                        "classification.confidence", float(result["confidence"])
                    )
            if "status" in result:
                span.set_attribute("classification.status", str(result["status"]))
            if "itemId" in result:
                span.set_attribute("classification.item_id", str(result["itemId"]))

        if func_name == "transcribe_audio":
            span.set_attribute(
                "transcription.success", bool(result and isinstance(result, str))
            )
