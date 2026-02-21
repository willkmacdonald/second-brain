"""Shared test fixtures for the Second Brain backend."""

import pytest

from second_brain.config import Settings


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
