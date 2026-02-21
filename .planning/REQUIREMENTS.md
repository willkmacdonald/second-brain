# Requirements: The Active Second Brain

**Defined:** 2026-02-21
**Core Value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions — with zero organizational effort.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: Agent Framework server runs on Azure Container Apps with AG-UI endpoint accepting HTTP POST and streaming SSE responses
- [ ] **INFRA-02**: Cosmos DB provisioned with 5 containers (Inbox, People, Projects, Ideas, Admin) partitioned by `/userId`
- [ ] **INFRA-03**: Azure Blob Storage configured for media file uploads (voice recordings)
- [ ] **INFRA-04**: OpenTelemetry tracing enabled across all agent handoffs with traces viewable in Agent Framework DevUI
- [ ] **INFRA-05**: API key authentication protects the AG-UI endpoint (key stored in Expo Secure Store)

### Capture

- [ ] **CAPT-01**: User can type a thought in the Expo app and submit it with one tap
- [ ] **CAPT-02**: User receives real-time visual feedback showing the agent chain processing their capture (Orchestrator → Classifier → Action)
- [ ] **CAPT-03**: User can record a voice note in the Expo app which is transcribed by the Perception Agent via Whisper
- [ ] **CAPT-04**: User sees transcribed text and classification result after voice capture
- [ ] **CAPT-05**: Expo app runs on both iOS and Android

### Orchestration

- [ ] **ORCH-01**: Orchestrator Agent receives all input and routes to the correct specialist agent based on input type and context
- [ ] **ORCH-02**: Orchestrator routes text input directly to Classifier Agent
- [ ] **ORCH-03**: Orchestrator routes audio input to Perception Agent first, then Classifier Agent
- [ ] **ORCH-04**: Orchestrator routes classified Projects/Admin items to Action Agent for sharpening
- [ ] **ORCH-05**: Orchestrator routes digest/summary requests to Digest Agent
- [ ] **ORCH-06**: Orchestrator provides brief confirmation when the full agent chain completes

### Classification

- [ ] **CLAS-01**: Classifier Agent classifies input into exactly one of four buckets: People, Projects, Ideas, or Admin
- [ ] **CLAS-02**: Classifier assigns a confidence score (0.0–1.0) to each classification
- [ ] **CLAS-03**: When confidence >= 0.6, Classifier silently files the record and confirms (e.g., "Filed → Projects (0.85)")
- [ ] **CLAS-04**: When confidence < 0.6, Classifier asks the user a focused clarifying question before filing
- [ ] **CLAS-05**: Classifier checks existing People and Projects records before creating new ones
- [ ] **CLAS-06**: Classifier extracts cross-references (people mentioned in project captures, projects mentioned in people captures) and links them
- [ ] **CLAS-07**: Every capture is logged to the Inbox container with full classification details and agent chain metadata

### Action Sharpening

- [ ] **ACTN-01**: Action Agent receives items classified as Projects or Admin and sharpens vague thoughts into specific, executable next actions
- [ ] **ACTN-02**: Action Agent updates the Project's `nextAction` field or the Admin task's description with the sharpened action
- [ ] **ACTN-03**: When a thought is too vague to actionize, Action Agent asks one clarifying question ("What's the first concrete step?")
- [ ] **ACTN-04**: People and Ideas captures skip the Action Agent entirely

### People (Personal CRM)

- [ ] **PEOP-01**: People records store name, context, contact details, birthday, lastInteraction, interactionHistory, and followUps
- [ ] **PEOP-02**: When a capture mentions a known person, their record is updated with the interaction
- [ ] **PEOP-03**: When a capture mentions an unknown person, a new People record is created
- [ ] **PEOP-04**: User can view People records in the Expo app

### Digests

- [ ] **DGST-01**: Digest Agent composes a daily briefing under 150 words at 6:30 AM CT with Today's Focus (top 3 actions), Unblock This (one stuck item), and Small Win (recent progress)
- [ ] **DGST-02**: User can ask "what's on my plate" at any time and receive an ad-hoc summary from the Digest Agent
- [ ] **DGST-03**: Digest Agent composes a weekly review on Sunday 9 AM CT summarizing activity, stalled projects, and neglected relationships
- [ ] **DGST-04**: Push notification sent for daily digest and weekly review
- [ ] **DGST-05**: Push notification sent when an agent needs clarification (HITL)
- [ ] **DGST-06**: All other capture confirmations are silent (badge update only)

### Search

- [ ] **SRCH-01**: User can search across all buckets by keyword matching on rawText, titles, names, and task descriptions
- [ ] **SRCH-02**: Search results show the bucket, record title/name, and a snippet of matching text

### App UX

- [ ] **APPX-01**: Main screen shows four large capture buttons (Voice, Photo, Video, Text) — no settings, folders, or tags visible
- [ ] **APPX-02**: Inbox view shows recent captures with the agent chain that processed each one
- [ ] **APPX-03**: Digest view displays the morning briefing, opened via push notification
- [ ] **APPX-04**: Conversation view opens when a specialist needs clarification, showing a focused chat

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Media

- **MDIA-01**: User can capture and process photos with Vision understanding (OCR, scene description)
- **MDIA-02**: User can capture and process video clips with keyframe extraction
- **MDIA-03**: Share sheet extension for capturing from other apps

### Intelligence

- **INTL-01**: Entity Resolution Agent runs nightly to merge duplicate People records via fuzzy name matching
- **INTL-02**: Evaluation Agent produces weekly system health reports (classification accuracy, stale content, action quality, system performance)
- **INTL-03**: Full-text / semantic search with embeddings across all buckets
- **INTL-04**: Correction feedback loop — clarification history used as few-shot examples to improve classification

### Data

- **DATA-01**: JSON export of all records (data portability)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Folder/tag taxonomy | Contradicts zero-organization principle; forces decisions at capture time |
| Rich text editor | This is a capture app, not a writing app; degrades capture speed |
| Bi-directional links / graph view | Eye candy requiring thousands of notes; cross-references serve the same purpose |
| Offline capture | Core value (AI processing) requires cloud; Will's capture contexts have connectivity |
| Custom bucket types | Scope creep; 4 buckets are deliberately "painfully small" per Principle 9 |
| Real-time collaboration | Single-user system; zero benefit from multi-user complexity |
| Calendar integration | System captures thoughts, not schedules; Admin bucket handles time-sensitive tasks |
| Web clipper | Captures other people's content, not Will's thoughts; creates hoarding pattern |
| Template system | Pre-structured forms oppose frictionless capture; agents apply structure after capture |
| Plugin ecosystem | Single-user hobby project; adds maintenance burden for zero benefit |
| Gamification | Streaks/badges create guilt; contradicts "Design for Restart" principle |
| Multi-tenancy | Built for Will only; `userId: "will"` is hardcoded |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | TBD | Pending |
| INFRA-02 | TBD | Pending |
| INFRA-03 | TBD | Pending |
| INFRA-04 | TBD | Pending |
| INFRA-05 | TBD | Pending |
| CAPT-01 | TBD | Pending |
| CAPT-02 | TBD | Pending |
| CAPT-03 | TBD | Pending |
| CAPT-04 | TBD | Pending |
| CAPT-05 | TBD | Pending |
| ORCH-01 | TBD | Pending |
| ORCH-02 | TBD | Pending |
| ORCH-03 | TBD | Pending |
| ORCH-04 | TBD | Pending |
| ORCH-05 | TBD | Pending |
| ORCH-06 | TBD | Pending |
| CLAS-01 | TBD | Pending |
| CLAS-02 | TBD | Pending |
| CLAS-03 | TBD | Pending |
| CLAS-04 | TBD | Pending |
| CLAS-05 | TBD | Pending |
| CLAS-06 | TBD | Pending |
| CLAS-07 | TBD | Pending |
| ACTN-01 | TBD | Pending |
| ACTN-02 | TBD | Pending |
| ACTN-03 | TBD | Pending |
| ACTN-04 | TBD | Pending |
| PEOP-01 | TBD | Pending |
| PEOP-02 | TBD | Pending |
| PEOP-03 | TBD | Pending |
| PEOP-04 | TBD | Pending |
| DGST-01 | TBD | Pending |
| DGST-02 | TBD | Pending |
| DGST-03 | TBD | Pending |
| DGST-04 | TBD | Pending |
| DGST-05 | TBD | Pending |
| DGST-06 | TBD | Pending |
| SRCH-01 | TBD | Pending |
| SRCH-02 | TBD | Pending |
| APPX-01 | TBD | Pending |
| APPX-02 | TBD | Pending |
| APPX-03 | TBD | Pending |
| APPX-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 42 total
- Mapped to phases: 0
- Unmapped: 42

---
*Requirements defined: 2026-02-21*
*Last updated: 2026-02-21 after initial definition*
