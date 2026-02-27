"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # Azure AI Foundry
    azure_ai_project_endpoint: str = ""
    azure_ai_classifier_agent_id: str = ""

    # Application Insights
    applicationinsights_connection_string: str = ""

    # Cosmos DB
    cosmos_endpoint: str = ""

    # Azure Key Vault
    key_vault_url: str = ""
    api_key_secret_name: str = "second-brain-api-key"

    # Azure Blob Storage (voice recordings -- kept for future use)
    blob_storage_url: str = ""

    # Classification
    classification_threshold: float = 0.6

    # Database
    database_name: str = "second-brain"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
