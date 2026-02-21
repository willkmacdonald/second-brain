"""Shared test fixtures for the Second Brain backend."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from second_brain.config import Settings
from second_brain.db.cosmos import CONTAINER_NAMES, CosmosManager


@pytest.fixture
def settings() -> Settings:
    """Provide test-safe settings with placeholder values."""
    return Settings(
        azure_openai_endpoint="https://test.openai.azure.com/",
        azure_openai_chat_deployment_name="gpt-4o-test",
        cosmos_endpoint="https://test.documents.azure.com:443/",
        key_vault_url="https://test-vault.vault.azure.net/",
        enable_instrumentation=False,
        enable_sensitive_data=False,
    )


@pytest.fixture
def mock_cosmos_manager() -> CosmosManager:
    """Return a mock CosmosManager with mock containers.

    Each container has async mocks for create_item, read_item,
    and query_items. No real Azure calls are made.
    """
    manager = MagicMock(spec=CosmosManager)

    containers: dict = {}
    for name in CONTAINER_NAMES:
        container = MagicMock()
        container.create_item = AsyncMock()
        container.read_item = AsyncMock()
        container.query_items = MagicMock()  # Returns an async iterator
        containers[name] = container

    manager.containers = containers
    manager.get_container = MagicMock(side_effect=lambda n: containers[n])

    return manager
