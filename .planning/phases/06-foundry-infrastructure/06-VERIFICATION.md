---
phase: 06-foundry-infrastructure
verified: 2026-02-27T03:15:00Z
status: human_needed
score: 11/14 must-haves verified (3 require human confirmation of deployed state)
re_verification: false
human_verification:
  - test: "curl -H 'Authorization: Bearer <api-key>' https://<container-app-url>/health and confirm JSON response"
    expected: '{"status":"ok","foundry":"connected","cosmos":"connected"}'
    why_human: "RBAC assignments and deployed Foundry connectivity cannot be verified programmatically from local machine"
  - test: "Confirm three RBAC role assignments in Azure portal or via az role assignment list on the Foundry resource scope"
    expected: "Developer Entra ID = Azure AI User, Container App MI = Azure AI User, Foundry project MI = Cognitive Services User"
    why_human: "RBAC state lives in Azure AD and cannot be inspected from the codebase"
  - test: "Open Azure Foundry portal > project > Tracing tab and confirm Application Insights 'second-brain-insights' is connected"
    expected: "Application Insights instance shown as connected and accepting telemetry"
    why_human: "AppInsights connection state lives in the Foundry project portal and cannot be inferred from code"
---

# Phase 6: Foundry Infrastructure Verification Report

**Phase Goal:** The Foundry project endpoint is reachable, RBAC allows authentication from both local dev and Container App, Application Insights is connected, dead orchestration code is deleted, and the codebase compiles cleanly against the new SDK
**Verified:** 2026-02-27T03:15:00Z
**Status:** human_needed (all automated checks pass; 3 deployed/RBAC items need confirmation)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All 7 old agent/workflow files deleted (orchestrator, perception, echo, workflow, transcription, test_agui_endpoint, test_integration) | VERIFIED | `ls` returns "No such file or directory" for all 7 paths |
| 2 | No AG-UI endpoint functions, request models, or imports anywhere in main.py or source | VERIFIED | grep finds zero matches for AGUIRunRequest, RespondRequest, ag_ui_endpoint, respond_to_hitl, follow_up_misunderstood, voice_capture |
| 3 | main.py is a clean FastAPI shell (~142 lines) with lifespan (Key Vault + Cosmos + Foundry), health router, inbox router, and middleware | VERIFIED | File read confirms structure: no dead code, correct lifespan pattern |
| 4 | ruff check passes on all Phase 6 modified files | VERIFIED | `uv run ruff check src/second_brain/main.py config.py api/health.py tests/conftest.py test_health.py test_deployed_health.py` — all checks passed |
| 5 | pyproject.toml depends on agent-framework-azure-ai and azure-monitor-opentelemetry; no old AG-UI/orchestrations packages | VERIFIED | pyproject.toml line 8: `agent-framework-azure-ai`; line 15: `azure-monitor-opentelemetry>=1.8.6`; comment-only mention of old packages (not a dependency) |
| 6 | config.py has azure_ai_project_endpoint, azure_ai_classifier_agent_id, applicationinsights_connection_string; old OpenAI/Whisper/OTel fields removed | VERIFIED | config.py lines 12-16 confirm new fields; grep finds zero matches for old fields |
| 7 | main.py calls configure_azure_monitor() after load_dotenv() and before other imports | VERIFIED | main.py lines 11-15: import then call in correct order with noqa E402 |
| 8 | main.py creates AzureAIAgentClient in lifespan with agents_client.list_agents(limit=1) probe call (fail fast) | VERIFIED | main.py lines 84-111: full fail-fast pattern with probe and `raise` on failure |
| 9 | GET /health returns {status, foundry, cosmos} JSON with foundry connectivity status | VERIFIED | health.py returns dict with all three keys; test_health.py validates all states |
| 10 | Test suite (41 tests) passes with updated conftest.py and test_health.py fixtures | VERIFIED | `uv run python3 -m pytest tests/ --ignore=tests/test_deployed_health.py` — 41 passed |
| 11 | test_deployed_health.py exists and skips gracefully when env vars not set | VERIFIED | pytest shows 1 SKIPPED with correct skip reason |
| 12 | RBAC: developer Entra ID has Azure AI User role on Foundry resource | HUMAN NEEDED | 06-03-SUMMARY claims validated; cannot verify from codebase |
| 13 | RBAC: Container App managed identity has Azure AI User role on Foundry resource; Foundry project MI has Cognitive Services User role | HUMAN NEEDED | 06-03-SUMMARY claims validated; cannot verify from codebase |
| 14 | Deployed Container App GET /health returns foundry: connected | HUMAN NEEDED | 06-03-SUMMARY claims `{"status":"ok","foundry":"connected","cosmos":"connected"}` returned; cannot verify from codebase |

**Score:** 11/14 automated truths verified; 3 require human confirmation of deployed/Azure state

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/src/second_brain/main.py` | Clean FastAPI shell without AG-UI endpoints or old agent imports | VERIFIED | 142 lines; configure_azure_monitor(), AzureAIAgentClient in lifespan, health + inbox routers |
| `backend/src/second_brain/config.py` | Settings class with Foundry and AppInsights env vars | VERIFIED | azure_ai_project_endpoint, azure_ai_classifier_agent_id, applicationinsights_connection_string present; old fields absent |
| `backend/src/second_brain/api/health.py` | Health endpoint returning foundry + cosmos connectivity status | VERIFIED | Returns {status, foundry, cosmos} with correct logic |
| `backend/pyproject.toml` | Updated dependencies with Foundry SDK and observability packages | VERIFIED | agent-framework-azure-ai, azure-monitor-opentelemetry, azure-core-tracing-opentelemetry present; old AG-UI packages absent |
| `backend/.env.example` | Documentation of all required environment variables | VERIFIED | AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_CLASSIFIER_AGENT_ID, APPLICATIONINSIGHTS_CONNECTION_STRING documented |
| `backend/tests/conftest.py` | Test fixtures without AG-UI mock classes or AG-UI event imports | VERIFIED | No MockAgentFrameworkAgent, no ag_ui imports; settings fixture uses new Foundry fields |
| `backend/tests/test_health.py` | Health endpoint test validating {status, foundry, cosmos} response shape | VERIFIED | 4 test cases covering degraded, ok, fully connected, and app_with_mocks states |
| `backend/tests/test_deployed_health.py` | Pytest integration test that hits deployed Container App /health endpoint | VERIFIED | env-var-gated, skips cleanly, httpx call with Bearer auth, asserts foundry: connected |
| `backend/uv.lock` | Regenerated with new dependency tree | VERIFIED | File exists; regenerated in Plan 02 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/src/second_brain/main.py` | `backend/src/second_brain/api/health.py` | `include_router(health_router)` | WIRED | Line 135 confirmed |
| `backend/src/second_brain/main.py` | `backend/src/second_brain/api/inbox.py` | `include_router(inbox_router)` | WIRED | Line 136 confirmed |
| `backend/src/second_brain/main.py` | `azure.monitor.opentelemetry` | `configure_azure_monitor()` call at module level | WIRED | Lines 11 and 15 confirmed |
| `backend/src/second_brain/main.py` | `agent_framework.azure.AzureAIAgentClient` | Client creation in lifespan stored on app.state.foundry_client | WIRED | Lines 17, 85, 100 confirmed |
| `backend/src/second_brain/api/health.py` | `app.state.foundry_client` | `request.app.state` access in health endpoint | WIRED | Lines 12-14 confirmed |
| `Deployed Container App` | `Foundry project endpoint` | AzureAIAgentClient with managed identity credential | HUMAN NEEDED | RBAC must be verified in Azure portal |
| `Foundry project` | `Application Insights` | Connected in Foundry portal Tracing tab | HUMAN NEEDED | Portal state, not verifiable from code |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-10 | 06-02, 06-03 | AI Foundry project connectivity validated with model deployment accessible from project endpoint | VERIFIED (code) + HUMAN NEEDED (deployed) | AzureAIAgentClient with probe call wired in lifespan; deployed validation in 06-03-SUMMARY |
| INFRA-11 | 06-02, 06-03 | Application Insights instance created and connected to the Foundry project | VERIFIED (code) + HUMAN NEEDED (portal) | configure_azure_monitor() wired; APPLICATIONINSIGHTS_CONNECTION_STRING in config; portal connection in 06-03-SUMMARY |
| INFRA-12 | 06-03 | RBAC configured: developer Entra ID (Azure AI User), Container App MI (Azure AI User), Foundry project MI (Cognitive Services User) | HUMAN NEEDED | 06-03-SUMMARY claims all three verified; not verifiable from codebase |
| INFRA-13 | 06-02 | New environment variables configured in .env, config.py, and deployed Container App | VERIFIED (code) | config.py and .env.example updated; deployed env vars in 06-03-SUMMARY |
| INFRA-14 | 06-01 | Old orchestration code deleted: HandoffBuilder, AGUIWorkflowAdapter, Orchestrator agent, Perception Agent, Whisper integration | VERIFIED | All 7 files absent; no dead references in remaining source |
| AGNT-04 | 06-01 | Orchestrator agent eliminated; code-based routing in FastAPI endpoint replaces HandoffBuilder orchestration | VERIFIED | workflow.py, orchestrator.py deleted; main.py has no HandoffBuilder or AG-UI routing logic |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/second_brain/agents/classifier.py` | 8 | `AzureOpenAIChatClient` import | INFO | This file is explicitly preserved for Phase 7 reuse (per 06-01 PLAN locked decisions). Not dead code introduced by Phase 6 — it pre-exists Phase 6. Will be replaced when Phase 7 migrates classifier to AzureAIAgentClient. |
| `backend/src/second_brain/agents/classifier.py` | 95 | E501 line too long | INFO | Pre-existing ruff error, explicitly deferred in 06-01 and 06-02 SUMMARYs. Not introduced by Phase 6. |
| `backend/src/second_brain/tools/classification.py` | 125, 190 | E501 line too long (2 errors) | INFO | Pre-existing ruff errors, explicitly deferred. Not introduced by Phase 6. |
| `backend/tests/test_classification.py` | 209 | E501 line too long | INFO | Pre-existing ruff error, explicitly deferred. Not introduced by Phase 6. |

No blocker anti-patterns found. All Phase 6 modified files pass ruff check cleanly.

---

## Human Verification Required

### 1. Deployed Container App health check

**Test:** From a machine with API key access, run:
```bash
curl -H "Authorization: Bearer <api-key>" https://<container-app-url>/health
```
**Expected:** `{"status":"ok","foundry":"connected","cosmos":"connected"}`
**Why human:** Foundry connectivity depends on RBAC assignments and deployed env vars that cannot be inspected from the local codebase. The 06-03-SUMMARY documents this was validated (`pytest test_deployed_health.py PASSED`), but this verifier cannot confirm the current deployed state.

### 2. RBAC role assignments

**Test:** Run:
```bash
az role assignment list --scope "/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource>" --output table
```
**Expected:** Three entries: developer Entra ID with "Azure AI User", Container App managed identity with "Azure AI User", Foundry project MI with "Cognitive Services User" (on OpenAI resource scope)
**Why human:** RBAC state lives in Azure AD, not in the codebase. The 06-03-SUMMARY claims all three were configured and verified, but this verifier cannot confirm current Azure AD state.

### 3. Application Insights connected to Foundry project

**Test:** Open Azure Foundry portal > your project > Tracing tab
**Expected:** Application Insights instance "second-brain-insights" shown as connected and telemetry flowing
**Why human:** Portal connection state cannot be inferred from the APPLICATIONINSIGHTS_CONNECTION_STRING in config.py alone. The 06-03-SUMMARY claims this was connected, but this verifier cannot confirm current portal state.

---

## Phase Goal Assessment

**Phase Goal:** "The Foundry project endpoint is reachable, RBAC allows authentication from both local dev and Container App, Application Insights is connected, dead orchestration code is deleted, and the codebase compiles cleanly against the new SDK"

**Automated verifiable claims:**
- Dead orchestration code is deleted: CONFIRMED — all 7 files absent, no dead references
- Codebase compiles cleanly against the new SDK: CONFIRMED — import OK, main.py imports successfully, 41 tests pass
- Foundry SDK (AzureAIAgentClient) and AppInsights (configure_azure_monitor) are properly wired in code: CONFIRMED
- config.py and .env.example document all required env vars: CONFIRMED

**Human-dependent claims:**
- Foundry project endpoint is reachable: Cannot verify from code (requires deployed state check)
- RBAC allows authentication from local dev and Container App: Cannot verify from code
- Application Insights is connected: Cannot verify from code (portal state)

The 06-03-SUMMARY documents all three human-dependent claims were completed and validated (pytest integration test passed, RBAC verified via az CLI, AppInsights connected in portal). The automated code work is complete and correct.

---

_Verified: 2026-02-27T03:15:00Z_
_Verifier: Claude (gsd-verifier)_
