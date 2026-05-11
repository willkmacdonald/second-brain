"""Background warm-up pings to prevent Azure AI Foundry agent cold starts.

Phase 24 task group 23.3 (plan 24-19): GA migration. The warmup loop takes
GA ``Agent`` instances and pings each agent via ``agent.run("ping")``. The
RC client + single-message ping shape has been removed.

Self-heal still works in shape — the factory dict now produces GA Agent
objects via the ``build_*_agent`` factories. The factory is invoked with
no arguments per call site; each factory closes over its scoped
``chat_client``, tool list, and middleware at lifespan-construction time.
"""

import asyncio
import logging
from collections.abc import Callable

from agent_framework import Agent

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3


async def agent_warmup_loop(
    agents: list[tuple[str, Agent]],
    interval_seconds: int,
    agent_factories: dict[str, Callable[[], Agent]] | None = None,
    on_recreate: Callable[[str, Agent], None] | None = None,
) -> None:
    """Ping agents periodically to keep them warm.

    Self-heals unresponsive agents by recreating the Agent via its factory
    after MAX_CONSECUTIVE_FAILURES consecutive ping failures.

    Args:
        agents: List of (name, agent) tuples to ping.
        interval_seconds: Seconds between ping rounds.
        agent_factories: Optional dict mapping agent name to a callable that
            returns a fresh ``Agent``. Used for self-healing.
        on_recreate: Optional callback invoked with (name, new_agent) after
            successful agent recreation, so the caller can update app.state.
    """
    failure_counts: dict[str, int] = {name: 0 for name, _ in agents}

    while True:
        await asyncio.sleep(interval_seconds)
        for idx, (name, agent) in enumerate(agents):
            try:
                await agent.run("ping")
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
                    and agent_factories
                    and name in agent_factories
                ):
                    logger.error(
                        "Warmup: %s failed %d consecutive pings "
                        "-- attempting agent recreation",
                        name,
                        failure_counts[name],
                    )
                    try:
                        new_agent = agent_factories[name]()
                        agents[idx] = (name, new_agent)
                        if on_recreate:
                            on_recreate(name, new_agent)
                        failure_counts[name] = 0
                        logger.info("Warmup: %s agent recreated successfully", name)
                    except Exception:
                        logger.error(
                            "Warmup: failed to recreate %s agent",
                            name,
                            exc_info=True,
                        )
