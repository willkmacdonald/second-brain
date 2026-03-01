---
phase: 06-foundry-infrastructure
plan: 03
subsystem: infra
tags: [rbac, azure-ad, application-insights, container-apps, integration-testing, pytest]

# Dependency graph
requires:
  - phase: 06-foundry-infrastructure
    plan: 02
    provides: "AzureAIAgentClient with probe call, enhanced health endpoint, config.py with Foundry fields"
provides:
  - "Three RBAC assignments verified (developer, Container App MI, Foundry project MI)"
  - "Application Insights connected to Foundry project for tracing"
  - "Deployed backend reporting foundry: connected from Container App"
  - "Updated test fixtures matching new Foundry config shape"
  - "Pytest integration test for deployed health endpoint validation"
affects: [07-classifier-agent, 09-observability]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Integration test pattern: env-var-gated pytest with @pytest.mark.integration for deployed endpoint validation"
    - "RBAC triple: developer Azure AI User + Container App MI Azure AI User + Foundry project MI Cognitive Services User"

key-files:
  created:
    - "backend/tests/test_deployed_health.py"
  modified:
    - "backend/tests/conftest.py"
    - "backend/tests/test_health.py"
    - "backend/pyproject.toml"

key-decisions:
  - "Register custom 'integration' pytest marker in pyproject.toml to separate deployed tests from unit tests"
  - "Use httpx for deployed health check (already in dev dependencies, no new deps)"
  - "Application Insights connected to Foundry project via REST API (portal Tracing tab)"

patterns-established:
  - "Deployed endpoint testing: SECOND_BRAIN_URL + SECOND_BRAIN_API_KEY env vars gate integration tests with pytest.mark.skipif"

requirements-completed: [INFRA-12, INFRA-10, INFRA-11]

# Metrics
duration: 5min
completed: 2026-02-27
---

# Phase 6 Plan 03: RBAC + AppInsights + Deployment Validation Summary

**Three RBAC assignments verified, Application Insights connected, and deployed Container App returns foundry: connected -- validated by pytest integration test**

## Performance

- **Duration:** ~5 min (code tasks) + human checkpoint for RBAC/deploy/validation
- **Started:** 2026-02-27T01:35:00Z
- **Completed:** 2026-02-27T02:27:00Z
- **Tasks:** 3
- **Files modified:** 4 (conftest.py, test_health.py, test_deployed_health.py, pyproject.toml)

## Accomplishments
- Updated test fixtures to match new Foundry config shape (removed old OpenAI/instrumentation fields, added azure_ai_project_endpoint, azure_ai_classifier_agent_id, applicationinsights_connection_string)
- Rewrote test_health.py to validate {status, foundry, cosmos} response shape with tests for connected, not_configured, and fully connected states
- Created test_deployed_health.py -- env-var-gated pytest integration test that hits deployed Container App /health endpoint
- Three RBAC role assignments configured and verified: developer Azure AI User, Container App MI Azure AI User, Foundry project MI Cognitive Services User
- Application Insights "second-brain-insights" created and connected to Foundry project
- Backend deployed via CI/CD (57s) -- GET /health returns {"status":"ok","foundry":"connected","cosmos":"connected"}
- pytest test_deployed_health.py PASSED against deployed Container App

## Task Commits

Each task was committed atomically:

1. **Task 1: Update test fixtures and health test for new config shape** - `e0eba5b` (test)
2. **Task 2: Create pytest integration test for deployed health endpoint** - `f2e1cab` (test)
3. **Task 3: Configure RBAC + Application Insights + deploy and validate** - human checkpoint (no code commit -- Azure portal and CLI actions)

## Files Created/Modified
- `backend/tests/conftest.py` - Updated settings fixture: removed azure_openai_endpoint, azure_openai_chat_deployment_name, enable_instrumentation, enable_sensitive_data; added azure_ai_project_endpoint, azure_ai_classifier_agent_id, applicationinsights_connection_string
- `backend/tests/test_health.py` - Rewrote to validate {status, foundry, cosmos} response shape with connected/not_configured state tests
- `backend/tests/test_deployed_health.py` - New integration test: env-var-gated, hits deployed /health with Bearer auth, asserts foundry connected and status ok
- `backend/pyproject.toml` - Added custom 'integration' pytest marker

## Decisions Made
- Registered custom `integration` pytest marker in pyproject.toml to cleanly separate deployed endpoint tests from unit tests
- Used httpx for the deployed health check since it was already in dev dependencies
- Application Insights connected via REST API rather than portal UI alone

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - RBAC, Application Insights, and environment variables were configured during the checkpoint task. No further setup needed.

## Next Phase Readiness
- Phase 6 complete: Foundry infrastructure fully operational
- AzureAIAgentClient authenticated and connected from deployed Container App
- Application Insights wired for tracing (will receive telemetry from Phase 7+ agent runs)
- Three RBAC assignments in place for developer, Container App MI, and Foundry project MI
- Ready for Phase 7: Classifier Agent Baseline (register persistent Foundry agent, local @tool functions)

## Self-Check: PASSED

All 4 files confirmed present on disk. Both task commits (e0eba5b, f2e1cab) confirmed in git log. SUMMARY.md exists on disk.

---
*Phase: 06-foundry-infrastructure*
*Completed: 2026-02-27*
