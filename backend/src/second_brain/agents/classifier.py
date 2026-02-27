"""Classifier agent registration for Foundry Agent Service.

This module provides:
- ensure_classifier_agent(): Self-healing agent registration at startup

Agent instructions live in the AI Foundry portal -- editable without
redeployment. No local copy is kept in the repo.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_framework.azure import AzureAIAgentClient

logger = logging.getLogger(__name__)

async def ensure_classifier_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str,
) -> str:
    """Ensure the Classifier agent exists in Foundry.

    Self-healing: if the stored agent ID is valid, returns it. If missing
    or invalid, creates a new agent and returns the new ID.

    If agent registration fails, the exception propagates up to the
    lifespan and crashes the app (hard dependency per CONTEXT.md).

    Args:
        foundry_client: Initialized AzureAIAgentClient instance.
        stored_agent_id: Agent ID from AZURE_AI_CLASSIFIER_AGENT_ID env var.

    Returns:
        The validated or newly created agent ID.
    """
    if stored_agent_id:
        try:
            agent_info = await foundry_client.agents_client.get_agent(
                stored_agent_id
            )
            logger.info(
                "Classifier agent loaded: id=%s name=%s",
                agent_info.id,
                agent_info.name,
            )
            return stored_agent_id
        except Exception:
            logger.warning(
                "Stored agent ID %s not found in Foundry, "
                "creating new agent",
                stored_agent_id,
            )

    # Create agent shell -- instructions are managed in the AI Foundry portal
    new_agent = await foundry_client.agents_client.create_agent(
        model="gpt-4o",
        name="Classifier",
    )
    logger.info(
        "NEW Classifier agent: id=%s -- "
        "SET INSTRUCTIONS IN AI FOUNDRY PORTAL and "
        "UPDATE AZURE_AI_CLASSIFIER_AGENT_ID in env",
        new_agent.id,
    )
    return new_agent.id
