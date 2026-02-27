# Requirements: The Active Second Brain

**Defined:** 2026-02-26
**Core Value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and proactively follows up — with zero organizational effort from the user.

## v2.0 Requirements — Proactive Second Brain

Transform the Second Brain from a filing cabinet into a proactive thinking partner. Rebuild on Foundry Agent Service with four specialist agents that follow up over time via push notifications.

**Foundry project endpoint:** `https://second-brain-foundry-resource.services.ai.azure.com/api/projects/second-brain`

### Infrastructure

- [x] **INFRA-10**: AI Foundry project connectivity validated with model deployment accessible from project endpoint
- [x] **INFRA-11**: Application Insights instance created and connected to the Foundry project
- [x] **INFRA-12**: RBAC configured: developer Entra ID (Azure AI User on project), Container App managed identity (Azure AI User on project), Foundry project managed identity (Cognitive Services User on OpenAI resource)
- [x] **INFRA-13**: New environment variables configured in `.env`, `config.py`, and deployed Container App (`AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_CLASSIFIER_AGENT_ID`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, specialist agent IDs)
- [x] **INFRA-14**: Old orchestration code deleted: HandoffBuilder, AGUIWorkflowAdapter, Orchestrator agent, Perception Agent, Whisper integration

### Agent Migration

- [x] **AGNT-01**: Classifier agent registered as a persistent Foundry agent with stable ID visible in AI Foundry portal
- [x] **AGNT-02**: Classifier agent executes in-process Python `@tool` functions (`classify_and_file`, `request_misunderstood`, `mark_as_junk`) through Foundry callback mechanism with results written to Cosmos DB
- [x] **AGNT-03**: `AzureAIAgentClient` with `should_cleanup_agent=False` manages agent lifecycle — agent persists across Container App restarts
- [x] **AGNT-04**: Orchestrator agent eliminated; code-based routing in FastAPI endpoint replaces HandoffBuilder orchestration
- [x] **AGNT-05**: `transcribe_audio` is a `@tool` callable by the Classifier agent, using `gpt-4o-transcribe` via `AsyncAzureOpenAI` (replaces Whisper)
- [x] **AGNT-06**: Agent middleware wired: `AgentMiddleware` for audit logging, `FunctionMiddleware` for tool validation/timing

### Streaming

- [ ] **STRM-01**: `FoundrySSEAdapter` replaces `AGUIWorkflowAdapter`, streaming `AgentResponseUpdate` events to AG-UI SSE format
- [ ] **STRM-02**: Text capture produces same AG-UI events as v1 (`StepStarted`, `StepFinished`, `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED`, `RUN_FINISHED`)
- [ ] **STRM-03**: Voice capture produces same AG-UI events as v1 (transcription step + classification stream)

### HITL Parity

- [ ] **HITL-01**: Low-confidence captures filed as pending with bucket buttons for recategorization (direct Cosmos write, unchanged)
- [ ] **HITL-02**: Misunderstood captures trigger conversational follow-up using fresh Foundry thread (no conversation history contamination)
- [ ] **HITL-03**: Recategorize from inbox detail card works end-to-end (direct Cosmos write, unchanged)

### Observability

- [ ] **OBSV-01**: Application Insights receives traces from Foundry agent runs with per-classification visibility
- [ ] **OBSV-02**: Token usage and cost metrics visible in Foundry portal or Application Insights

### Specialist Agents

- [ ] **SPEC-01**: Admin Agent registered as persistent Foundry agent with domain-specific `@tool` functions for Admin bucket operations
- [ ] **SPEC-02**: Ideas Agent registered as persistent Foundry agent with domain-specific `@tool` functions for Ideas bucket operations
- [ ] **SPEC-03**: People Agent registered as persistent Foundry agent with domain-specific `@tool` functions for People bucket operations (including `log_interaction` updating `last_interaction` timestamp)
- [ ] **SPEC-04**: Projects Agent registered as persistent Foundry agent (stub — action item extraction deferred to v2.1)
- [ ] **SPEC-05**: Post-classification routing: FastAPI `if/elif` routes classified captures to the appropriate specialist agent for domain enrichment
- [ ] **SPEC-06**: Each specialist agent's Cosmos DB writes verified independently (Admin → Admin container, People → People container, etc.)

### Push Notifications

- [ ] **PUSH-01**: User's Expo push token registered on app startup via `POST /api/push-token` and stored in Cosmos DB
- [ ] **PUSH-02**: Backend can send push notifications to the user's device via Expo Push Service (APNs/FCM)
- [ ] **PUSH-03**: Notification frequency budget enforced: maximum 3 nudges per day total across all agents
- [ ] **PUSH-04**: Quiet hours enforced: no notifications between 9pm and 8am (user's timezone)
- [ ] **PUSH-05**: Push receipt polling detects `DeviceNotRegistered` and stops sending to invalid tokens
- [ ] **PUSH-06**: User taps notification and deep-links to the relevant capture/person/idea in the app (not home screen)
- [ ] **PUSH-07**: Notifications include action buttons: "Done" (marks complete) and "Snooze 1 week" (reschedules)
- [ ] **PUSH-08**: Backend `POST /api/nudge/respond` endpoint processes Done/Snooze actions from notification buttons

### Proactive Scheduling

- [ ] **SCHED-01**: APScheduler `AsyncIOScheduler` runs in FastAPI lifespan, sharing initialized agent connections and Cosmos client
- [ ] **SCHED-02**: Admin Agent sends Friday evening digest (5pm) summarizing pending Admin captures ranked by urgency
- [ ] **SCHED-03**: Admin Agent sends Saturday morning errand nudge (9am) for errand-type Admin captures
- [ ] **SCHED-04**: Ideas Agent sends weekly check-in (Tuesday-Thursday, 10am) for the stalest un-nudged idea with contextual "any new thoughts?" message
- [ ] **SCHED-05**: People Agent runs daily scan (8am) and sends relationship nudge when interaction gap exceeds 4-week threshold (max 1 People nudge per day)
- [ ] **SCHED-06**: All scheduled agent notifications use agent-generated copy referencing actual capture content (not templates)

### Deployment

- [ ] **DPLY-01**: Migrated backend deployed to Azure Container Apps with all new env vars and dependencies
- [ ] **DPLY-02**: CI/CD pipeline updated for new dependencies (`agent-framework-azure-ai`, `azure-monitor-opentelemetry`, `APScheduler`, `exponent-server-sdk`)
- [ ] **DPLY-03**: Expo development build created for push notification and notification action testing (Expo Go insufficient)

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
- [x] **CLAS-02**: Classifier assigns confidence score (0.0-1.0) — Phase 3
- [x] **CLAS-03**: Confidence >= 0.6 silently files and confirms — Phase 3
- [x] **CLAS-04**: Confidence < 0.6 triggers clarifying question — Phase 4
- [x] **CLAS-07**: Every capture logged to Inbox with classification details — Phase 3
- [x] **APPX-01**: Main screen shows capture buttons — Phase 2
- [x] **APPX-02**: Inbox view shows recent captures — Phase 4
- [x] **APPX-04**: Conversation view for clarification — Phase 4

### Partially Complete (v1.0)

- [ ] **INFRA-03**: Azure Blob Storage for media uploads — configured, voice working, photo/video deferred
- [ ] **CAPT-03**: Voice recording in Expo app via Whisper — backend working, mobile UAT incomplete

## v2.1 Requirements (Deferred)

### Projects Agent Intelligence

- **PROJ-01**: Projects Agent extracts action items from Project captures in real-time (new `action_item` Cosmos DB document type)
- **PROJ-02**: Projects Agent sends weekly progress check-in: "2 open items on [project]. Are you on track?" (requires PROJ-01)

## v3.0+ Requirements (Deferred)

### Connected Agents
- **CONN-01**: `classify_and_file` tool moved to Azure Functions for server-side execution
- **CONN-02**: Orchestrator re-introduced as Connected Agent invoking Classifier as sub-agent

### Geofencing
- **GEO-01**: Background geofencing for errand reminders (requires Expo dev build, known Android limitations)
- **GEO-02**: Location-aware nudges: "You're near CVS" when entering geofence region

### Features
- **SRCH-01**, **SRCH-02**: Search across all buckets
- **MDIA-01** through **MDIA-03**: Photo/video capture, share sheet
- **APPX-03**: Digest view in mobile app
- **DGST-01** through **DGST-06**: Comprehensive digest system
- **CLAS-05**, **CLAS-06**: Cross-references and duplicate checking

## Out of Scope

| Feature | Reason |
|---------|--------|
| Background geofencing | Expo managed workflow limitations, iOS force-quit kills it, Android doesn't restart. Time-window heuristic covers 80% of value. Deferred to v3.0 |
| Connected Agents pattern | Requires moving @tool functions to Azure Functions — v3.0 scope |
| Projects Agent action item extraction | HIGH complexity, new document type. Deferred to v2.1 after core agents proven |
| Per-person nudge frequency settings | Settings creep — add only when explicitly requested |
| Calendar integration | OAuth scope complexity out of bounds for v2.0 |
| Digest as conversation | Complex AG-UI threading redesign not justified for one-way summaries |
| Multi-user / multi-tenancy | Single-user system for Will only |
| Offline capture | Requires connectivity |

## Traceability

*Updated during roadmap creation: 2026-02-26*

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-10 | Phase 6: Foundry Infrastructure | Complete |
| INFRA-11 | Phase 6: Foundry Infrastructure | Complete |
| INFRA-12 | Phase 6: Foundry Infrastructure | Complete |
| INFRA-13 | Phase 6: Foundry Infrastructure | Complete |
| INFRA-14 | Phase 6: Foundry Infrastructure | Complete |
| AGNT-01 | Phase 7: Classifier Agent Baseline | Complete |
| AGNT-02 | Phase 7: Classifier Agent Baseline | Complete |
| AGNT-03 | Phase 7: Classifier Agent Baseline | Complete |
| AGNT-04 | Phase 6: Foundry Infrastructure | Complete |
| AGNT-05 | Phase 7: Classifier Agent Baseline | Complete |
| AGNT-06 | Phase 7: Classifier Agent Baseline | Complete |
| STRM-01 | Phase 8: FoundrySSEAdapter and Streaming | Pending |
| STRM-02 | Phase 8: FoundrySSEAdapter and Streaming | Pending |
| STRM-03 | Phase 8: FoundrySSEAdapter and Streaming | Pending |
| HITL-01 | Phase 9: HITL Parity and Observability | Pending |
| HITL-02 | Phase 9: HITL Parity and Observability | Pending |
| HITL-03 | Phase 9: HITL Parity and Observability | Pending |
| OBSV-01 | Phase 9: HITL Parity and Observability | Pending |
| OBSV-02 | Phase 9: HITL Parity and Observability | Pending |
| SPEC-01 | Phase 10: Specialist Agents | Pending |
| SPEC-02 | Phase 10: Specialist Agents | Pending |
| SPEC-03 | Phase 10: Specialist Agents | Pending |
| SPEC-04 | Phase 10: Specialist Agents | Pending |
| SPEC-05 | Phase 10: Specialist Agents | Pending |
| SPEC-06 | Phase 10: Specialist Agents | Pending |
| PUSH-01 | Phase 11: Push Notifications | Pending |
| PUSH-02 | Phase 11: Push Notifications | Pending |
| PUSH-03 | Phase 11: Push Notifications | Pending |
| PUSH-04 | Phase 11: Push Notifications | Pending |
| PUSH-05 | Phase 11: Push Notifications | Pending |
| PUSH-06 | Phase 11: Push Notifications | Pending |
| PUSH-07 | Phase 11: Push Notifications | Pending |
| PUSH-08 | Phase 11: Push Notifications | Pending |
| SCHED-01 | Phase 12: Proactive Scheduling and Deployment | Pending |
| SCHED-02 | Phase 12: Proactive Scheduling and Deployment | Pending |
| SCHED-03 | Phase 12: Proactive Scheduling and Deployment | Pending |
| SCHED-04 | Phase 12: Proactive Scheduling and Deployment | Pending |
| SCHED-05 | Phase 12: Proactive Scheduling and Deployment | Pending |
| SCHED-06 | Phase 12: Proactive Scheduling and Deployment | Pending |
| DPLY-01 | Phase 12: Proactive Scheduling and Deployment | Pending |
| DPLY-02 | Phase 12: Proactive Scheduling and Deployment | Pending |
| DPLY-03 | Phase 11: Push Notifications | Pending |

**Coverage:**
- v2.0 requirements: 42 total (corrected from initial estimate of 39)
- Mapped to phases: 42/42
- Unmapped: 0

---
*Requirements defined: 2026-02-26*
*Last updated: 2026-02-26 -- roadmap created, all 42 requirements mapped to phases 6-12*
