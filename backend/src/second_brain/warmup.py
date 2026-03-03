"""Background warm-up pings to prevent Azure AI Foundry agent cold starts."""

import asyncio
import logging

from agent_framework import Message
from agent_framework.azure import AzureAIAgentClient

logger = logging.getLogger(__name__)


async def agent_warmup_loop(
    clients: list[tuple[str, AzureAIAgentClient]],
    interval_seconds: int,
) -> None:
    """Ping agents periodically to keep them warm.

    Args:
        clients: List of (name, client) tuples to ping.
        interval_seconds: Seconds between ping rounds.
    """
    messages = [Message(role="user", text="ping")]

    while True:
        await asyncio.sleep(interval_seconds)
        for name, client in clients:
            try:
                await client.get_response(messages=messages)
                logger.debug("Warmup ping OK: %s", name)
            except Exception:
                logger.warning("Warmup ping failed: %s", name, exc_info=True)
