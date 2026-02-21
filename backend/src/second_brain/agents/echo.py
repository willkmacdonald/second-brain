"""Phase 1 test agent that echoes back user messages via Azure OpenAI."""

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

from second_brain.config import get_settings


def create_echo_agent() -> Agent:
    """Create an echo agent using AzureOpenAIChatClient.

    Uses DefaultAzureCredential for auth (az login locally,
    managed identity in production). Reads endpoint and deployment
    from Settings.
    """
    settings = get_settings()

    chat_client = AzureOpenAIChatClient(
        credential=DefaultAzureCredential(),
        endpoint=settings.azure_openai_endpoint,
        deployment_name=settings.azure_openai_chat_deployment_name,
    )

    return chat_client.as_agent(
        name="SecondBrainEcho",
        instructions=(
            "You are a test agent for the Second Brain system. "
            "Echo back what the user says and confirm the system is working. "
            "Keep responses brief."
        ),
    )
