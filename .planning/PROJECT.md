# The Active Second Brain

## What This Is

A personal capture-and-intelligence system that turns fleeting thoughts — voice notes and text — into organized, actionable records across four buckets (People, Projects, Ideas, Admin). Built on Azure AI Foundry Agent Service with a persistent Classifier agent and an Expo mobile app as the capture surface. Will's only job is to capture the thought; the agent handles classification, filing, and HITL clarification automatically.

## Core Value

One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies — with zero organizational effort from the user.

## Current State (after v2.0)

**Shipped:** v2.0 Foundry Migration & HITL Parity (2026-03-01)
**Architecture:** Azure AI Foundry Agent Service with persistent Classifier agent, FastAPI code-based routing, SSE streaming to Expo mobile app
**Codebase:** ~2,800 LOC Python (backend), ~19,800 LOC TypeScript (mobile)
**Deployed:** Azure Container Apps with CI/CD via GitHub Actions

**What works today:**
- Text capture → Classifier agent → filed to Cosmos DB with confidence scoring
- Voice capture → `gpt-4o-transcribe` → Classifier agent → filed
- Low-confidence captures show bucket buttons for manual selection
- Misunderstood captures trigger conversational follow-up (text + voice)
- Unified capture screen with Voice/Text toggle (voice default)
- Granular processing feedback (Uploading → Classifying)
- Inbox with detail cards, recategorize, swipe-to-delete
- Application Insights observability with OTel spans and token usage

## Next Milestone: v3.0 Proactive Second Brain

**Goal:** Transform the filing cabinet into a proactive thinking partner. Four specialist agents per bucket that follow up over time via push notifications.

*Requirements to be defined via `/gsd:new-milestone`*

## Requirements

### Validated

- [x] Text capture from Expo app routes through Classifier → filed to Cosmos DB — v1.0
- [x] Voice capture transcribed by gpt-4o-transcribe, then classified and filed — v1.0, v2.0
- [x] Classifier Agent classifies into People/Projects/Ideas/Admin with confidence scoring — v1.0
- [x] Low-confidence captures trigger bucket selection buttons (HITL) — v1.0, v2.0
- [x] Misunderstood captures trigger conversational follow-up (text + voice) — v1.0, v2.0
- [x] AG-UI SSE streams real-time agent feedback to the app — v1.0, v2.0
- [x] Inbox view with detail cards and recategorize capability — v1.0
- [x] Foundry Agent Service migration: persistent Classifier, AzureAIAgentClient, local @tool — v2.0
- [x] FoundrySSEAdapter replaces AGUIWorkflowAdapter — v2.0
- [x] Application Insights with OTel spans and token usage tracking — v2.0
- [x] All three HITL flows working on Foundry (low-confidence, misunderstood, recategorize) — v2.0
- [x] Unified capture screen with Voice/Text toggle, inline text, processing stages — v2.0

### Active (v3.0)

*To be defined via `/gsd:new-milestone`*

### Future (v3.0+)

- Photo/video capture processed by vision model
- Cross-references extracted (people mentioned in projects, projects mentioned with people)
- Daily digest delivered at 6:30 AM CT with top actions, blockers, and wins (<150 words)
- Weekly review digest on Sunday 9 AM CT
- Full-text search across all buckets
- Entity Resolution Agent for duplicate People records

### Out of Scope

- Multi-user / multi-tenancy — single-user system for Will only
- Offline capture — requires connectivity
- Real-time chat — not core to the capture loop
- Background geofencing — Expo managed workflow limitations; time-window heuristic covers 80% of value
- Connected Agents pattern — requires moving @tool functions to Azure Functions
- Projects Agent action item extraction — deferred to after core agents proven
- Calendar integration — OAuth scope complexity out of bounds

## Context

**Who:** Will Macdonald — Microsoft Manufacturing Industry Advisor (MedTech focus) by day, AI/Python hobbyist developer by night.

**Problem:** Traditional note-taking systems fail because they require organizational effort at capture time. Open cognitive loops pile up. The brain is for thinking, not storage.

**Learning goal:** This is explicitly a learning project for multi-agent orchestration patterns using Microsoft Agent Framework. The architecture is chosen to deeply learn these patterns.

**Agent team (current):**
1. **Classifier** — persistent Foundry agent that classifies captures into People/Projects/Ideas/Admin with confidence scoring, executes `file_capture` and `transcribe_audio` @tools locally

**Agent team (v3.0 target):**
2. **Admin Agent** — errand/task specialist: timing awareness, weekend digest
3. **Projects Agent** — action item tracking, progress follow-ups (stub initially)
4. **Ideas Agent** — weekly idea check-ins, keeps captured ideas alive
5. **People Agent** — relationship tracking, interaction nudges

**Data model:** Cosmos DB with 5 containers (Inbox, People, Projects, Ideas, Admin), all partitioned by `/userId`.

## Constraints

- **Tech stack**: Microsoft Agent Framework (Python), Azure AI Foundry Agent Service, Expo/React Native, Azure Container Apps, Cosmos DB, Blob Storage
- **Agent client**: `AzureAIAgentClient` from `agent-framework-azure-ai` (Foundry Agent Service)
- **Protocol**: AG-UI (SSE event stream) for agent-to-frontend communication
- **LLM**: Azure OpenAI GPT-4o (with `gpt-4o-transcribe` for voice)
- **Platform**: iOS and Android via Expo
- **Single user**: No multi-tenancy — hardcode `userId: "will"`
- **Observability**: Application Insights + Foundry portal
- **Infrastructure**: AI Foundry project (project endpoint, Azure AI User RBAC)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Microsoft Agent Framework for multi-agent orchestration | Explicit learning goal + handoff pattern + OpenTelemetry | ✓ Good — learned fundamentals through v1 and v2 |
| AG-UI protocol for frontend communication | Open standard, real-time streaming, handoff visibility | ✓ Good — works well for SSE streaming |
| Cosmos DB NoSQL | JSON documents, serverless pricing, free tier | ✓ Good — simple, effective for single-user |
| API key auth (not Azure AD) | Single user, simplest approach | ✓ Good — no issues |
| GPT-4o for all agents | Proven model, native Agent Framework support | ✓ Good — quality and cost acceptable |
| AzureOpenAIChatClient + HandoffBuilder for v1 | Simplest option to learn Agent Framework basics | ✓ Good — learned fundamentals, graduated to Foundry |
| Foundry Agent Service migration (v2.0) | Persistent agents, server threads, portal observability | ✓ Good — cleaner architecture, better observability |
| FastAPI code-based routing (no Orchestrator agent) | Connected Agents can't call local @tools | ✓ Good — simpler, more reliable than HandoffBuilder |
| gpt-4o-transcribe replaces Whisper | Better quality, simpler pipeline | ✓ Good — cleaner voice capture |
| ContextVar for follow-up state | file_capture is @tool, can't add params agent doesn't know | ✓ Good — eliminated orphan reconciliation |
| Unified capture screen (v2.0) | Two screens were redundant | ✓ Good — simpler UX, voice-first design |
| v2.0 scope = Foundry migration only | Original scope (specialist agents + push) too large. Ship migration, defer proactive features | ✓ Good — clean cut point |

---
*Last updated: 2026-03-01 after v2.0 milestone*
