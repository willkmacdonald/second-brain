"""Integration tests for the Classifier agent (requires live Azure credentials).

These tests hit deployed Foundry and Cosmos services. They are skipped in CI
and local runs by default -- run with:

    pytest -m integration tests/test_classifier_integration.py -v

Prerequisites:
- AZURE_AI_PROJECT_ENDPOINT set to a valid Foundry project endpoint
- AZURE_AI_CLASSIFIER_AGENT_ID set to a registered Classifier agent ID
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

from second_brain.db.cosmos import CONTAINER_NAMES
from second_brain.tools.classification import ClassifierTools

_SKIP_REASON = (
    "Integration test requires AZURE_AI_PROJECT_ENDPOINT "
    "and AZURE_AI_CLASSIFIER_AGENT_ID"
)

_has_credentials = bool(
    os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    and os.environ.get("AZURE_AI_CLASSIFIER_AGENT_ID")
)


def _make_mock_cosmos_manager() -> MagicMock:
    """Create a mock CosmosManager for integration tests.

    Self-contained (no fixture dependency) so integration tests
    remain independent from the unit test conftest.
    """
    manager = MagicMock()
    containers: dict = {}
    for name in CONTAINER_NAMES:
        container = MagicMock()
        container.create_item = AsyncMock(side_effect=lambda *, body: body)
        container.read_item = AsyncMock()
        container.upsert_item = AsyncMock()
        container.delete_item = AsyncMock()
        container.query_items = MagicMock()
        containers[name] = container
    manager.containers = containers
    manager.get_container = MagicMock(side_effect=lambda n: containers[n])
    return manager


@pytest.mark.integration
@pytest.mark.skipif(not _has_credentials, reason=_SKIP_REASON)
async def test_classifier_agent_classifies_text() -> None:
    """Send text to the Classifier agent and verify it calls file_capture.

    Uses a mock CosmosManager so no real Cosmos writes occur, but the
    agent runs in Foundry and makes a real tool call.
    """
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    agent_id = os.environ["AZURE_AI_CLASSIFIER_AGENT_ID"]

    credential = DefaultAzureCredential()
    mock_manager = _make_mock_cosmos_manager()

    try:
        classifier_tools = ClassifierTools(
            cosmos_manager=mock_manager,
            classification_threshold=0.6,
        )

        client = AzureAIAgentClient(
            credential=credential,
            project_endpoint=endpoint,
            agent_id=agent_id,
            should_cleanup_agent=False,
        )

        messages = [Message(role="user", text="Pick up prescription at Walgreens")]
        options = ChatOptions(tools=[classifier_tools.file_capture])

        response = await client.get_response(messages=messages, options=options)

        # Agent should produce a text response (e.g. "Filed to Admin (0.85)")
        assert response.text is not None
        assert len(response.text) > 0

        # The agent should have invoked file_capture, which writes to Inbox
        inbox_container = mock_manager.get_container("Inbox")
        assert inbox_container.create_item.call_count >= 1

        # Inspect the Inbox write: status should be one of the valid values
        inbox_body = inbox_container.create_item.call_args[1]["body"]
        assert inbox_body["status"] in ("classified", "pending", "misunderstood")

    finally:
        await credential.close()


@pytest.mark.integration
@pytest.mark.skipif(not _has_credentials, reason=_SKIP_REASON)
async def test_classifier_agent_id_is_valid() -> None:
    """Verify the stored agent ID is retrievable from Foundry.

    Validates AGNT-01: agent visible in Foundry with stable ID.
    """
    endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    agent_id = os.environ["AZURE_AI_CLASSIFIER_AGENT_ID"]

    credential = DefaultAzureCredential()

    try:
        client = AzureAIAgentClient(
            credential=credential,
            project_endpoint=endpoint,
            model_deployment_name="gpt-4o",
        )

        agent_info = await client.agents_client.get_agent(agent_id)
        assert agent_info.name == "Classifier"
        assert agent_info.id == agent_id

    finally:
        await credential.close()
