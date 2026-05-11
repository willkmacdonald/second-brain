"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # Azure AI Foundry
    azure_ai_project_endpoint: str = ""
    foundry_model: str = "gpt-4o"  # Phase 24 task group 23.1 (GA chat client model)

    # Azure OpenAI (transcription API -- separate from Foundry project endpoint)
    azure_openai_endpoint: str = ""
    azure_openai_transcription_deployment: str = "gpt-4o-transcribe"

    # Application Insights
    applicationinsights_connection_string: str = ""

    # Log Analytics (workspace queries via LogsQueryClient)
    log_analytics_workspace_id: str = ""

    # Cosmos DB
    cosmos_endpoint: str = ""

    # Azure Key Vault
    key_vault_url: str = ""
    api_key_secret_name: str = "second-brain-api-key"

    # Sentry (mobile error tracking -- used by spine Sentry adapter)
    sentry_auth_token: str = ""
    sentry_org: str = ""
    sentry_project_mobile: str = ""

    # Azure Blob Storage (voice recordings -- kept for future use)
    blob_storage_url: str = ""

    # Agent warm-up (prevents cold starts)
    agent_warmup_enabled: bool = True
    agent_warmup_interval_minutes: int = 5

    # Classification
    classification_threshold: float = 0.6

    # Database
    database_name: str = "second-brain"

    # Environment (controls docs visibility -- defaults to production
    # so Swagger is not accidentally exposed if env var is unset)
    environment: str = "production"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        # Tolerate orphan env vars (e.g. AZURE_AI_CLASSIFIER_AGENT_ID) that
        # remain on the Container App between Phase 24 source-code cleanup
        # (this plan, 24-21) and post-UAT env-var removal (24-23). Per
        # 23-foundry-ga-prep/CONFIG-DELTAS.md Step C the GA image must boot
        # cleanly even though those vars are still set in the environment.
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
