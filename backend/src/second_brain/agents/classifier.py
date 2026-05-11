"""Classifier agent factory.

GA pattern (Phase 24 task group 23.3): mirrors agents/investigation.py and
agents/admin.py. Per D-04 (voice path split): classifier registers ONLY
file_capture. Transcription is a direct helper called from api/capture.py
when audio is on the request -- no longer a registered tool.

Replaces the RC portal-shell creation pattern (F-19).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from agent_framework import Agent
from agent_framework_foundry import FoundryChatClient

from second_brain.agents.investigation import load_instructions

logger = logging.getLogger(__name__)


def build_classifier_agent(
    chat_client: FoundryChatClient,
    tools: Sequence[Any],
    middleware: Sequence[Any],
) -> Agent:
    """Construct the Classifier Agent (streaming, single-tool: file_capture).

    Per CONTEXT D-04: tools list MUST contain ONLY file_capture. With one
    tool registered, tool_choice='required' (set on agent.run() options) is
    unambiguous -- the model must call file_capture. The Python safety net
    is deleted (D-03); failures route to forced_tool_failure SSE sub-code.
    """
    instructions = load_instructions("classifier")
    return Agent(
        client=chat_client,
        instructions=instructions,
        tools=list(tools),
        middleware=list(middleware),
    )
