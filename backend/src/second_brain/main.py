"""FastAPI app with inbox API, health check, and Cosmos DB persistence."""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env BEFORE any other imports that read env vars
load_dotenv()

from azure.monitor.opentelemetry import configure_azure_monitor  # noqa: E402

from second_brain.observability.span_processor import CaptureTraceSpanProcessor  # noqa: E402

# Scope log collection to application loggers only -- prevents azure-core,
# azure-cosmos, and azure-identity internal noise from flooding App Insights.
logging.getLogger("second_brain").setLevel(logging.INFO)
configure_azure_monitor(
    logger_name="second_brain",
    span_processors=[CaptureTraceSpanProcessor()],
)

from agent_framework.observability import enable_instrumentation  # noqa: E402

# Enable agent-framework instrumentation AFTER Azure Monitor configures exporters.
# Automatically tracks gen_ai.usage.input_tokens, gen_ai.usage.output_tokens,
# and gen_ai.operation.duration as OTel metrics for every get_response() call.
enable_instrumentation()

from agent_framework.azure import DurableAIAgentClient  # noqa: E402
from azure.identity.aio import (  # noqa: E402
    DefaultAzureCredential as AsyncDefaultAzureCredential,
    get_bearer_token_provider,
)
from azure.keyvault.secrets.aio import SecretClient as KeyVaultSecretClient  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from openai import AsyncAzureOpenAI  # noqa: E402

from second_brain.agents.admin import ensure_admin_agent  # noqa: E402
from second_brain.agents.classifier import ensure_classifier_agent  # noqa: E402
from second_brain.agents.investigation import ensure_investigation_agent  # noqa: E402
from second_brain.agents.middleware import (  # noqa: E402
    AuditAgentMiddleware,
    ToolTimingMiddleware,
)
from second_brain.api.capture import router as capture_router  # noqa: E402
from second_brain.api.health import router as health_router  # noqa: E402
from second_brain.api.inbox import router as inbox_router  # noqa: E402
from second_brain.api.investigate import router as investigate_router  # noqa: E402
from second_brain.api.errands import router as errands_router  # noqa: E402
from second_brain.api.feedback import router as feedback_router  # noqa: E402
from second_brain.api.tasks import router as tasks_router  # noqa: E402
from second_brain.api.telemetry import router as telemetry_router  # noqa: E402
from second_brain.auth import APIKeyMiddleware  # noqa: E402
from second_brain.config import get_settings  # noqa: E402
from second_brain.db.blob_storage import BlobStorageManager  # noqa: E402
from second_brain.db.cosmos import CosmosManager  # noqa: E402
from second_brain.observability.client import close_logs_client, create_logs_client  # noqa: E402
from second_brain.spine.middleware import SpineWorkloadMiddleware  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

from second_brain.streaming.investigation_adapter import SoftRateLimiter  # noqa: E402
from second_brain.tools.admin import AdminTools  # noqa: E402
from second_brain.tools.classification import ClassifierTools  # noqa: E402
from second_brain.tools.investigation import InvestigationTools  # noqa: E402
from second_brain.tools.recipe import RecipeTools  # noqa: E402
from second_brain.tools.transcription import TranscriptionTools  # noqa: E402
from second_brain.warmup import agent_warmup_loop  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Spine lifespan helper
# ---------------------------------------------------------------------------


async def _wire_spine(
    app: FastAPI,
    settings,
) -> tuple[asyncio.Task | None, list[asyncio.Task]]:
    """Wire spine into app lifespan. Returns (evaluator_task, liveness_tasks).

    evaluator_task is None when spine wiring is skipped or fails.
    liveness_tasks is empty when spine wiring is skipped or fails.
    Sets app.state.spine_repo (or None on skip/failure).
    """
    from functools import partial

    from second_brain.observability.queries import (
        fetch_agent_runs,
        query_backend_api_failures,
        query_backend_api_requests,
    )
    from second_brain.spine.adapters.backend_api import BackendApiAdapter
    from second_brain.spine.adapters.foundry_agent import FoundryAgentAdapter
    from second_brain.spine.adapters.registry import AdapterRegistry
    from second_brain.spine.api import build_spine_router
    from second_brain.spine.auth import spine_auth
    from second_brain.spine.background import evaluator_loop, liveness_emitter
    from second_brain.spine.evaluator import StatusEvaluator
    from second_brain.spine.registry import get_default_registry
    from second_brain.spine.storage import SpineRepository

    spine_evaluator_task: asyncio.Task | None = None
    spine_liveness_tasks: list[asyncio.Task] = []

    try:
        if app.state.cosmos_manager is None:
            logger.warning("Spine wiring skipped: cosmos_manager unavailable")
            app.state.spine_repo = None
            return None, []

        cosmos_mgr_for_spine = app.state.cosmos_manager
        spine_repo = SpineRepository(
            events_container=cosmos_mgr_for_spine.get_container("spine_events"),
            segment_state_container=cosmos_mgr_for_spine.get_container(
                "spine_segment_state"
            ),
            status_history_container=cosmos_mgr_for_spine.get_container(
                "spine_status_history"
            ),
            correlation_container=cosmos_mgr_for_spine.get_container(
                "spine_correlation"
            ),
        )
        app.state.spine_repo = spine_repo

        spine_registry = get_default_registry()
        spine_evaluator = StatusEvaluator(repo=spine_repo, registry=spine_registry)

        # The backend_api adapter requires the LogsQueryClient; if init
        # earlier was non-fatal-failed, ship spine without the adapter
        # (status/ingest/correlation endpoints still work).
        adapters: list = []
        if app.state.logs_client is not None and settings.log_analytics_workspace_id:
            failures_fetcher = partial(
                query_backend_api_failures,
                app.state.logs_client,
                settings.log_analytics_workspace_id,
            )
            requests_fetcher = partial(
                query_backend_api_requests,
                app.state.logs_client,
                settings.log_analytics_workspace_id,
            )
            adapters.append(
                BackendApiAdapter(
                    failures_fetcher=failures_fetcher,
                    requests_fetcher=requests_fetcher,
                    native_url_template=(
                        "https://portal.azure.com/#blade/AppInsightsExtension"
                    ),
                )
            )
            logger.info("Spine BackendApiAdapter wired")

            # Phase 3: External Services adapter (same App Insights queries)
            from second_brain.spine.adapters.external_services import (
                ExternalServicesAdapter,
            )

            adapters.append(
                ExternalServicesAdapter(
                    failures_fetcher=failures_fetcher,
                    requests_fetcher=requests_fetcher,
                    native_url_template=(
                        "https://portal.azure.com/#blade/AppInsightsExtension"
                    ),
                )
            )
            logger.info("Spine ExternalServicesAdapter wired")

            # Container App rollup adapter (same App Insights queries)
            from second_brain.spine.adapters.container_app import (
                ContainerAppAdapter,
            )

            adapters.append(
                ContainerAppAdapter(
                    failures_fetcher=failures_fetcher,
                    requests_fetcher=requests_fetcher,
                    native_url_template=(
                        "https://portal.azure.com/#blade/AppInsightsExtension"
                    ),
                )
            )
            logger.info("Spine ContainerAppAdapter wired")

            # Phase 2: Foundry agent adapters (reuse same logs client)
            spans_fetcher = partial(
                fetch_agent_runs,
                app.state.logs_client,
                settings.log_analytics_workspace_id,
            )
            agent_segments = [
                (
                    "classifier",
                    getattr(app.state, "classifier_agent_id", None),
                    "Classifier",
                ),
                (
                    "admin",
                    getattr(app.state, "admin_agent_id", None),
                    "Admin Agent",
                ),
                (
                    "investigation",
                    getattr(app.state, "investigation_agent_id", None),
                    "Investigation Agent",
                ),
            ]
            for seg_id, agent_id, agent_name in agent_segments:
                if agent_id:
                    adapters.append(
                        FoundryAgentAdapter(
                            segment_id=seg_id,
                            agent_id=agent_id,
                            agent_name=agent_name,
                            spans_fetcher=spans_fetcher,
                            native_url_template=(
                                f"https://ai.azure.com/build/agents/{agent_id}"
                            ),
                        )
                    )
            logger.info(
                "Spine Foundry agent adapters wired: %d",
                len(adapters) - 1,
            )

            # Phase 3: Cosmos diagnostic logs adapter
            from second_brain.observability.queries import (
                fetch_cosmos_diagnostics,
            )
            from second_brain.spine.adapters.cosmos import CosmosAdapter

            cosmos_diag_fetcher = partial(
                fetch_cosmos_diagnostics,
                app.state.logs_client,
                settings.log_analytics_workspace_id,
            )
            adapters.append(
                CosmosAdapter(
                    diagnostics_fetcher=cosmos_diag_fetcher,
                    native_url=(
                        "https://portal.azure.com/#blade/Microsoft_Azure_DocumentDB"
                    ),
                )
            )
            logger.info("Spine CosmosAdapter wired")
        else:
            logger.warning("Spine wired without adapters: logs_client unavailable")

        # Phase 4: Mobile composite adapters (Sentry + spine telemetry)
        # These adapters use spine_repo directly, not logs_client, so they
        # are wired unconditionally (regardless of logs_client availability).
        from second_brain.spine.adapters.composite import CompositeAdapter
        from second_brain.spine.adapters.mobile_telemetry import MobileTelemetryAdapter
        from second_brain.spine.adapters.sentry import (
            SentryAdapter,
            make_sentry_fetcher,
        )

        _sentry_auth_token = getattr(settings, "sentry_auth_token", "")
        _sentry_org = getattr(settings, "sentry_org", "")
        _sentry_project_mobile = getattr(settings, "sentry_project_mobile", "")
        if _sentry_auth_token and _sentry_org and _sentry_project_mobile:
            sentry_fetcher = await make_sentry_fetcher(
                auth_token=_sentry_auth_token,
                org=_sentry_org,
                project=_sentry_project_mobile,
            )
            sentry_ui = SentryAdapter(
                segment_id="mobile_ui",
                sentry_fetcher=sentry_fetcher,
                native_url_template=(
                    f"https://sentry.io/organizations/{_sentry_org}"
                    f"/projects/{_sentry_project_mobile}"
                    f"/?query=app_segment%3Amobile_ui"
                ),
                tag_filter={"app_segment": "mobile_ui"},
            )
            sentry_capture = SentryAdapter(
                segment_id="mobile_capture",
                sentry_fetcher=sentry_fetcher,
                native_url_template=(
                    f"https://sentry.io/organizations/{_sentry_org}"
                    f"/projects/{_sentry_project_mobile}"
                    f"/?query=app_segment%3Amobile_capture"
                ),
                tag_filter={"app_segment": "mobile_capture"},
            )
        else:
            sentry_ui = None
            sentry_capture = None

        mobile_telemetry_ui = MobileTelemetryAdapter(
            segment_id="mobile_ui",
            repo=spine_repo,
            native_url="https://portal.azure.com/#blade/AppInsightsExtension",
        )
        mobile_telemetry_capture = MobileTelemetryAdapter(
            segment_id="mobile_capture",
            repo=spine_repo,
            native_url="https://portal.azure.com/#blade/AppInsightsExtension",
        )

        mobile_ui_composite = CompositeAdapter(
            segment_id="mobile_ui",
            sources={
                **({"sentry": sentry_ui} if sentry_ui else {}),
                "telemetry": mobile_telemetry_ui,
            },
            native_url=(
                sentry_ui.native_url_template
                if sentry_ui
                else mobile_telemetry_ui.native_url_template
            ),
        )
        mobile_capture_composite = CompositeAdapter(
            segment_id="mobile_capture",
            sources={
                **({"sentry": sentry_capture} if sentry_capture else {}),
                "telemetry": mobile_telemetry_capture,
            },
            native_url=(
                sentry_capture.native_url_template
                if sentry_capture
                else mobile_telemetry_capture.native_url_template
            ),
        )
        adapters.extend([mobile_ui_composite, mobile_capture_composite])
        logger.info("Spine mobile composite adapters wired")

        adapter_registry = AdapterRegistry(adapters)
        app.state.spine_adapter_registry = adapter_registry

        # Create background tasks BEFORE mounting the router so that a
        # failure in task creation cannot leave routes mounted against a
        # repo that the `except` below resets to None (I2 fix).
        spine_evaluator_task = asyncio.create_task(
            evaluator_loop(spine_evaluator, spine_repo, spine_registry)
        )
        # Liveness emitters for all registered segments
        for seg_cfg in spine_registry.all():
            spine_liveness_tasks.append(
                asyncio.create_task(
                    liveness_emitter(spine_repo, segment_id=seg_cfg.segment_id)
                )
            )
        logger.info(
            "Spine liveness emitters started: %d",
            len(spine_liveness_tasks),
        )

        from second_brain.observability.queries import (
            fetch_audit_cosmos_diagnostics_for_correlation,
            fetch_audit_exceptions_for_correlation,
            fetch_audit_spans_for_correlation,
        )
        from second_brain.spine.audit.native_lookup import NativeLookup
        from second_brain.spine.audit.walker import CorrelationAuditor

        if app.state.logs_client is not None and settings.log_analytics_workspace_id:
            audit_lookup = NativeLookup(
                spans_fetcher=partial(
                    fetch_audit_spans_for_correlation,
                    app.state.logs_client,
                    settings.log_analytics_workspace_id,
                ),
                exceptions_fetcher=partial(
                    fetch_audit_exceptions_for_correlation,
                    app.state.logs_client,
                    settings.log_analytics_workspace_id,
                ),
                cosmos_fetcher=partial(
                    fetch_audit_cosmos_diagnostics_for_correlation,
                    app.state.logs_client,
                    settings.log_analytics_workspace_id,
                ),
            )
        else:
            audit_lookup = NativeLookup(
                spans_fetcher=None,
                exceptions_fetcher=None,
                cosmos_fetcher=None,
            )
        spine_auditor = CorrelationAuditor(repo=spine_repo, lookup=audit_lookup)

        app.include_router(
            build_spine_router(
                repo=spine_repo,
                evaluator=spine_evaluator,
                adapter_registry=adapter_registry,
                segment_registry=spine_registry,
                auth_dependency=spine_auth,
                auditor=spine_auditor,
            )
        )
        logger.info("Spine lifespan wiring complete")
    except Exception:
        logger.warning("Spine wiring failed -- spine unavailable", exc_info=True)
        for _task in [spine_evaluator_task, *spine_liveness_tasks]:
            if _task is not None:
                _task.cancel()
        app.state.spine_repo = None
        app.state.spine_adapter_registry = None
        spine_evaluator_task = None
        spine_liveness_tasks = []

    return spine_evaluator_task, spine_liveness_tasks


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources at startup, clean up at shutdown."""
    settings = get_settings()

    # Async credential -- persists for the entire lifespan (used by Key Vault,
    # Foundry agent client, and OpenAI transcription client)
    credential = AsyncDefaultAzureCredential()
    app.state.credential = credential

    try:
        # Fetch API key from Azure Key Vault
        kv_client = KeyVaultSecretClient(
            vault_url=settings.key_vault_url, credential=credential
        )
        try:
            secret = await kv_client.get_secret(settings.api_key_secret_name)
            app.state.api_key = secret.value
            logger.info("API key fetched from Key Vault")
        except Exception:
            logger.warning(
                "Could not fetch API key from Key Vault. "
                "API key auth will not be available until Key Vault is configured."
            )
            app.state.api_key = None
        finally:
            await kv_client.close()

        # Initialize Cosmos DB client singleton
        cosmos_mgr = CosmosManager(
            endpoint=settings.cosmos_endpoint,
            database_name=settings.database_name,
        )
        try:
            await cosmos_mgr.initialize()
            app.state.cosmos_manager = cosmos_mgr
            logger.info("Cosmos DB manager initialized")
        except Exception:
            logger.warning(
                "Could not initialize Cosmos DB. "
                "Database operations will not be available "
                "until Cosmos DB is configured."
            )
            app.state.cosmos_manager = None
            cosmos_mgr = None

        # --- LogsQueryClient (non-fatal) ---
        try:
            logs_client = create_logs_client(credential)
            app.state.logs_client = logs_client
            app.state.log_analytics_workspace_id = settings.log_analytics_workspace_id
            logger.info("LogsQueryClient initialized")
        except Exception:
            logger.warning(
                "Could not initialize LogsQueryClient "
                "-- observability queries unavailable",
                exc_info=True,
            )
            app.state.logs_client = None
            app.state.log_analytics_workspace_id = ""

        # --- Foundry Agent Service (fail fast) ---
        try:
            foundry_client = DurableAIAgentClient(
                credential=credential,
                project_endpoint=settings.azure_ai_project_endpoint,
                # model_deployment_name needed for constructor validation
                # when no agent_id is provided (Phase 7 sets agent_id)
                model_deployment_name="gpt-4o",
            )
            # DurableAIAgentClient is a lazy client -- construction alone does
            # NOT make a network call, so wrong credentials would pass
            # silently. Force an auth round-trip to genuinely validate
            # connectivity + RBAC.
            async for _ in foundry_client.agents_client.list_agents(limit=1):
                break
            app.state.foundry_client = foundry_client
            logger.info(
                "Foundry client initialized and connectivity validated: %s",
                settings.azure_ai_project_endpoint,
            )
        except Exception:
            logger.error(
                "FATAL: Could not initialize Foundry client",
                exc_info=True,
            )
            raise  # Fail fast -- backend is useless without Foundry

        # --- Foundry Project Client (for evaluations) ---
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import (
                DefaultAzureCredential as SyncDefaultAzureCredential,
            )

            sync_credential = SyncDefaultAzureCredential()
            project_client = AIProjectClient(
                endpoint=settings.azure_ai_project_endpoint,
                credential=sync_credential,
            )
            app.state.project_client = project_client
            logger.info(
                "Foundry project client initialized: %s",
                settings.azure_ai_project_endpoint,
            )
        except Exception:
            logger.warning(
                "Could not initialize Foundry project client "
                "(eval features unavailable)",
                exc_info=True,
            )
            app.state.project_client = None

        # --- Classifier Agent Registration (fail fast) ---
        classifier_agent_id = await ensure_classifier_agent(
            foundry_client=foundry_client,
            stored_agent_id=settings.azure_ai_classifier_agent_id,
        )
        app.state.classifier_agent_id = classifier_agent_id

        # --- ClassifierTools (uses Cosmos for filing) ---
        classifier_tools = ClassifierTools(
            cosmos_manager=cosmos_mgr,
            classification_threshold=settings.classification_threshold,
        )
        app.state.classifier_tools = classifier_tools

        # --- OpenAI transcription client (optional) ---
        openai_client: AsyncAzureOpenAI | None = None
        if settings.azure_openai_endpoint:
            # cognitiveservices scope (NOT ai.azure.com) per RESEARCH pitfall #4
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            openai_client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2025-04-01-preview",
            )
            app.state.openai_client = openai_client
        else:
            app.state.openai_client = None
            logger.warning("AZURE_OPENAI_ENDPOINT not set -- transcription unavailable")

        # --- TranscriptionTools + BlobStorage (optional) ---
        blob_manager: BlobStorageManager | None = None
        if openai_client and settings.blob_storage_url:
            blob_manager = BlobStorageManager(
                account_url=settings.blob_storage_url,
            )
            await blob_manager.initialize()
            app.state.blob_manager = blob_manager

            transcription_tools = TranscriptionTools(
                openai_client=openai_client,
                credential=credential,
                deployment_name=settings.azure_openai_transcription_deployment,
            )
            app.state.transcription_tools = transcription_tools
        else:
            app.state.blob_manager = None
            app.state.transcription_tools = None

        # --- Classifier DurableAIAgentClient (with middleware) ---
        # Separate client from the probe client -- this one has agent_id set
        # and should_cleanup_agent=False to persist the agent across restarts
        classifier_client = DurableAIAgentClient(
            credential=credential,
            project_endpoint=settings.azure_ai_project_endpoint,
            agent_id=classifier_agent_id,
            should_cleanup_agent=False,
            middleware=[
                AuditAgentMiddleware(agent_name="classifier"),
                ToolTimingMiddleware(),
            ],
        )
        app.state.classifier_client = classifier_client

        # Build tool list for request-time use (file_capture always,
        # transcribe_audio only if configured)
        agent_tools = [classifier_tools.file_capture]
        if app.state.transcription_tools:
            agent_tools.append(app.state.transcription_tools.transcribe_audio)
        app.state.classifier_agent_tools = agent_tools

        logger.info(
            "Classifier agent ready: id=%s tools=%d middleware=2",
            classifier_agent_id,
            len(agent_tools),
        )

        # --- Admin Agent Registration (non-fatal) ---
        # Admin Agent is not required for core capture flow. If registration
        # fails, log warning and continue -- Phase 11 will handle the
        # capture-to-admin handoff and can check if admin_client is available.
        try:
            admin_agent_id = await ensure_admin_agent(
                foundry_client=foundry_client,
                stored_agent_id=settings.azure_ai_admin_agent_id,
            )
            app.state.admin_agent_id = admin_agent_id

            # --- AdminTools (uses Cosmos for errand item writes) ---
            admin_tools = AdminTools(cosmos_manager=cosmos_mgr)
            app.state.admin_tools = admin_tools

            # --- Admin DurableAIAgentClient (separate from Classifier) ---
            admin_client = DurableAIAgentClient(
                credential=credential,
                project_endpoint=settings.azure_ai_project_endpoint,
                agent_id=admin_agent_id,
                should_cleanup_agent=False,
                middleware=[
                    AuditAgentMiddleware(agent_name="admin"),
                    ToolTimingMiddleware(),
                ],
            )
            app.state.admin_client = admin_client
            app.state.admin_agent_tools = [
                admin_tools.add_errand_items,
                admin_tools.add_task_items,
                admin_tools.get_routing_context,
                admin_tools.manage_destination,
                admin_tools.manage_affinity_rule,
                admin_tools.query_rules,
            ]

            logger.info(
                "Admin agent ready: id=%s tools=%d",
                admin_agent_id,
                len(app.state.admin_agent_tools),
            )

            # --- Playwright browser for recipe URL fetching ---
            try:
                pw = await async_playwright().start()
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-software-rasterizer",
                    ],
                )
                app.state.playwright = pw
                app.state.browser = browser

                recipe_tools = RecipeTools(
                    browser=browser,
                    spine_repo=getattr(app.state, "spine_repo", None),
                )
                app.state.recipe_tools = recipe_tools
                app.state.admin_agent_tools.append(recipe_tools.fetch_recipe_url)

                logger.info(
                    "Playwright browser started, fetch_recipe_url tool registered "
                    "(admin only)"
                )
            except Exception:
                logger.warning(
                    "Playwright browser launch failed "
                    "-- recipe URL fetching unavailable",
                    exc_info=True,
                )
                app.state.playwright = None
                app.state.browser = None
                app.state.recipe_tools = None

        except Exception:
            logger.warning(
                "Admin agent registration failed -- admin features unavailable",
                exc_info=True,
            )
            app.state.admin_agent_id = None
            app.state.admin_client = None
            app.state.admin_tools = None
            app.state.admin_agent_tools = []
            app.state.playwright = None
            app.state.browser = None
            app.state.recipe_tools = None

        # --- Investigation Agent Registration (non-fatal) ---
        # Investigation Agent is not required for core capture flow.
        # If registration fails, investigation features are simply
        # unavailable (503 on /api/investigate).
        try:
            investigation_agent_id = await ensure_investigation_agent(
                foundry_client=foundry_client,
                stored_agent_id=settings.azure_ai_investigation_agent_id,
            )
            app.state.investigation_agent_id = investigation_agent_id

            # InvestigationTools requires LogsQueryClient
            if app.state.logs_client is not None:
                investigation_tools = InvestigationTools(
                    logs_client=app.state.logs_client,
                    workspace_id=settings.log_analytics_workspace_id,
                    cosmos_manager=app.state.cosmos_manager,
                    classifier_client=app.state.classifier_client,
                    admin_client=getattr(app.state, "admin_client", None),
                    project_client=getattr(app.state, "project_client", None),
                )
                app.state.investigation_tools_instance = investigation_tools

                investigation_client = DurableAIAgentClient(
                    credential=credential,
                    project_endpoint=settings.azure_ai_project_endpoint,
                    agent_id=investigation_agent_id,
                    should_cleanup_agent=False,
                    middleware=[
                        AuditAgentMiddleware(agent_name="investigation"),
                        ToolTimingMiddleware(),
                    ],
                )
                app.state.investigation_client = investigation_client
                app.state.investigation_tools = [
                    investigation_tools.trace_lifecycle,
                    investigation_tools.recent_errors,
                    investigation_tools.system_health,
                    investigation_tools.usage_patterns,
                    investigation_tools.query_feedback_signals,
                    investigation_tools.promote_to_golden_dataset,
                    investigation_tools.run_classifier_eval,
                    investigation_tools.run_admin_eval,
                    investigation_tools.get_eval_results,
                ]
                app.state.investigation_rate_limiter = SoftRateLimiter()

                logger.info(
                    "Investigation agent ready: id=%s tools=%d",
                    investigation_agent_id,
                    len(app.state.investigation_tools),
                )
            else:
                logger.warning(
                    "Investigation agent registered but LogsQueryClient "
                    "unavailable -- investigation tools disabled"
                )
                app.state.investigation_client = None
                app.state.investigation_tools = []
                app.state.investigation_rate_limiter = None
        except Exception:
            logger.warning(
                "Investigation agent registration failed -- investigation unavailable",
                exc_info=True,
            )
            app.state.investigation_agent_id = None
            app.state.investigation_client = None
            app.state.investigation_tools = []
            app.state.investigation_rate_limiter = None

        # --- Background task tracking ---
        # Strong references prevent GC of fire-and-forget tasks.
        # Tasks self-remove via add_done_callback when complete.
        app.state.background_tasks: set = set()

        # --- In-flight processing guard ---
        # Prevents duplicate Admin Agent processing when polls overlap.
        app.state.admin_processing_ids: set = set()

        app.state.settings = settings

        # --- Spine wiring (non-fatal on component failures) ---
        spine_evaluator_task, spine_liveness_tasks = await _wire_spine(app, settings)

        # Backfill spine_repo on RecipeTools — it was created before spine
        # wiring so its _spine_repo is None at init time.
        if getattr(app.state, "recipe_tools", None) and app.state.spine_repo:
            app.state.recipe_tools._spine_repo = app.state.spine_repo

        # --- Agent warm-up background task ---
        warmup_task = None
        if settings.agent_warmup_enabled:
            warmup_clients: list = [("classifier", classifier_client)]
            if app.state.admin_client is not None:
                warmup_clients.append(("admin", app.state.admin_client))
            if getattr(app.state, "investigation_client", None) is not None:
                warmup_clients.append(("investigation", app.state.investigation_client))

            # Factory functions for self-healing: recreate agent clients on
            # consecutive warmup failures without manual Container App restart.
            def _make_classifier_client() -> DurableAIAgentClient:
                return DurableAIAgentClient(
                    credential=credential,
                    project_endpoint=settings.azure_ai_project_endpoint,
                    agent_id=classifier_agent_id,
                    should_cleanup_agent=False,
                    middleware=[
                        AuditAgentMiddleware(agent_name="classifier"),
                        ToolTimingMiddleware(),
                    ],
                )

            warmup_factories: dict[str, Callable[[], DurableAIAgentClient]] = {
                "classifier": _make_classifier_client,
            }
            if app.state.admin_client is not None:

                def _make_admin_client() -> DurableAIAgentClient:
                    return DurableAIAgentClient(
                        credential=credential,
                        project_endpoint=settings.azure_ai_project_endpoint,
                        agent_id=app.state.admin_agent_id,
                        should_cleanup_agent=False,
                        middleware=[
                            AuditAgentMiddleware(agent_name="admin"),
                            ToolTimingMiddleware(),
                        ],
                    )

                warmup_factories["admin"] = _make_admin_client
            if getattr(app.state, "investigation_client", None) is not None:

                def _make_investigation_client() -> DurableAIAgentClient:
                    return DurableAIAgentClient(
                        credential=credential,
                        project_endpoint=settings.azure_ai_project_endpoint,
                        agent_id=app.state.investigation_agent_id,
                        should_cleanup_agent=False,
                        middleware=[
                            AuditAgentMiddleware(agent_name="investigation"),
                            ToolTimingMiddleware(),
                        ],
                    )

                warmup_factories["investigation"] = _make_investigation_client

            def _on_recreate(name: str, new_client: DurableAIAgentClient) -> None:
                """Update app.state with the recreated client."""
                attr = f"{name}_client"
                setattr(app.state, attr, new_client)
                logger.info("app.state.%s replaced by warmup self-heal", attr)

            warmup_task = asyncio.create_task(
                agent_warmup_loop(
                    clients=warmup_clients,
                    interval_seconds=settings.agent_warmup_interval_minutes * 60,
                    client_factories=warmup_factories,
                    on_recreate=_on_recreate,
                )
            )
            logger.info(
                "Agent warmup started: interval=%dm agents=%d",
                settings.agent_warmup_interval_minutes,
                len(warmup_clients),
            )

        yield

        # Cleanup in reverse order
        if warmup_task is not None:
            warmup_task.cancel()

        # Cancel spine background tasks
        all_spine_tasks = [spine_evaluator_task, *spine_liveness_tasks]
        for task in all_spine_tasks:
            if task is not None:
                task.cancel()
        for task in all_spine_tasks:
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        if getattr(app.state, "browser", None) is not None:
            await app.state.browser.close()
        if getattr(app.state, "playwright", None) is not None:
            await app.state.playwright.stop()

        if getattr(app.state, "blob_manager", None) is not None:
            await app.state.blob_manager.close()

        if getattr(app.state, "openai_client", None) is not None:
            await app.state.openai_client.close()

        if getattr(app.state, "logs_client", None) is not None:
            await close_logs_client(app.state.logs_client)

        if getattr(app.state, "cosmos_manager", None) is not None:
            await app.state.cosmos_manager.close()

    finally:
        await credential.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_settings = get_settings()
_docs_url = "/docs" if _settings.environment == "development" else None
_openapi_url = "/openapi.json" if _settings.environment == "development" else None
app = FastAPI(
    title="Second Brain API",
    lifespan=lifespan,
    docs_url=_docs_url,
    openapi_url=_openapi_url,
)

# Middleware ordering (load-bearing): `add_middleware` PREPENDS to the
# internal stack, so the LAST-registered middleware ends up at
# `app.user_middleware[0]` — the OUTERMOST layer, which runs FIRST on
# the inbound path. APIKeyMiddleware must therefore be registered LAST
# so unauthenticated requests are 401'd before SpineWorkloadMiddleware
# observes them (otherwise unauth traffic pollutes the backend_api
# workload dataset).
#
# Spine workload middleware: reads repo from app.state.spine_repo at
# dispatch time (set by lifespan). No-op when spine wiring was skipped.
app.add_middleware(SpineWorkloadMiddleware)

# API key auth middleware -- reads app.state.api_key lazily (set by lifespan)
app.add_middleware(APIKeyMiddleware)

# Include routers
app.include_router(health_router)
app.include_router(inbox_router)
app.include_router(capture_router)
app.include_router(errands_router)
app.include_router(tasks_router)
app.include_router(telemetry_router)
app.include_router(investigate_router)
app.include_router(feedback_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8003)
