"""Orchestrator agent that routes input to specialist agents."""

from __future__ import annotations

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient


def create_orchestrator_agent(chat_client: AzureOpenAIChatClient) -> Agent:
    """Create the Orchestrator agent.

    The Orchestrator receives all user input and routes to the appropriate
    specialist. For Phase 3 (text only), it always routes to the Classifier.
    """
    return chat_client.as_agent(
        name="Orchestrator",
        instructions=(
            "You are the Orchestrator for a personal knowledge management system. "
            "Your ONLY job is to route user input to the correct specialist agent. "
            "NEVER answer questions directly. ALWAYS hand off to a specialist.\n\n"
            "Input may be typed text or transcribed speech from the Perception Agent. "
            "In both cases: hand off to the Classifier agent immediately.\n\n"
            "Do not add commentary. Just hand off."
        ),
        description="Routes user input to the appropriate specialist agent",
    )
