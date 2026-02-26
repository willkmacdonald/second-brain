# The Active Second Brain

## What This Is

A personal capture-and-intelligence system that turns fleeting thoughts — voice notes, photos, text — into organized, actionable records across four buckets (People, Projects, Ideas, Admin). Built as a multi-agent system using Microsoft Agent Framework with an Expo mobile app as the capture surface. Will's only job is to capture the thought; seven specialist agents handle everything else.

## Core Value

One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions — with zero organizational effort from the user.

## Current Milestone: v2.0 Proactive Second Brain

**Goal:** Transform the Second Brain from a filing cabinet into a proactive thinking partner — rebuilt on Foundry Agent Service with four specialist agents that follow up over time. Captures still flow in via text/voice, but now each bucket has a specialist agent that understands its domain and proactively nudges Will at the right time.

**Target features:**
- Foundry Agent Service infrastructure (persistent agents, Connected Agents, server threads)
- Hard delete old orchestration code (HandoffBuilder, AzureOpenAIChatClient, Perception Agent, Whisper)
- `gpt-4o-transcribe` replaces Whisper for voice transcription
- Application Insights observability (per-agent traces, token usage, cost)
- **Admin Agent** — errand timing awareness (weekend vs weekday), Friday evening weekend planning digest, location-aware reminders (geofencing)
- **Ideas Agent** — weekly nudge per idea ("any new thoughts on X?"), keeps ideas alive
- **Projects Agent** — tracks action items, follows up on progress ("are you on track?"), accountability partner
- **People Agent** — relationship nudges ("haven't talked to X in Y weeks"), follow-up reminders, interaction tracking
- Push notifications (Expo) for all proactive nudges
- Background geofencing for location-aware errand reminders
- All v1 capture flows working on new foundation (text, voice, HITL)
- Mobile app capture UX unchanged (AG-UI SSE interface stays the same)

## Requirements

### Validated (v1.0)

- [x] Text capture from Expo app routes through Orchestrator → Classifier → filed to Cosmos DB
- [x] Voice capture transcribed by Perception Agent, then classified and filed
- [x] Classifier Agent classifies into People/Projects/Ideas/Admin with confidence scoring
- [x] Low-confidence captures trigger clarification conversation with the user (HITL)
- [x] AG-UI protocol streams real-time agent handoff visibility to the app
- [x] Misunderstood captures trigger conversational follow-up
- [x] Inbox view with detail cards and recategorize capability

### Active (v2.0)

*Defined in .planning/REQUIREMENTS.md*

### Future (v3.0+)

- Photo/video capture processed by vision model
- Cross-references extracted (people mentioned in projects, projects mentioned with people)
- Daily digest delivered at 6:30 AM CT with top actions, blockers, and wins (<150 words)
- Weekly review digest on Sunday 9 AM CT
- Ad-hoc "what's on my plate" queries answered via Digest Agent
- Entity Resolution Agent runs nightly to merge duplicate People records
- Evaluation Agent produces weekly system health reports
- Full-text search across all buckets

### Out of Scope

- Multi-user / multi-tenancy — single-user system for Will only
- Offline capture — requires connectivity
- Real-time chat — not core to the capture loop
- Cost ceiling optimization — optimize for capability
- Full-text search — deferred to v3.0+
- Share sheet extension — deferred to v3.0+
- Video keyframe extraction — deferred to v3.0+

## Context

**Who:** Will Macdonald — Microsoft Manufacturing Industry Advisor (MedTech focus) by day, AI/Python hobbyist developer by night. Child at Lane Tech, does woodworking.

**Problem:** Traditional note-taking systems fail because they require organizational effort at capture time. Open cognitive loops pile up across work and personal life. The brain is for thinking, not storage.

**Learning goal:** This is explicitly a learning project for multi-agent orchestration patterns using Microsoft Agent Framework. The architecture (7 agents, handoff pattern, AG-UI, OpenTelemetry) is chosen to deeply learn these patterns, not because a simpler architecture couldn't work.

**Agent team (v2.0):**
1. **Orchestrator** — routes input to the right specialist, manages Connected Agent invocations
2. **Classifier** — classifies captures into People/Projects/Ideas/Admin with confidence scoring
3. **Admin Agent** — errand/task specialist: timing awareness, location reminders, weekend digest
4. **Projects Agent** — action item tracking, progress follow-ups, accountability nudges
5. **Ideas Agent** — weekly idea check-ins, keeps captured ideas alive
6. **People Agent** — relationship tracking, interaction nudges, follow-up reminders

**Data model:** Cosmos DB with 5 containers (Inbox, People, Projects, Ideas, Admin), all partitioned by `/userId`. Minimalist fields — "painfully small" to ensure adoption.

**Existing decisions:** 18 design decisions already resolved in the PRD covering auth (API key), entity resolution (lazy nightly), mode dimension, offline (not needed), cost (no cap), digest timing (6:30 AM CT), notifications (silent except HITL/digests), and architecture choices.

## Constraints

- **Tech stack**: Microsoft Agent Framework (Python), Azure AI Foundry Agent Service, Expo/React Native, Azure Container Apps, Cosmos DB, Blob Storage
- **Agent client**: `AzureAIAgentClient` from `agent-framework-azure-ai` (Foundry Agent Service — NOT `AzureOpenAIChatClient`)
- **Protocol**: AG-UI (SSE event stream) for agent-to-frontend communication
- **LLM**: Azure OpenAI GPT-4o (with `gpt-4o-transcribe` for voice — replaces Whisper)
- **Platform**: iOS and Android via Expo
- **Single user**: No multi-tenancy design needed — hardcode `userId: "will"`
- **Observability**: Application Insights + Foundry portal (replaces DevUI-only observability)
- **Infrastructure**: AI Foundry project required (project endpoint, Azure AI User RBAC)
- **First-time framework**: Will is learning Agent Framework through this project — expect discovery and iteration

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Microsoft Agent Framework for multi-agent orchestration | Explicit learning goal + handoff pattern + OpenTelemetry + DevUI | — Pending |
| AG-UI protocol for frontend communication | Open standard, real-time streaming, handoff visibility | — Pending |
| Handoff pattern (not parallel) | Specialists own their domain + clarification conversation | — Pending |
| Action Agent separate from Classifier | Single responsibility — classify vs sharpen are different skills | — Pending |
| Cosmos DB NoSQL | JSON documents, serverless pricing, free tier, simple for single-user | — Pending |
| API key auth (not Azure AD) | Single user, simplest approach, stored in Expo Secure Store | — Pending |
| GPT-4o for all agents | Proven model, native Agent Framework support, lower cost than GPT-5.2 | — Pending |
| Evaluation Agent in Phase 4 | Needs weeks of data before patterns emerge | — Pending |
| Claude Code + GSD methodology | Development approach; fallback to spec-driven if GSD impedes | — Pending |
| AzureOpenAIChatClient + HandoffBuilder for v1 | Simplest option to learn Agent Framework basics first | ✓ Good — learned fundamentals, now graduating |
| Foundry Agent Service migration (v2.0) | Learning goal demands real infrastructure: persistent agents, server threads, Connected Agents, portal observability | — Pending |
| v2.0 scope = migration only | Same features as v1 rebuilt on Foundry. Action/People/Digests/Search deferred to v3.0 | ⚠️ Revisit — expanded to proactive specialist agents |
| v2.0 scope = proactive specialist agents | Filing cabinet → thinking partner. Specialist agents per bucket with follow-up behaviors. Full Foundry + intelligence in one milestone | — Pending |
| Push notifications for nudges | All proactive behaviors delivered via push. Expo push notification system | — Pending |
| Background geofencing for errands | Location-aware reminders for Admin Agent errand tracking | — Pending |
| gpt-4o-transcribe replaces Whisper | Better quality, simpler pipeline, hard delete Perception Agent + Whisper code | — Pending |

---
*Last updated: 2026-02-25 after v2.0 milestone redefinition (proactive specialist agents)*
