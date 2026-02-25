"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_chat_deployment_name: str = "gpt-4o"

    # Cosmos DB
    cosmos_endpoint: str = ""

    # Azure Key Vault
    key_vault_url: str = ""
    api_key_secret_name: str = "second-brain-api-key"

    # Azure Blob Storage (voice recordings)
    blob_storage_url: str = ""

    # Azure OpenAI Whisper (transcription)
    azure_openai_whisper_deployment_name: str = "whisper"

    # Classification
    classification_threshold: float = 0.6

    # Database
    database_name: str = "second-brain"

    # OpenTelemetry
    enable_instrumentation: bool = True
    enable_sensitive_data: bool = False

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
