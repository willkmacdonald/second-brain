---
phase: 01-backend-foundation
plan: 01
subsystem: infra
tags: [fastapi, ag-ui, agent-framework, azure-openai, opentelemetry, pydantic-settings, uv]

# Dependency graph
requires: []
provides:
  - FastAPI server scaffold with AG-UI endpoint at POST /api/ag-ui
  - Echo agent using AzureOpenAIChatClient with DefaultAzureCredential
  - Health check endpoint at GET /health
  - Pydantic-settings configuration loading from .env
  - OpenTelemetry tracing via configure_otel_providers()
  - API key fetch from Azure Key Vault in lifespan
  - Monorepo backend structure with domain-based packages
affects: [01-02-PLAN, 01-03-PLAN, 02-01-PLAN]

# Tech tracking
tech-stack:
  added: [agent-framework-ag-ui, agent-framework-core, azure-identity, azure-keyvault-secrets, azure-cosmos, pydantic-settings, python-dotenv, ruff, pytest, pytest-asyncio, httpx, agent-framework-devui]
  patterns: [src-layout packaging, load_dotenv before imports, module-level agent creation, lifespan for async resources, mock AG-UI agent for tests]

key-files:
  created:
    - backend/pyproject.toml
    - backend/src/second_brain/main.py
    - backend/src/second_brain/config.py
    - backend/src/second_brain/agents/echo.py
    - backend/src/second_brain/api/health.py
    - backend/tests/test_health.py
    - backend/tests/test_agui_endpoint.py
    - backend/.env.example
    - .gitignore
  modified: []

key-decisions:
  - "AzureOpenAIChatClient uses sync DefaultAzureCredential (not async) since the client expects TokenCredential"
  - "Agent and AG-UI endpoint registered at module level (not in lifespan) following research Pattern 1"
  - "Key Vault fetch in lifespan with graceful fallback if unavailable"
  - "Ruff per-file ignore for main.py (E402, I001) to support load_dotenv-before-imports pattern"

patterns-established:
  - "load_dotenv() then configure_otel_providers() at top of main.py before other imports"
  - "Module-level agent creation with add_agent_framework_fastapi_endpoint"
  - "MockAgentFrameworkAgent pattern for testing AG-UI endpoints without LLM calls"
  - "Pydantic BaseSettings with lru_cache for get_settings()"

requirements-completed: [INFRA-01, INFRA-04]

# Metrics
duration: 5min
completed: 2026-02-21
---

# Phase 1 Plan 01: Project Scaffold + AG-UI Server Summary

**FastAPI server scaffold with AG-UI endpoint streaming SSE events from an echo agent, plus OpenTelemetry tracing via Agent Framework**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-21T21:32:01Z
- **Completed:** 2026-02-21T21:36:49Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- Monorepo backend structure with domain-based packages (api, agents, db, models, tools)
- AG-UI endpoint at POST /api/ag-ui accepting requests and streaming SSE responses
- Echo agent using AzureOpenAIChatClient with DefaultAzureCredential
- Health check endpoint returning 200 with {"status": "ok"}
- OpenTelemetry configured via configure_otel_providers()
- API key fetched from Azure Key Vault in FastAPI lifespan (with graceful fallback)
- All 3 tests passing, ruff lint and format clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Create project scaffold with pyproject.toml and directory structure** - `a3a16f9` (feat)
2. **Task 2: Create FastAPI app with echo agent, AG-UI endpoint, and OpenTelemetry** - `b899207` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Project definition with uv, dependency groups (core, dev, test), ruff + pytest config
- `backend/.python-version` - Python 3.12
- `backend/.env.example` - Environment variable template for Azure services
- `backend/src/second_brain/__init__.py` - Package init
- `backend/src/second_brain/config.py` - Pydantic-settings configuration with lru_cache
- `backend/src/second_brain/main.py` - FastAPI app with AG-UI endpoint, lifespan, and OpenTelemetry
- `backend/src/second_brain/agents/echo.py` - Echo agent using AzureOpenAIChatClient
- `backend/src/second_brain/api/__init__.py` - API package init
- `backend/src/second_brain/api/health.py` - Health check endpoint router
- `backend/src/second_brain/agents/__init__.py` - Agents package init
- `backend/src/second_brain/db/__init__.py` - Database package init (placeholder)
- `backend/src/second_brain/models/__init__.py` - Models package init (placeholder)
- `backend/src/second_brain/tools/__init__.py` - Tools package init (placeholder)
- `backend/tests/__init__.py` - Tests package init
- `backend/tests/conftest.py` - Shared test fixtures with test-safe Settings
- `backend/tests/test_health.py` - Health endpoint test
- `backend/tests/test_agui_endpoint.py` - AG-UI endpoint SSE streaming tests
- `.gitignore` - Python/venv/IDE/OS ignore patterns

## Decisions Made
- Used sync `DefaultAzureCredential` for `AzureOpenAIChatClient` because the client's `credential` parameter expects `TokenCredential` (sync), not `AsyncTokenCredential`. Async credential used only for Key Vault operations in the lifespan.
- Registered the agent and AG-UI endpoint at module level (not inside lifespan) following the research Pattern 1 example. This is simpler and avoids complications with `add_agent_framework_fastapi_endpoint` requiring the app to not yet be running.
- Added ruff per-file ignore for `main.py` (`E402`, `I001`) to support the required pattern of calling `load_dotenv()` and `configure_otel_providers()` before other imports.
- Key Vault fetch wrapped in try/except with graceful fallback -- server starts even without Key Vault access (enables local development without Azure setup).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed credential type mismatch for AzureOpenAIChatClient**
- **Found during:** Task 2 (echo agent creation)
- **Issue:** Plan specified `azure.identity.aio.DefaultAzureCredential` (async) for the chat client, but `AzureOpenAIChatClient` accepts `TokenCredential` (sync `azure.core.credentials`)
- **Fix:** Used sync `DefaultAzureCredential` from `azure.identity` for the chat client; async credential used only for Key Vault in lifespan
- **Files modified:** `backend/src/second_brain/agents/echo.py`
- **Verification:** Agent creation succeeds; imports resolve correctly
- **Committed in:** b899207

**2. [Rule 2 - Missing Critical] Added graceful Key Vault fallback**
- **Found during:** Task 2 (main.py lifespan)
- **Issue:** Plan shows Key Vault fetch without error handling. Without Key Vault configured, server would crash on startup, blocking all local development
- **Fix:** Wrapped Key Vault fetch in try/except; logs warning and sets `api_key = None` if unavailable
- **Files modified:** `backend/src/second_brain/main.py`
- **Verification:** Server starts without Key Vault; warning logged
- **Committed in:** b899207

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required

**External services require manual configuration.** The plan's `user_setup` section details:
- **Azure OpenAI:** Deploy a gpt-4o model and set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`
- **Azure CLI:** Run `az login` for DefaultAzureCredential local dev auth
- **Azure Key Vault:** Create a vault, add an `api-key` secret, grant yourself Key Vault Secrets User role, set `KEY_VAULT_URL`

See `backend/.env.example` for all required environment variables.

## Next Phase Readiness
- Backend scaffold complete with all directory placeholders for Plan 01-02 (Cosmos DB data layer)
- AG-UI endpoint proven working with mock tests; ready for real agent integration
- Configuration system ready to add new settings (cosmos_endpoint already defined)
- The `db/`, `models/`, and `tools/` packages are empty placeholders ready for Plan 01-02

## Self-Check: PASSED

All 11 key files verified present. Both task commits (a3a16f9, b899207) verified in git log.

---
*Phase: 01-backend-foundation*
*Completed: 2026-02-21*
