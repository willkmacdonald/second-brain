"""Investigation agent registration for Foundry Agent Service.

This module provides:
- ensure_investigation_agent(): Self-healing agent registration at startup

Agent instructions live in the AI Foundry portal -- editable without
redeployment. No local copy is kept in the repo.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_framework.azure import AzureAIAgentClient

logger = logging.getLogger(__name__)


async def ensure_investigation_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str,
) -> str:
    """Ensure the Investigation agent exists in Foundry.

    Self-healing: if the stored agent ID is valid, returns it. If missing
    or invalid, creates a new agent and returns the new ID.

    Investigation Agent registration is non-fatal -- if it fails, the app
    still starts (investigation is not required for core capture flow).
    The caller should catch exceptions.

    Args:
        foundry_client: Initialized AzureAIAgentClient instance.
        stored_agent_id: Agent ID from AZURE_AI_INVESTIGATION_AGENT_ID
            env var.

    Returns:
        The validated or newly created agent ID.
    """
    if stored_agent_id:
        try:
            agent_info = await foundry_client.agents_client.get_agent(stored_agent_id)
            logger.info(
                "Investigation agent loaded: id=%s name=%s",
                agent_info.id,
                agent_info.name,
            )
            return stored_agent_id
        except Exception:
            logger.warning(
                "Stored Investigation agent ID %s not found in "
                "Foundry, creating new agent",
                stored_agent_id,
            )

    # Create agent shell -- instructions managed in AI Foundry portal
    new_agent = await foundry_client.agents_client.create_agent(
        model="gpt-4o",
        name="InvestigationAgent",
    )
    logger.info(
        "NEW Investigation agent: id=%s -- "
        "SET INSTRUCTIONS IN AI FOUNDRY PORTAL and "
        "UPDATE AZURE_AI_INVESTIGATION_AGENT_ID in env",
        new_agent.id,
    )
    return new_agent.id
