"""Investigation agent factory.

GA pattern (Phase 24 task group 23.1): instructions live in repo (D-02),
Agent constructed at lifespan startup with bound tool methods and capture-trace
middleware. Replaces the RC portal-shell ensure_*_agent creation pattern (F-19).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient

logger = logging.getLogger(__name__)

INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"


def load_instructions(name: str) -> str:
    """Read agents/instructions/{name}.md and return its contents.

    Raises FileNotFoundError if the file is missing — fail fast at startup.
    """
    return (INSTRUCTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")


def build_investigation_agent(
    chat_client: FoundryChatClient,
    tools: Sequence[Any],
    middleware: Sequence[Any],
) -> Agent:
    """Construct the Investigation Agent."""
    instructions = load_instructions("investigation")
    return Agent(
        client=chat_client,
        instructions=instructions,
        tools=list(tools),
        middleware=list(middleware),
    )
