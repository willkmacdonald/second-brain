# The Active Second Brain

## What This Is

A personal capture-and-intelligence system that turns fleeting thoughts — voice notes and text — into organized, actionable records across four buckets (People, Projects, Ideas, Admin). Built on Azure AI Foundry Agent Service with persistent Classifier and Admin agents, an Expo mobile app as the capture surface, and a dynamic errands system with voice-managed destination routing. Will's only job is to capture the thought; the agents handle classification, filing, errand routing, recipe extraction, and HITL clarification automatically.

## Core Value

One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies — with zero organizational effort from the user.

## Current Milestone: v3.1 Observability & Evals

**Goal:** The system watches itself — an investigation agent answers questions about captures and system health, an eval pipeline measures agent quality, and alerts fire when things degrade.

**Target features:**
- Observability investigation agent (mobile chat + dashboard + Claude Code MCP tool)
- Eval framework for Classifier and Admin Agent quality (implicit signals, manual feedback, golden datasets, Azure AI Foundry evals)
- Self-monitoring loop with alerts when eval scores drop

## Current State (after v3.0)

**Shipped:** v3.0 Admin Agent & Shopping Lists (2026-03-23)
**Architecture:** Azure AI Foundry Agent Service with persistent Classifier and Admin agents, FastAPI code-based routing, SSE streaming to Expo mobile app, Playwright for recipe scraping
**Codebase:** ~5,100 LOC Python (backend), ~110,800 LOC TypeScript (mobile)
**Deployed:** Azure Container Apps with CI/CD via GitHub Actions

**What works today:**
- Text capture → Classifier agent → filed to Cosmos DB with confidence scoring
- Voice capture → on-device SFSpeechRecognizer (iOS) with cloud fallback → Classifier → filed
- Multi-bucket splitting for mixed-content captures ("buy milk and call the vet")
- Admin-classified captures → Admin Agent processes silently when user opens Status screen
- Dynamic destination routing with voice-managed affinity rules and HITL routing for unknowns
- Recipe URL pasting → three-tier fetch → ingredient extraction → errand items with source attribution
- Status & Priorities screen with errands grouped by destination, swipe-to-remove, processing banner
- Admin notifications as dismissible banners (rule confirmations, query responses)
- Per-capture trace ID propagation from mobile through backend to App Insights
- Azure Monitor alerts for API errors, capture failures, and health checks
- Low-confidence captures show bucket buttons for manual selection
- Misunderstood captures trigger conversational follow-up (text + voice)
- Inbox with detail cards, recategorize, swipe-to-delete
- Security hardened: timing-safe auth, parameterized queries, error sanitization, upload validation

## Requirements

### Validated

- ✓ Text capture from Expo app routes through Classifier → filed to Cosmos DB — v1.0
- ✓ Voice capture transcribed and classified — v1.0, v2.0, v3.0 (on-device SFSpeechRecognizer)
- ✓ Classifier Agent classifies into People/Projects/Ideas/Admin with confidence scoring — v1.0
- ✓ Low-confidence captures trigger bucket selection buttons (HITL) — v1.0, v2.0
- ✓ Misunderstood captures trigger conversational follow-up (text + voice) — v1.0, v2.0
- ✓ AG-UI SSE streams real-time agent feedback to the app — v1.0, v2.0
- ✓ Inbox view with detail cards and recategorize capability — v1.0
- ✓ Foundry Agent Service migration: persistent Classifier, AzureAIAgentClient, local @tool — v2.0
- ✓ FoundrySSEAdapter replaces AGUIWorkflowAdapter — v2.0
- ✓ Application Insights with OTel spans and token usage tracking — v2.0
- ✓ All three HITL flows working on Foundry (low-confidence, misunderstood, recategorize) — v2.0
- ✓ Unified capture screen with Voice/Text toggle, inline text, processing stages — v2.0
- ✓ Admin Agent as persistent Foundry agent with silent background processing — v3.0
- ✓ Multi-bucket splitting for mixed-content captures — v3.0
- ✓ Dynamic destination routing with voice-managed affinity rules — v3.0
- ✓ HITL routing for unrouted items with auto-learning — v3.0
- ✓ Recipe URL extraction with ingredient parsing and source attribution — v3.0
- ✓ Status & Priorities screen with errands grouped by destination — v3.0
- ✓ On-device voice transcription via SFSpeechRecognizer (cloud fallback preserved) — v3.0
- ✓ Per-capture trace ID propagation and structured logging — v3.0
- ✓ Azure Monitor alerts and KQL operational queries — v3.0
- ✓ Security hardening (timing-safe auth, parameterized queries, upload validation) — v3.0

### Active (v3.1)

- [ ] Observability investigation agent — natural language interface over App Insights (mobile chat + dashboard + Claude Code MCP tool)
- [ ] Eval framework for Classifier and Admin Agent quality — implicit signals, manual feedback, golden datasets, Azure AI Foundry evals
- [ ] Self-monitoring alerts when eval scores drop

### Active (v3.2+)

- [ ] Push notifications for agent-processed output
- [ ] Location-aware reminders (notify near store with items on list)
- [ ] Projects Agent — action item tracking, progress follow-ups
- [ ] Ideas Agent — weekly idea check-ins, keeps captured ideas alive
- [ ] People Agent — relationship tracking, interaction nudges
- [ ] Daily digest delivered at 6:30 AM CT
- [ ] Full-text search across all buckets

### Future

- Recurring item auto-ordering (computer use for Chewy.com, etc.)
- "I've got free hours" → Admin Agent surfaces fitting tasks
- Weekend meal prep planning pipeline
- Photo/video capture processed by vision model
- Cross-references extracted (people mentioned in projects, projects mentioned with people)
- Weekly review digest on Sunday 9 AM CT
- Entity Resolution Agent for duplicate People records
- YouTube recipe extraction via captions (supplement URL extraction)

### Out of Scope

- Multi-user / multi-tenancy — single-user system for Will only
- Offline capture — requires connectivity
- Real-time chat — not core to the capture loop
- Background geofencing — Expo managed workflow limitations
- Connected Agents pattern — requires moving @tool functions to Azure Functions
- Calendar integration — OAuth scope complexity out of bounds

## Context

**Who:** Will Macdonald — Microsoft Manufacturing Industry Advisor (MedTech focus) by day, AI/Python hobbyist developer by night.

**Problem:** Traditional note-taking systems fail because they require organizational effort at capture time. Open cognitive loops pile up. The brain is for thinking, not storage.

**Learning goal:** This is explicitly a learning project for multi-agent orchestration patterns using Microsoft Agent Framework. The architecture is chosen to deeply learn these patterns.

**Agent team:**
1. **Classifier** — persistent Foundry agent that classifies captures into People/Projects/Ideas/Admin with confidence scoring, multi-bucket splitting for mixed content, executes `file_capture` and `transcribe_audio` @tools locally
2. **Admin Agent** — household operations manager with 6 tools: `add_errand_items`, `get_routing_context`, `manage_destination`, `manage_affinity_rule`, `query_rules`, `fetch_recipe_url`. Routes items to dynamic destinations using affinity rules stored in Cosmos DB.

**Data model:** Cosmos DB with 9 containers (Inbox, People, Projects, Ideas, Admin, Errands, Destinations, AffinityRules + legacy Admin), partitioned by `/userId` or `/destination`/`/slug`/`/itemPattern`.

## Constraints

- **Tech stack**: Microsoft Agent Framework (Python), Azure AI Foundry Agent Service, Expo/React Native, Azure Container Apps, Cosmos DB, Blob Storage, Playwright (recipe scraping)
- **Agent client**: `AzureAIAgentClient` from `agent-framework-azure-ai` (Foundry Agent Service)
- **Protocol**: AG-UI (SSE event stream) for agent-to-frontend communication
- **LLM**: Azure OpenAI GPT-4o
- **Voice**: On-device SFSpeechRecognizer via expo-speech-recognition (cloud gpt-4o-transcribe as fallback)
- **Platform**: iOS via Expo (EAS development builds for native modules)
- **Single user**: No multi-tenancy — hardcode `userId: "will"`
- **Observability**: Application Insights with per-capture trace IDs, structured logging, KQL queries, Azure Monitor alerts
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
| Admin Agent as second persistent Foundry agent | Mirrors Classifier pattern, separate client/tools | ✓ Good — clean separation, no tool leakage |
| Processing triggered by Status screen GET (not auto-fire) | User reviews inbox first, then triggers processing | ✓ Good — matches Will's intended workflow |
| Dynamic destinations replace hardcoded store list | Voice-managed rules in Cosmos, HITL routing for unknowns | ✓ Good — extensible, auto-learning |
| pending_calls dict for batched tool calls | SDK delivers function_call/result in batches, single-variable tracking drops second result | ✓ Good — fixed multi-bucket splitting |
| Three-tier recipe fetch (Jina, httpx, Playwright) | Each tier catches different site types; Playwright is heavyweight fallback | ✓ Good — works for most recipe sites |
| On-device SFSpeechRecognizer via expo-speech-recognition | Eliminates cloud transcription cost, real-time streaming | ✓ Good — faster, free, works well for informal captures |
| Per-capture trace ID via ContextVar + Cosmos doc | ContextVar for sync flow, stored on inbox doc for async admin processing | ✓ Good — full E2E traceability |
| hmac.compare_digest for API key auth | Timing-safe comparison prevents timing attacks | ✓ Good — security baseline |

---
*Last updated: 2026-04-05 after v3.1 milestone started*
