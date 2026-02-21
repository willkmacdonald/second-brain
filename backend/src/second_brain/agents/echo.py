"""Phase 1 test agent that echoes back user messages via Azure OpenAI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from second_brain.config import get_settings
from second_brain.tools.cosmos_crud import CosmosCrudTools

if TYPE_CHECKING:
    from second_brain.db.cosmos import CosmosManager


def create_echo_agent(
    cosmos_manager: CosmosManager | None = None,
) -> Agent:
    """Create an echo agent using AzureOpenAIChatClient.

    Uses DefaultAzureCredential for auth (az login locally,
    managed identity in production). Reads endpoint and deployment
    from Settings.

    Args:
        cosmos_manager: Optional CosmosManager for CRUD tool access.
            When provided, the agent gains create/read/list document tools.
    """
    settings = get_settings()

    chat_client = AzureOpenAIChatClient(
        credential=DefaultAzureCredential(),
        endpoint=settings.azure_openai_endpoint,
        deployment_name=settings.azure_openai_chat_deployment_name,
    )

    tools: list = []
    if cosmos_manager is not None:
        crud = CosmosCrudTools(cosmos_manager)
        tools = [crud.create_document, crud.read_document, crud.list_documents]

    return chat_client.as_agent(
        name="SecondBrainEcho",
        instructions=(
            "You are a test agent for the Second Brain system. "
            "You can create and read documents in the Inbox, People, "
            "Projects, Ideas, and Admin containers. "
            "Echo back what the user says and confirm operations."
        ),
        tools=tools,
    )
