"""Agent middleware for audit logging and tool timing.

AuditAgentMiddleware logs agent run start/end with elapsed time.
ToolTimingMiddleware logs tool call name, timing, and structured result
fields for AppInsights queryability.
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

logger = logging.getLogger(__name__)


class AuditAgentMiddleware(AgentMiddleware):
    """Logs agent run start/end with elapsed time.

    Uses Foundry's built-in thread/run IDs for correlation (no custom
    run_id). Token usage tracking deferred to Phase 9.
    """

    async def process(
        self,
        context: AgentContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Log agent run lifecycle."""
        start = time.monotonic()
        logger.info("[Agent] Run started")

        await call_next()

        elapsed = time.monotonic() - start
        logger.info("[Agent] Run completed in %.3fs", elapsed)


class ToolTimingMiddleware(FunctionMiddleware):
    """Logs tool call name, timing, and structured result summary.

    For file_capture success results, logs bucket/confidence/status/item_id
    as structured fields queryable in AppInsights. Tool failures are logged
    at WARNING level per CONTEXT.md.
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Log tool call with timing and result inspection."""
        func_name = context.function.name
        logger.info("[Tool] Calling %s", func_name)

        start = time.monotonic()
        await call_next()
        elapsed = time.monotonic() - start

        result = context.result
        if isinstance(result, dict) and "bucket" in result:
            # file_capture success -- log structured fields
            logger.info(
                "[Tool] %s completed in %.3fs: "
                "bucket=%s confidence=%.2f status=%s item_id=%s",
                func_name,
                elapsed,
                result.get("bucket"),
                result.get("confidence"),
                result.get("status", "classified"),
                result.get("item_id"),
            )
        elif isinstance(result, dict) and "error" in result:
            # Tool failure -- WARNING per CONTEXT.md
            logger.warning(
                "[Tool] %s failed in %.3fs: error=%s detail=%s",
                func_name,
                elapsed,
                result.get("error"),
                result.get("detail"),
            )
        else:
            # Generic completion (e.g. transcribe_audio)
            logger.info(
                "[Tool] %s completed in %.3fs",
                func_name,
                elapsed,
            )
