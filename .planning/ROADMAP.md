# Roadmap: The Active Second Brain

## Overview

This roadmap delivers a multi-agent capture-and-intelligence system in 9 phases, progressing from backend infrastructure through the core text capture-classify loop, then layering on multimodal input, action sharpening, people CRM, digests, and search. The build order is driven by the research finding that proving one agent works with real daily captures before adding the next is the single most important risk mitigation. Phases 1-4 deliver a usable daily text capture system; Phases 5-9 expand capabilities on that proven foundation.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Backend Foundation** - FastAPI server with AG-UI endpoint, Cosmos DB, API auth, and OpenTelemetry tracing
- [x] **Phase 2: Expo App Shell** - Mobile app with text input, main capture screen, and cross-platform support
- [ ] **Phase 3: Text Classification Pipeline** - Orchestrator and Classifier agents that route text input to the correct bucket in Cosmos DB
- [x] **Phase 4: HITL Clarification and AG-UI Streaming** - Real-time agent chain visibility and clarification conversation for low-confidence classifications
- [ ] **Phase 5: Voice Capture** - Voice recording with Whisper transcription routed through the Perception Agent
- [ ] **Phase 6: Action Sharpening** - Action Agent that converts vague Projects/Admin captures into concrete next actions
- [ ] **Phase 7: People CRM and Cross-References** - People records with automatic relationship tracking and cross-reference extraction
- [ ] **Phase 8: Digests and Notifications** - Daily/weekly briefings, ad-hoc queries, and push notifications
- [ ] **Phase 9: Search** - Keyword search across all buckets with result snippets

## Phase Details

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
- [x] 01-01-PLAN.md — Project scaffold + AG-UI server with echo agent + OpenTelemetry
- [x] 01-02-PLAN.md — Cosmos DB data layer (models, singleton client, CRUD tools)
- [x] 01-03-PLAN.md — API key auth middleware + end-to-end integration verification

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
- [x] 02-01-PLAN.md — Expo project scaffold + main capture screen with four buttons
- [x] 02-02-PLAN.md — Text capture flow with AG-UI backend connectivity

### Phase 3: Text Classification Pipeline
**Goal**: A typed thought is automatically classified into the correct bucket and filed in Cosmos DB without any user effort
**Depends on**: Phase 1, Phase 2
**Requirements**: ORCH-01, ORCH-02, ORCH-06, CLAS-01, CLAS-02, CLAS-03, CLAS-07
**Success Criteria** (what must be TRUE):
  1. A text capture submitted from the app is routed by the Orchestrator to the Classifier Agent
  2. The Classifier assigns the capture to exactly one of the four buckets (People, Projects, Ideas, Admin) with a confidence score
  3. When confidence is >= 0.6, the capture is silently filed and the user sees a confirmation (e.g., "Filed -> Projects (0.85)")
  4. Every capture is logged to the Inbox container with full classification details and agent chain metadata
  5. The Orchestrator provides a brief confirmation when the full agent chain completes
**Plans**: 2 plans

Plans:
- [x] 03-01-PLAN.md — Backend classification pipeline (models, tools, agents, workflow, main.py wiring)
- [x] 03-02-PLAN.md — Mobile classification result toast + backend classification tests

### Phase 4: HITL Clarification and AG-UI Streaming
**Goal**: Will can see agents working in real time and respond to clarification questions when the system is unsure
**Depends on**: Phase 3
**Requirements**: CLAS-04, CAPT-02, APPX-02, APPX-04
**Success Criteria** (what must be TRUE):
  1. User sees real-time visual feedback showing the agent chain processing their capture (Orchestrator -> Classifier -> Action)
  2. When classification confidence is < 0.6, the user is asked a focused clarifying question before filing
  3. Inbox view shows recent captures with the agent chain that processed each one
  4. Conversation view opens when a specialist needs clarification, showing a focused chat
**Plans**: 6 plans (3 original + 3 gap closure)

Plans:
- [x] 04-01-PLAN.md — Backend HITL workflow, AG-UI step events, echo filter, respond endpoint, Inbox API
- [x] 04-02-PLAN.md — Mobile tab navigation, capture screen with step dots, streaming text, inline HITL bucket buttons
- [x] 04-03-PLAN.md — Inbox list view with detail cards and conversation screen for pending clarifications
- [x] 04-04-PLAN.md — [Gap fix] Backend: request_clarification tool, classifier instructions, adapter HITL detection, respond endpoint fix
- [x] 04-05-PLAN.md — [Gap fix] Mobile: inboxItemId flow, real clarification text, top-2 bucket emphasis
- [x] 04-06-PLAN.md — [UAT fix] Remove Classifier autonomous mode, fix useCallback closure bug, harden respond endpoint, inbox auto-refresh

### Phase 04.2: Swipe-to-delete inbox items (INSERTED)

**Goal:** [Urgent work - to be planned]
**Depends on:** Phase 4
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 04.2 to break down)

### Phase 04.1: Backend Deployment to Azure Container Apps (INSERTED)

**Goal:** The FastAPI backend is containerized, deployed to Azure Container Apps, and accessible over HTTPS with automated CI/CD on push to main
**Depends on:** Phase 4
**Requirements:** INFRA-01
**Plans:** 6/6 plans complete

Plans:
- [x] 04.1-01-PLAN.md -- Backend containerization (Dockerfile + .dockerignore with multi-stage uv build)
- [x] 04.1-02-PLAN.md -- CI/CD pipeline and deployment (GitHub Actions workflow, Azure infra setup, deploy verification)

### Phase 5: Voice Capture
**Goal**: Will can speak a thought into the app and have it transcribed, classified, and filed automatically
**Depends on**: Phase 3
**Requirements**: INFRA-03, CAPT-03, CAPT-04, ORCH-03
**Success Criteria** (what must be TRUE):
  1. User can record a voice note in the Expo app
  2. The voice recording is uploaded to Azure Blob Storage and transcribed by the Perception Agent via Whisper
  3. User sees the transcribed text and classification result after voice capture
  4. Orchestrator correctly routes audio input to Perception Agent first, then to Classifier Agent
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

### Phase 6: Action Sharpening
**Goal**: Vague project and admin captures are automatically sharpened into specific, executable next actions
**Depends on**: Phase 3
**Requirements**: ACTN-01, ACTN-02, ACTN-03, ACTN-04, ORCH-04
**Success Criteria** (what must be TRUE):
  1. Items classified as Projects or Admin are routed to the Action Agent after classification
  2. The Action Agent converts vague thoughts into specific next actions and updates the record
  3. When a thought is too vague, the Action Agent asks one clarifying question ("What's the first concrete step?")
  4. People and Ideas captures skip the Action Agent entirely
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

### Phase 7: People CRM and Cross-References
**Goal**: Will's People records are automatically created, updated, and linked to other captures
**Depends on**: Phase 3
**Requirements**: PEOP-01, PEOP-02, PEOP-03, PEOP-04, CLAS-05, CLAS-06
**Success Criteria** (what must be TRUE):
  1. People records store name, context, contact details, birthday, lastInteraction, interactionHistory, and followUps
  2. When a capture mentions a known person, their record is updated with the interaction
  3. When a capture mentions an unknown person, a new People record is created
  4. Cross-references are extracted linking People and Projects mentioned in each other's captures
  5. User can view People records in the Expo app
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD
- [ ] 07-03: TBD

### Phase 8: Digests and Notifications
**Goal**: Will receives automated daily and weekly briefings and can ask "what's on my plate" at any time
**Depends on**: Phase 6, Phase 7
**Requirements**: DGST-01, DGST-02, DGST-03, DGST-04, DGST-05, DGST-06, ORCH-05, APPX-03
**Success Criteria** (what must be TRUE):
  1. A daily briefing under 150 words is composed at 6:30 AM CT with Today's Focus, Unblock This, and Small Win sections
  2. A weekly review is composed on Sunday 9 AM CT summarizing activity, stalled projects, and neglected relationships
  3. User can ask "what's on my plate" at any time and receive an ad-hoc summary
  4. Push notification is sent for daily digest, weekly review, and when an agent needs clarification
  5. All other capture confirmations are silent (badge update only)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD
- [ ] 08-02: TBD
- [ ] 08-03: TBD

### Phase 9: Search
**Goal**: Will can find any capture or record by searching across all buckets
**Depends on**: Phase 3
**Requirements**: SRCH-01, SRCH-02
**Success Criteria** (what must be TRUE):
  1. User can search across all buckets by keyword matching on rawText, titles, names, and task descriptions
  2. Search results show the bucket, record title/name, and a snippet of matching text
**Plans**: TBD

Plans:
- [ ] 09-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
Note: Phases 5, 6, 7, and 9 depend only on Phase 3 and can be parallelized, but serial execution is recommended for a solo developer.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Foundation | 3/3 | Complete | 2026-02-21 |
| 2. Expo App Shell | 2/2 | Complete    | 2026-02-22 |
| 3. Text Classification Pipeline | 2/2 | Complete | 2026-02-22 |
| 4. HITL Clarification and AG-UI Streaming | 6/6 | Complete | 2026-02-24 |
| 4.1 Backend Deployment to Azure Container Apps | 2/2 | Complete | 2026-02-23 |
| 5. Voice Capture | 0/3 | Not started | - |
| 6. Action Sharpening | 0/2 | Not started | - |
| 7. People CRM and Cross-References | 0/3 | Not started | - |
| 8. Digests and Notifications | 0/3 | Not started | - |
| 9. Search | 0/1 | Not started | - |
