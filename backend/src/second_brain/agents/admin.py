"""Admin agent factory.

GA pattern (Phase 24 task group 23.2): mirrors agents/investigation.py.
Reuses load_instructions from agents/investigation. Replaces the
RC portal-shell creation pattern (F-19).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient

from second_brain.agents.investigation import load_instructions

logger = logging.getLogger(__name__)


def build_admin_agent(
    chat_client: FoundryChatClient,
    tools: Sequence[Any],
    middleware: Sequence[Any],
) -> Agent:
    """Construct the Admin Agent (single-turn, non-streaming)."""
    instructions = load_instructions("admin")
    return Agent(
        client=chat_client,
        instructions=instructions,
        tools=list(tools),
        middleware=list(middleware),
    )
