"""Background warm-up pings to prevent Azure AI Foundry agent cold starts."""

import asyncio
import logging
from collections.abc import Callable

from agent_framework import Message
from agent_framework.azure import AzureAIAgentClient

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3


async def agent_warmup_loop(
    clients: list[tuple[str, AzureAIAgentClient]],
    interval_seconds: int,
    client_factories: dict[str, Callable[[], AzureAIAgentClient]] | None = None,
    on_recreate: Callable[[str, AzureAIAgentClient], None] | None = None,
) -> None:
    """Ping agents periodically to keep them warm.

    Self-heals unresponsive agents by recreating their client after
    MAX_CONSECUTIVE_FAILURES consecutive ping failures.

    Args:
        clients: List of (name, client) tuples to ping.
        interval_seconds: Seconds between ping rounds.
        client_factories: Optional dict mapping agent name to a callable that
            returns a fresh AzureAIAgentClient. Used for self-healing.
        on_recreate: Optional callback invoked with (name, new_client) after
            successful client recreation, so the caller can update app.state.
    """
    messages = [Message(role="user", text="ping")]
    failure_counts: dict[str, int] = {name: 0 for name, _ in clients}

    while True:
        await asyncio.sleep(interval_seconds)
        for idx, (name, client) in enumerate(clients):
            try:
                await client.get_response(messages=messages)
                logger.debug("Warmup ping OK: %s", name)
                failure_counts[name] = 0
            except Exception:
                failure_counts[name] = failure_counts.get(name, 0) + 1
                logger.warning(
                    "Warmup ping failed: %s (consecutive=%d)",
                    name,
                    failure_counts[name],
                    exc_info=True,
                )

                if (
                    failure_counts[name] >= MAX_CONSECUTIVE_FAILURES
                    and client_factories
                    and name in client_factories
                ):
                    logger.error(
                        "Warmup: %s failed %d consecutive pings "
                        "-- attempting client recreation",
                        name,
                        failure_counts[name],
                    )
                    try:
                        new_client = client_factories[name]()
                        clients[idx] = (name, new_client)
                        if on_recreate:
                            on_recreate(name, new_client)
                        failure_counts[name] = 0
                        logger.info("Warmup: %s client recreated successfully", name)
                    except Exception:
                        logger.error(
                            "Warmup: failed to recreate %s client",
                            name,
                            exc_info=True,
                        )
