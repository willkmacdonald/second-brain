# Phase 6: Foundry Infrastructure - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate the backend from AG-UI/HandoffBuilder/Swarm to Azure AI Foundry Agent Service. Establish Foundry project connectivity, RBAC, Application Insights, delete all old orchestration code, swap to async credentials, and confirm the deployed backend connects to Foundry. No new agent behavior — just the plumbing swap.

</domain>

<decisions>
## Implementation Decisions

### Cleanup scope
- Hard delete all old code: HandoffBuilder, AGUIWorkflowAdapter, Orchestrator agent, Perception Agent, Whisper code
- Git history is sufficient — no archive branch or tag needed
- Delete old test files alongside the code they test
- Remove old SDK packages (ag-ui, swarm, etc.) from requirements immediately — clean break
- Remove old env vars from .env, .env.example, and config.py alongside code deletion
- Leave Classifier agent code intact — Phase 7 refactors it for Foundry registration
- Remove old endpoints entirely (POST /api/ag-ui, POST /api/voice-capture) — no stubs
- The split is clean: Cosmos DB layer, auth middleware, and shared utilities are not entangled with old agent code

### Special handling: main.py
- main.py wires up old endpoints and workflow — needs careful surgery to remove old routing while keeping FastAPI app running
- After cleanup, main.py should be a clean FastAPI shell with Cosmos DB, config, health endpoint, and Foundry client initialization

### Special handling: config.py
- Strip old AG-UI/Whisper env vars
- Add new Foundry vars: AZURE_AI_PROJECT_ENDPOINT, AZURE_AI_CLASSIFIER_AGENT_ID, APPLICATIONINSIGHTS_CONNECTION_STRING
- Non-secret config (agent IDs, endpoints) in .env
- Secrets (connection strings, keys) in Azure Key Vault (shared-services-kv) — KV integration already exists from v1
- Only add env vars that Phase 6 needs — specialist agent IDs added in Phase 10

### Dev workflow
- No localhost backend — backend runs only in Azure Container Apps
- Deploy to wkmsharedservicesacr via existing CI/CD pipeline (merge to main triggers deploy)
- Backend requires Foundry connection at startup — fail fast if credentials are wrong
- Startup initialization: AzureAIAgentClient created in FastAPI lifespan event using azure.identity.aio.DefaultAzureCredential
- Azure CLI auth already set up — no setup docs needed for local credential chain
- Add GET /health endpoint that confirms Foundry client connectivity — returns connection status
- Mobile app (Expo) development paused during Phases 6-8 while backend is being rebuilt
- Validation via pytest integration tests that hit the deployed Container App + health endpoint

### Validation approach
- ruff check for unused imports + dead references after cleanup
- Backend starts cleanly in Container Apps (no import errors)
- GET /health returns Foundry connectivity status from the deployed container
- pytest integration tests confirm Foundry auth succeeds against deployed backend
- Use same CI/CD pipeline from Phase 4.1 — merge to main, deploy, test against Azure

### Claude's Discretion
- Exact order of file deletions (as long as everything listed gets deleted)
- Application Insights integration details (how to wire telemetry to Foundry project)
- Async credential implementation details (lifecycle management in lifespan)
- Health endpoint response format

</decisions>

<specifics>
## Specific Ideas

- Container registry: wkmsharedservicesacr
- Key Vault: shared-services-kv (already integrated from v1)
- Dev cycle: edit locally → push to main → CI/CD deploys to Container Apps → test against deployed backend
- Phase 4.1 CI/CD pipeline is the deployment mechanism — no new pipeline needed
- "No local backend" is a firm preference — all testing against Azure-hosted container

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-foundry-infrastructure*
*Context gathered: 2026-02-26*
