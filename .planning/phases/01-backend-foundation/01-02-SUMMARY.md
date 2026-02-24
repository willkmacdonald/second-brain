---
phase: 01-backend-foundation
plan: 02
subsystem: database
tags: [cosmos-db, pydantic, async, crud-tools, agent-framework]

# Dependency graph
requires:
  - phase: 01-01
    provides: FastAPI server scaffold with AG-UI endpoint, monorepo backend structure
provides:
  - Pydantic document models for all 5 Cosmos DB containers (Inbox, People, Projects, Ideas, Admin)
  - CosmosManager async singleton with lifecycle management and container accessors
  - CosmosCrudTools with create_document, read_document, list_documents @tool functions
  - Echo agent wired with CRUD tools for document operations
  - Mock-based test suite for CRUD operations (7 tests)
affects: [01-03-PLAN, 03-01-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns: [CosmosManager singleton in lifespan, class-based tool binding, mock_cosmos_manager fixture, camelCase Cosmos fields with N815 ignore]

key-files:
  created:
    - backend/src/second_brain/models/documents.py
    - backend/src/second_brain/db/cosmos.py
    - backend/src/second_brain/tools/cosmos_crud.py
    - backend/tests/test_cosmos_crud.py
  modified:
    - backend/src/second_brain/main.py
    - backend/src/second_brain/agents/echo.py
    - backend/tests/conftest.py
    - backend/pyproject.toml

key-decisions:
  - "Agent creation moved to lifespan (from module level) to pass runtime CosmosManager to CRUD tools"
  - "Class-based CosmosCrudTools pattern to bind container references without module-level globals"
  - "Ruff N815 per-file ignore for camelCase Cosmos DB document field names (userId, createdAt, etc.)"
  - "Graceful Cosmos DB fallback in lifespan -- server starts without Cosmos configured"

patterns-established:
  - "CosmosManager singleton initialized in lifespan, stored on app.state"
  - "CosmosCrudTools class binds stateful CosmosManager reference to @tool functions"
  - "mock_cosmos_manager fixture with AsyncMock containers for unit testing"
  - "Agent created in lifespan with runtime dependencies (tools, cosmos_manager)"

requirements-completed: [INFRA-02]

# Metrics
duration: 4min
completed: 2026-02-21
---

# Phase 1 Plan 02: Cosmos DB Data Layer Summary

**Pydantic document models for 5 containers, async CosmosManager singleton, and @tool CRUD functions wired into the echo agent**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-21T21:40:02Z
- **Completed:** 2026-02-21T21:44:15Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Pydantic document models with shared BaseDocument schema and bucket-specific extensions for all 5 containers
- CosmosManager async singleton with initialize/close lifecycle, DefaultAzureCredential auth, and container accessors
- CosmosCrudTools with create_document, read_document, list_documents @tool functions returning strings
- Echo agent updated with CRUD tools and registered via AG-UI endpoint in lifespan
- 7 new CRUD tests plus 3 existing tests all passing (10 total)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Pydantic document models and Cosmos DB singleton client** - `5752fd2` (feat)
2. **Task 2: Create CRUD tools, wire into echo agent, and add tests** - `07f7fe0` (feat)

## Files Created/Modified
- `backend/src/second_brain/models/documents.py` - Pydantic models for all 5 containers with shared BaseDocument
- `backend/src/second_brain/db/cosmos.py` - CosmosManager async singleton with lifecycle and container accessors
- `backend/src/second_brain/tools/cosmos_crud.py` - CosmosCrudTools class with @tool-decorated CRUD functions
- `backend/tests/test_cosmos_crud.py` - 7 tests for CRUD operations with mocked CosmosManager
- `backend/src/second_brain/main.py` - Lifespan updated with CosmosManager init/close and agent creation
- `backend/src/second_brain/agents/echo.py` - Echo agent accepts CosmosManager, registers CRUD tools
- `backend/tests/conftest.py` - Added mock_cosmos_manager fixture
- `backend/pyproject.toml` - Added N815 per-file ignore for document models

## Decisions Made
- Moved agent creation from module level to lifespan. The 01-01 decision to register at module level was based on no runtime dependencies. CRUD tools require the CosmosManager which is only available after lifespan initialization. The AG-UI endpoint is now registered in the lifespan after agent creation.
- Used class-based CosmosCrudTools pattern (from research Open Question 3) to bind CosmosManager references to @tool functions, avoiding module-level globals.
- Added ruff N815 per-file ignore for `documents.py` because Cosmos DB document field names use camelCase to match the JSON schema stored in Cosmos DB (userId, createdAt, rawText, etc.).
- Added graceful fallback for Cosmos DB initialization (same pattern as Key Vault from 01-01) so the server starts even without Cosmos DB configured.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed deprecated datetime.utcnow()**
- **Found during:** Task 2 (running tests)
- **Issue:** `datetime.utcnow()` is deprecated in Python 3.12+ and scheduled for removal. Tests emitted DeprecationWarning.
- **Fix:** Changed to `datetime.now(UTC)` using `from datetime import UTC`
- **Files modified:** `backend/src/second_brain/models/documents.py`
- **Verification:** Tests pass with no deprecation warnings
- **Committed in:** 07f7fe0

**2. [Rule 3 - Blocking] Moved agent creation to lifespan for CRUD tool wiring**
- **Found during:** Task 2 (wiring CRUD tools into echo agent)
- **Issue:** Agent was created at module level (per 01-01 decision) but CRUD tools require runtime CosmosManager from lifespan. Cannot pass cosmos_manager to module-level agent creation.
- **Fix:** Moved agent creation and AG-UI endpoint registration into the lifespan, after CosmosManager initialization
- **Files modified:** `backend/src/second_brain/main.py`
- **Verification:** Import succeeds, all tests pass
- **Committed in:** 07f7fe0

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correctness. No scope creep. Agent-in-lifespan pattern is the natural evolution when agents need runtime dependencies.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required

**External services require manual configuration.** The plan's `user_setup` section details:
- **Azure Cosmos DB:** Create a Cosmos DB for NoSQL account (serverless capacity mode), create database named 'second-brain', create 5 containers (Inbox, People, Projects, Ideas, Admin) each with partition key /userId
- Set `COSMOS_ENDPOINT` in `.env` (from Azure Portal -> Cosmos DB account -> Keys -> URI)

See `backend/.env.example` for all required environment variables.

## Next Phase Readiness
- Cosmos DB data layer complete with models, client, and CRUD tools
- Echo agent has document creation/read/list capabilities via @tool functions
- Ready for Plan 01-03 (API key auth middleware and OpenTelemetry configuration)
- mock_cosmos_manager fixture available for all future tests needing Cosmos DB mocks

## Self-Check: PASSED

All 8 key files verified present. Both task commits (5752fd2, 07f7fe0) verified in git log.

---
*Phase: 01-backend-foundation*
*Completed: 2026-02-21*
