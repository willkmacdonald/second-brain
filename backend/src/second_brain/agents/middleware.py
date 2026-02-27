"""Agent middleware skeletons for Foundry Agent Service.

Validates that AgentMiddleware and FunctionMiddleware interfaces work
with the Foundry agent framework. Structured observability (AppInsights
custom dimensions, token tracking) is wired in Phase 9.
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
    """Skeleton: logs agent run start/end to console.

    Phase 9 replaces console logging with Application Insights traces
    including token usage and Foundry thread/run ID correlation.
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
    """Skeleton: logs tool call name and timing to console.

    Phase 9 replaces console logging with Application Insights custom
    dimensions (bucket, confidence, status, item_id) for structured
    querying.
    """

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        """Log tool call with timing."""
        func_name = context.function.name
        start = time.monotonic()

        await call_next()

        elapsed = time.monotonic() - start
        logger.info("[Tool] %s completed in %.3fs", func_name, elapsed)
