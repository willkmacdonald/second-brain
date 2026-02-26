# Requirements: The Active Second Brain

**Defined:** 2026-02-25
**Core Value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions — with zero organizational effort from the user.

## v2.0 Requirements — Foundry Agent Service Migration

Migrate the backend agent layer from `AzureOpenAIChatClient` + `HandoffBuilder` to `AzureAIAgentClient` (Azure AI Foundry Agent Service). Same features as v1.0, rebuilt on managed infrastructure with persistent agents, server-managed threads, and Application Insights observability.

**Foundry project endpoint:** `https://second-brain-foundry-resource.services.ai.azure.com/api/projects/second-brain`

### Infrastructure

- [ ] **INFRA-10**: AI Foundry project connectivity validated with model deployment accessible from project endpoint
- [ ] **INFRA-11**: Application Insights instance created and connected to the Foundry project
- [ ] **INFRA-12**: RBAC configured: developer Entra ID (Azure AI User on project), Container App managed identity (Azure AI User on project), Foundry project managed identity (Cognitive Services User on OpenAI resource)
- [ ] **INFRA-13**: New environment variables configured in `.env`, `config.py`, and deployed Container App (`AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_CLASSIFIER_AGENT_ID`, `APPLICATIONINSIGHTS_CONNECTION_STRING`)

### Agent Migration

- [ ] **AGNT-01**: Classifier agent registered as a persistent Foundry agent with stable ID visible in AI Foundry portal
- [ ] **AGNT-02**: Classifier agent executes local `@tool` functions (`classify_and_file`, `request_misunderstood`, `mark_as_junk`) through Foundry service with results written to Cosmos DB
- [ ] **AGNT-03**: `AzureAIAgentClient` with `should_cleanup_agent=False` manages agent lifecycle — agent persists across Container App restarts
- [ ] **AGNT-04**: Orchestrator agent eliminated; code-based routing in FastAPI endpoint replaces HandoffBuilder orchestration
- [ ] **AGNT-05**: `transcribe_audio` is a `@tool` callable by the Classifier agent, using `gpt-4o-transcribe` via `AsyncAzureOpenAI` (replaces sync Whisper via Cognitive Services)
- [ ] **AGNT-06**: Agent middleware wired: `AgentMiddleware` for audit logging, `FunctionMiddleware` for tool validation/timing

### Streaming

- [ ] **STRM-01**: `FoundrySSEAdapter` replaces `AGUIWorkflowAdapter`, streaming `AgentResponseUpdate` events to AG-UI SSE format
- [ ] **STRM-02**: Text capture produces same AG-UI events as v1 (`StepStarted`, `StepFinished`, `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED`, `RUN_FINISHED`)
- [ ] **STRM-03**: Voice capture produces same AG-UI events as v1 (Perception step + classification stream)

### HITL Parity

- [ ] **HITL-01**: Low-confidence captures filed as pending with bucket buttons for recategorization (direct Cosmos write, unchanged)
- [ ] **HITL-02**: Misunderstood captures trigger conversational follow-up using fresh Foundry thread (no conversation history contamination)
- [ ] **HITL-03**: Recategorize from inbox detail card works end-to-end (direct Cosmos write, unchanged)

### Observability

- [ ] **OBSV-01**: Application Insights receives traces from Foundry agent runs with per-classification visibility
- [ ] **OBSV-02**: Token usage and cost metrics visible in Foundry portal or Application Insights

### Deployment

- [ ] **DPLY-01**: Migrated backend deployed to Azure Container Apps with all new env vars and dependencies
- [ ] **DPLY-02**: CI/CD pipeline updated for new dependencies (`agent-framework-azure-ai`, `azure-monitor-opentelemetry`)

## v1.0 Requirements (Completed)

### Validated (shipped in v1.0)

- [x] **INFRA-01**: Agent Framework server runs on Azure Container Apps with AG-UI endpoint — Phase 1
- [x] **INFRA-02**: Cosmos DB provisioned with 5 containers partitioned by `/userId` — Phase 1
- [x] **INFRA-04**: OpenTelemetry tracing enabled across all agent handoffs — Phase 1
- [x] **INFRA-05**: API key authentication protects the AG-UI endpoint — Phase 1
- [x] **CAPT-01**: User can type a thought and submit with one tap — Phase 2
- [x] **CAPT-02**: Real-time visual feedback showing agent chain processing — Phase 4
- [x] **CAPT-04**: User sees transcribed text and classification result after voice capture — Phase 5
- [x] **CAPT-05**: Expo app runs on both iOS and Android — Phase 2
- [x] **ORCH-01**: Orchestrator routes to correct specialist agent — Phase 3
- [x] **ORCH-02**: Orchestrator routes text to Classifier — Phase 3
- [x] **ORCH-03**: Orchestrator routes audio to Perception then Classifier — Phase 5
- [x] **ORCH-06**: Orchestrator provides confirmation when agent chain completes — Phase 3
- [x] **CLAS-01**: Classifier classifies into People/Projects/Ideas/Admin — Phase 3
- [x] **CLAS-02**: Classifier assigns confidence score (0.0–1.0) — Phase 3
- [x] **CLAS-03**: Confidence >= 0.6 silently files and confirms — Phase 3
- [x] **CLAS-04**: Confidence < 0.6 triggers clarifying question — Phase 4
- [x] **CLAS-07**: Every capture logged to Inbox with classification details — Phase 3
- [x] **APPX-01**: Main screen shows capture buttons — Phase 2
- [x] **APPX-02**: Inbox view shows recent captures — Phase 4
- [x] **APPX-04**: Conversation view for clarification — Phase 4

### Partially Complete (v1.0)

- [ ] **INFRA-03**: Azure Blob Storage for media uploads — configured, voice working, photo/video deferred
- [ ] **CAPT-03**: Voice recording in Expo app via Whisper — backend working, mobile UAT incomplete

## v3.0+ Requirements (Deferred)

### Connected Agents
- **CONN-01**: `classify_and_file` tool moved to Azure Functions for server-side execution
- **CONN-02**: Orchestrator re-introduced as Connected Agent invoking Classifier as sub-agent

### New Agents
- **ORCH-04**: Orchestrator routes classified Projects/Admin to Action Agent
- **ORCH-05**: Orchestrator routes digest/summary requests to Digest Agent
- **ACTN-01** through **ACTN-04**: Action Agent sharpening
- **PEOP-01** through **PEOP-04**: People CRM
- **DGST-01** through **DGST-06**: Digests and notifications
- **CLAS-05**, **CLAS-06**: Cross-references and duplicate checking

### Features
- **SRCH-01**, **SRCH-02**: Search across all buckets
- **MDIA-01** through **MDIA-03**: Photo/video capture, share sheet
- **APPX-03**: Digest view in mobile app

## Out of Scope

| Feature | Reason |
|---------|--------|
| Connected Agents pattern | Requires moving @tool functions to Azure Functions — v3.0 scope |
| New agent types (Action, Digest, People, Entity Resolution) | Not part of migration milestone |
| Orchestrator agent | Eliminated — code-based routing with single destination agent |
| Mobile app changes | AG-UI SSE interface unchanged; zero mobile code changes needed |
| Multi-user / multi-tenancy | Single-user system for Will only |
| Offline capture | Requires connectivity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-10 | TBD | Pending |
| INFRA-11 | TBD | Pending |
| INFRA-12 | TBD | Pending |
| INFRA-13 | TBD | Pending |
| AGNT-01 | TBD | Pending |
| AGNT-02 | TBD | Pending |
| AGNT-03 | TBD | Pending |
| AGNT-04 | TBD | Pending |
| AGNT-05 | TBD | Pending |
| AGNT-06 | TBD | Pending |
| STRM-01 | TBD | Pending |
| STRM-02 | TBD | Pending |
| STRM-03 | TBD | Pending |
| HITL-01 | TBD | Pending |
| HITL-02 | TBD | Pending |
| HITL-03 | TBD | Pending |
| OBSV-01 | TBD | Pending |
| OBSV-02 | TBD | Pending |
| DPLY-01 | TBD | Pending |
| DPLY-02 | TBD | Pending |

**Coverage:**
- v2.0 requirements: 20 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 20

---
*Requirements defined: 2026-02-25*
*Last updated: 2026-02-25 after v2.0 milestone definition*
