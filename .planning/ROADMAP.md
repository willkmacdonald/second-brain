# Roadmap: The Active Second Brain

## Milestones

- [x] **v1.0 Text & Voice Capture Loop** - Phases 1-5 plus 4.1, 4.2, 4.3 (shipped 2026-02-25, partial)
- [ ] **v2.0 Proactive Second Brain** - Phases 6-12 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

<details>
<summary>v1.0 Text & Voice Capture Loop (Phases 1-5) - SHIPPED 2026-02-25</summary>

- [x] **Phase 1: Backend Foundation** - FastAPI server with AG-UI endpoint, Cosmos DB, API auth, and OpenTelemetry tracing
- [x] **Phase 2: Expo App Shell** - Mobile app with text input, main capture screen, and cross-platform support
- [x] **Phase 3: Text Classification Pipeline** - Orchestrator and Classifier agents that route text input to the correct bucket in Cosmos DB
- [x] **Phase 4: HITL Clarification and AG-UI Streaming** - Real-time agent chain visibility and clarification conversation for low-confidence classifications
- [x] **Phase 4.1: Backend Deployment to Azure Container Apps** (INSERTED) - Containerized deployment with CI/CD
- [x] **Phase 4.2: Swipe-to-delete inbox items** (INSERTED) - Inbox management UX
- [x] **Phase 4.3: Agent-User UX with unclear item** (INSERTED) - Three distinct classification failure flows
- [x] **Phase 5: Voice Capture** - Voice recording with Whisper transcription routed through the Perception Agent

</details>

### v2.0 Proactive Second Brain (Phases 6-12)

**Milestone Goal:** Transform the Second Brain from a filing cabinet into a proactive thinking partner -- rebuilt on Foundry Agent Service with four specialist agents that follow up over time via push notifications.

- [x] **Phase 6: Foundry Infrastructure** - Foundry project connectivity, RBAC, Application Insights, old code deletion, async credential migration (completed 2026-02-27)
- [x] **Phase 7: Classifier Agent Baseline** - Persistent Classifier agent registered in Foundry with local @tool execution validated in isolation (completed 2026-02-27)
- [x] **Phase 8: FoundrySSEAdapter and Streaming** - New SSE adapter replacing AGUIWorkflowAdapter, text and voice capture end-to-end on Foundry (completed 2026-02-27)
- [x] **Phase 9: HITL Parity and Observability** - All three HITL flows verified on Foundry, Application Insights traces and token metrics (completed 2026-02-27)
- [ ] **Phase 10: Specialist Agents** - Four domain agents (Admin, Ideas, People, Projects) with post-classification routing and Cosmos DB writes
- [ ] **Phase 11: Push Notifications** - Expo push token registration, delivery pipeline, throttling, quiet hours, deep links, action buttons
- [ ] **Phase 12: Proactive Scheduling and Deployment** - APScheduler cron jobs for all agent nudges, deployed to Azure Container Apps with updated CI/CD

## Phase Details

<details>
<summary>v1.0 Phase Details (Phases 1-5)</summary>

### Phase 1: Backend Foundation
**Goal**: The backend server is running, accepting requests, persisting data, and producing observable traces
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. A POST request to the AG-UI endpoint returns a streaming SSE response
  2. Documents can be created and read in each of the 5 Cosmos DB containers
  3. Requests without a valid API key are rejected with 401
  4. Agent handoff traces are visible in the Agent Framework DevUI
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md -- Project scaffold + AG-UI server with echo agent + OpenTelemetry
- [x] 01-02-PLAN.md -- Cosmos DB data layer (models, singleton client, CRUD tools)
- [x] 01-03-PLAN.md -- API key auth middleware + end-to-end integration verification

### Phase 2: Expo App Shell
**Goal**: Will can open the app on his phone, type a thought, and send it to the backend
**Depends on**: Phase 1
**Requirements**: CAPT-01, CAPT-05, APPX-01
**Success Criteria** (what must be TRUE):
  1. User can open the app and see four large capture buttons (Voice, Photo, Video, Text) with no settings, folders, or tags visible
  2. User can type a thought and submit it with one tap
  3. App runs on both iOS and Android devices via Expo
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md -- Expo project scaffold + main capture screen with four buttons
- [x] 02-02-PLAN.md -- Text capture flow with AG-UI backend connectivity

### Phase 3: Text Classification Pipeline
**Goal**: A typed thought is automatically classified into the correct bucket and filed in Cosmos DB without any user effort
**Depends on**: Phase 1, Phase 2
**Requirements**: ORCH-01, ORCH-02, ORCH-06, CLAS-01, CLAS-02, CLAS-03, CLAS-07
**Success Criteria** (what must be TRUE):
  1. A text capture submitted from the app is routed by the Orchestrator to the Classifier Agent
  2. The Classifier assigns the capture to exactly one of the four buckets (People, Projects, Ideas, Admin) with a confidence score
  3. When confidence is >= 0.6, the capture is silently filed and the user sees a confirmation
  4. Every capture is logged to the Inbox container with full classification details and agent chain metadata
  5. The Orchestrator provides a brief confirmation when the full agent chain completes
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md -- Backend classification pipeline (models, tools, agents, workflow, main.py wiring)
- [x] 03-02-PLAN.md -- Mobile classification result toast + backend classification tests

### Phase 4: HITL Clarification and AG-UI Streaming
**Goal**: Will can see agents working in real time and respond to clarification questions when the system is unsure
**Depends on**: Phase 3
**Requirements**: CLAS-04, CAPT-02, APPX-02, APPX-04
**Success Criteria** (what must be TRUE):
  1. User sees real-time visual feedback showing the agent chain processing their capture
  2. When classification confidence is < 0.6, the user is asked a focused clarifying question before filing
  3. Inbox view shows recent captures with the agent chain that processed each one
  4. Conversation view opens when a specialist needs clarification, showing a focused chat
**Plans**: 6 plans

Plans:
- [x] 04-01-PLAN.md -- Backend HITL workflow, AG-UI step events, echo filter, respond endpoint, Inbox API
- [x] 04-02-PLAN.md -- Mobile tab navigation, capture screen with step dots, streaming text, inline HITL bucket buttons
- [x] 04-03-PLAN.md -- Inbox list view with detail cards and conversation screen for pending clarifications
- [x] 04-04-PLAN.md -- [Gap fix] Backend: request_clarification tool, classifier instructions, adapter HITL detection, respond endpoint fix
- [x] 04-05-PLAN.md -- [Gap fix] Mobile: inboxItemId flow, real clarification text, top-2 bucket emphasis
- [x] 04-06-PLAN.md -- [UAT fix] Remove Classifier autonomous mode, fix useCallback closure bug, harden respond endpoint, inbox auto-refresh

### Phase 04.1: Backend Deployment to Azure Container Apps (INSERTED)
**Goal:** The FastAPI backend is containerized, deployed to Azure Container Apps, and accessible over HTTPS with automated CI/CD on push to main
**Depends on:** Phase 4
**Requirements:** INFRA-01
**Plans:** 2/2 plans complete

Plans:
- [x] 04.1-01-PLAN.md -- Backend containerization (Dockerfile + .dockerignore with multi-stage uv build)
- [x] 04.1-02-PLAN.md -- CI/CD pipeline and deployment (GitHub Actions workflow, Azure infra setup, deploy verification)

### Phase 04.2: Swipe-to-delete inbox items (INSERTED)
**Goal:** Users can swipe to delete inbox items
**Depends on:** Phase 4
**Plans:** 1/1 plan complete

Plans:
- [x] 04.2-01-PLAN.md -- Swipe-to-delete implementation

### Phase 04.3: Agent-User UX with unclear item (INSERTED)
**Goal:** Three distinct classification failure flows: misunderstood (conversational follow-up), low-confidence (silent pending filing), and mis-categorized (inbox recategorize)
**Depends on:** Phase 4
**Requirements:** CLAS-04, APPX-04 (extended)
**Plans:** 10/10 plans complete

Plans:
- [x] 04.3-01-PLAN.md -- Backend classification tools, classifier instructions, and adapter (misunderstood vs low-confidence)
- [x] 04.3-02-PLAN.md -- Backend recategorize endpoint (PATCH inbox item to different bucket)
- [x] 04.3-03-PLAN.md -- Follow-up endpoint + mobile capture screen misunderstood conversation flow
- [x] 04.3-04-PLAN.md -- Mobile inbox detail card bucket buttons and status dots
- [x] 04.3-05-PLAN.md -- [UAT fix] Backend: filter Classifier reasoning text, fix misunderstood event detection
- [x] 04.3-06-PLAN.md -- [UAT fix] Mobile: inbox bucket buttons for all statuses, misunderstood display fixes
- [x] 04.3-07-PLAN.md -- [Gap fix] Backend: score validation/fallback for 0.00 confidence scores
- [x] 04.3-08-PLAN.md -- [Gap fix] Backend: follow-up orphan reconciliation (update original, delete duplicates)
- [x] 04.3-09-PLAN.md -- [Gap fix] Backend: parse tool return string for corrected confidence in toast
- [x] 04.3-10-PLAN.md -- [Gap fix] Backend: narrow junk definition and reorder classifier decision flow

### Phase 5: Voice Capture
**Goal**: Will can speak a thought into the app and have it transcribed, classified, and filed automatically
**Depends on**: Phase 3
**Requirements**: INFRA-03, CAPT-03, CAPT-04, ORCH-03
**Success Criteria** (what must be TRUE):
  1. User can record a voice note in the Expo app
  2. The voice recording is uploaded to Azure Blob Storage and transcribed by the Perception Agent via Whisper
  3. User sees the transcribed text and classification result after voice capture
  4. Orchestrator correctly routes audio input to Perception Agent first, then to Classifier Agent
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md -- Backend infra: Blob Storage manager, Whisper transcription tool, Perception Agent
- [x] 05-02-PLAN.md -- Backend wiring: POST /api/voice-capture endpoint, Orchestrator update
- [x] 05-03-PLAN.md -- Mobile: voice recording screen (expo-audio), upload client, Voice button enabled

</details>

### Phase 6: Foundry Infrastructure
**Goal**: The Foundry project endpoint is reachable, RBAC allows authentication from both local dev and Container App, Application Insights is connected, dead orchestration code is deleted, and the codebase compiles cleanly against the new SDK
**Depends on**: Phase 5 (v1.0 complete)
**Requirements**: INFRA-10, INFRA-11, INFRA-12, INFRA-13, INFRA-14, AGNT-04
**Success Criteria** (what must be TRUE):
  1. `AzureAIAgentClient` can authenticate to the Foundry project endpoint from local dev using developer Entra ID credentials
  2. Application Insights instance is connected to the Foundry project and accepting telemetry
  3. HandoffBuilder, AGUIWorkflowAdapter, Orchestrator agent, Perception Agent, and Whisper code are deleted with no import errors remaining
  4. All new environment variables (`AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_CLASSIFIER_AGENT_ID`, `APPLICATIONINSIGHTS_CONNECTION_STRING`, specialist agent IDs) are configured in `.env` and `config.py`
  5. The backend starts without errors after async credential swap (`azure.identity.aio.DefaultAzureCredential`)
**Plans**: 3 plans

Plans:
- [x] 06-01-PLAN.md -- Delete old orchestration code (agents, workflow, AG-UI endpoints, tests)
- [x] 06-02-PLAN.md -- Add Foundry SDK + AppInsights deps, config.py update, AzureAIAgentClient init, enhanced health endpoint
- [x] 06-03-PLAN.md -- RBAC configuration, AppInsights connection, deployment validation

### Phase 7: Classifier Agent Baseline
**Goal**: The Classifier is a persistent Foundry-registered agent that executes local @tool functions and writes to Cosmos DB, validated in isolation before touching the live streaming pipeline
**Depends on**: Phase 6
**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-05, AGNT-06
**Success Criteria** (what must be TRUE):
  1. Classifier agent is visible in the AI Foundry portal with a stable ID that survives process restarts
  2. `classify_and_file` executes locally and writes to Cosmos DB when invoked by the Foundry service during an agent run
  3. `transcribe_audio` works as a @tool callable by the Classifier, producing text from a voice recording via `gpt-4o-transcribe`
  4. `AgentMiddleware` and `FunctionMiddleware` fire during agent runs, producing audit log entries and tool timing in console output
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md -- Rewrite classification tools (file_capture), create transcription tool, create middleware, rewrite classifier module
- [ ] 07-02-PLAN.md -- Wire agent registration into FastAPI lifespan, integration test for end-to-end classification

### Phase 8: FoundrySSEAdapter and Streaming
**Goal**: Text and voice captures flow end-to-end through the Foundry-backed Classifier, producing the same AG-UI SSE events the mobile app already consumes
**Depends on**: Phase 7
**Requirements**: STRM-01, STRM-02, STRM-03
**Success Criteria** (what must be TRUE):
  1. Text capture from the Expo app produces `StepStarted`, `StepFinished`, and `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED` custom events identical to v1 behavior
  2. Voice capture produces AG-UI events with a transcription step followed by classification result, same as v1
  3. The `FoundrySSEAdapter` replaces `AGUIWorkflowAdapter` and the mobile app works without any frontend code changes
**Plans**: 2 plans

Plans:
- [ ] 08-01-PLAN.md -- Backend streaming module (FoundrySSEAdapter), POST /api/capture endpoint, SSE event constructors
- [ ] 08-02-PLAN.md -- Mobile event parser update for new v2 event types, endpoint URLs updated to /api/capture

### Phase 9: HITL Parity and Observability
**Goal**: All three HITL flows work identically to v1 on the Foundry backend, and Application Insights shows per-classification traces with token and cost metrics
**Depends on**: Phase 8
**Requirements**: HITL-01, HITL-02, HITL-03, OBSV-01, OBSV-02
**Success Criteria** (what must be TRUE):
  1. Low-confidence captures are filed as pending with bucket buttons appearing in the mobile inbox for recategorization
  2. Misunderstood captures trigger conversational follow-up using a fresh Foundry thread with no history contamination from the first classification pass
  3. Recategorize from inbox detail card writes to Cosmos DB and updates the mobile UI
  4. Application Insights shows traces for Foundry agent runs with per-classification visibility including token usage and cost
**Plans**: 7 plans

Plans:
- [x] 09-01-PLAN.md -- HITL parity: follow-up endpoint with thread reuse, pending instant PATCH, mobile updates
- [x] 09-02-PLAN.md -- Observability: enable_instrumentation(), OTel middleware spans, endpoint-level trace spans
- [x] 09-03-PLAN.md -- [Gap fix] Replace sendClarification with direct PATCH in capture screens, fix OTel span attribute
- [x] 09-04-PLAN.md -- [UAT fix] LOW_CONFIDENCE SSE event for pending captures with bucket buttons on capture screen
- [x] 09-05-PLAN.md -- [UAT fix] Voice follow-up for misunderstood clarifications (voice-first, text fallback)
- [x] 09-06-PLAN.md -- [UAT fix] Classifier instruction tuning: misunderstood vs pending boundary, follow-up context weighting
- [ ] 09-07-PLAN.md -- [UAT fix] Follow-up in-place update: file_capture updates existing misunderstood doc instead of creating orphan

### Phase 09.1: Mobile UX review and refinements (INSERTED)

**Goal:** Consolidate the two redundant capture screens into a single unified screen with Voice/Text mode toggle, inline text capture, granular processing feedback stages, and follow-up mode switching via persistent top toggles
**Requirements**: UX-01, UX-02, UX-03, UX-04, UX-05
**Depends on:** Phase 9
**Plans:** 1/2 plans executed

Plans:
- [ ] 09.1-01-PLAN.md -- Unified capture screen: Voice/Text toggle, text capture integration, processing stages, dead code cleanup
- [ ] 09.1-02-PLAN.md -- UAT checkpoint: verify unified screen on real device

### Phase 10: Specialist Agents
**Goal**: Four domain-specific agents enrich classified captures with domain intelligence before filing, each writing to its own Cosmos DB container
**Depends on**: Phase 9
**Requirements**: SPEC-01, SPEC-02, SPEC-03, SPEC-04, SPEC-05, SPEC-06
**Success Criteria** (what must be TRUE):
  1. Admin, Ideas, People, and Projects agents are visible as persistent agents in the AI Foundry portal with stable IDs
  2. After classification, the FastAPI endpoint routes the capture to the correct specialist agent based on the classified bucket
  3. Each specialist agent's @tool functions write enriched data to the correct Cosmos DB container (Admin to Admin, People to People, etc.)
  4. People Agent's `log_interaction` tool updates the `last_interaction` timestamp on the Person document
  5. Projects Agent is registered and functional as a stub (accepts captures, files them, but does not extract action items)
**Plans**: TBD

Plans:
- [ ] 10-01: TBD
- [ ] 10-02: TBD

### Phase 11: Push Notifications
**Goal**: The backend can deliver push notifications to Will's phone with frequency throttling, quiet hours, deep links, and action buttons -- proven end-to-end before any scheduler is connected
**Depends on**: Phase 10
**Requirements**: PUSH-01, PUSH-02, PUSH-03, PUSH-04, PUSH-05, PUSH-06, PUSH-07, PUSH-08, DPLY-03
**Success Criteria** (what must be TRUE):
  1. Expo push token is registered on app startup and stored in Cosmos DB via `POST /api/push-token`
  2. A test push notification sent from the backend arrives on Will's device via Expo Push Service
  3. Notification frequency budget (max 3/day) and quiet hours (9pm-8am) reject sends that would violate limits
  4. Tapping a notification deep-links to the relevant capture/person/idea in the app (not home screen)
  5. Notification action buttons ("Done" and "Snooze 1 week") trigger `POST /api/nudge/respond` and update the item in Cosmos DB
**Plans**: TBD

Plans:
- [ ] 11-01: TBD
- [ ] 11-02: TBD
- [ ] 11-03: TBD

### Phase 12: Proactive Scheduling and Deployment
**Goal**: Specialist agents proactively nudge Will at the right times via scheduled jobs, and the complete v2.0 system is deployed to Azure Container Apps
**Depends on**: Phase 11
**Requirements**: SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05, SCHED-06, DPLY-01, DPLY-02
**Success Criteria** (what must be TRUE):
  1. APScheduler runs in the FastAPI lifespan with cron triggers for all scheduled agent jobs
  2. Admin Agent sends a Friday 5pm digest summarizing pending Admin captures and a Saturday 9am errand nudge
  3. Ideas Agent sends a weekly check-in (Tue-Thu, 10am) for the stalest un-nudged idea with contextual agent-generated copy
  4. People Agent sends a relationship nudge when the interaction gap exceeds 4 weeks (max 1/day, daily 8am scan)
  5. All scheduled notifications use agent-generated copy referencing actual capture content and the migrated backend is deployed to Azure Container Apps with updated CI/CD
**Plans**: TBD

Plans:
- [ ] 12-01: TBD
- [ ] 12-02: TBD
- [ ] 12-03: TBD

## Progress

**Execution Order:**
- v1.0: 1 -> 2 -> 3 -> 4 -> 4.1 -> 4.2 -> 4.3 -> 5 (complete)
- v2.0: 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Backend Foundation | v1.0 | 3/3 | Complete | 2026-02-21 |
| 2. Expo App Shell | v1.0 | 2/2 | Complete | 2026-02-22 |
| 3. Text Classification Pipeline | v1.0 | 2/2 | Complete | 2026-02-22 |
| 4. HITL Clarification and AG-UI Streaming | v1.0 | 6/6 | Complete | 2026-02-24 |
| 4.1 Backend Deployment to Azure Container Apps | v1.0 | 2/2 | Complete | 2026-02-23 |
| 4.2 Swipe-to-delete inbox items | v1.0 | 1/1 | Complete | 2026-02-24 |
| 4.3 Agent-User UX with unclear item | v1.0 | 10/10 | Complete | 2026-02-25 |
| 5. Voice Capture | v1.0 | 3/3 | Complete | 2026-02-25 |
| 6. Foundry Infrastructure | v2.0 | Complete    | 2026-02-27 | 2026-02-27 |
| 7. Classifier Agent Baseline | v2.0 | Complete    | 2026-02-27 | - |
| 8. FoundrySSEAdapter and Streaming | v2.0 | Complete    | 2026-02-27 | - |
| 9. HITL Parity and Observability | v2.0 | 6/7 | Gap closure | 2026-02-27 |
| 10. Specialist Agents | v2.0 | 0/TBD | Not started | - |
| 11. Push Notifications | v2.0 | 0/TBD | Not started | - |
| 12. Proactive Scheduling and Deployment | v2.0 | 0/TBD | Not started | - |
