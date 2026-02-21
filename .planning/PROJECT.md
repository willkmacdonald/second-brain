# The Active Second Brain

## What This Is

A personal capture-and-intelligence system that turns fleeting thoughts — voice notes, photos, text — into organized, actionable records across four buckets (People, Projects, Ideas, Admin). Built as a multi-agent system using Microsoft Agent Framework with an Expo mobile app as the capture surface. Will's only job is to capture the thought; seven specialist agents handle everything else.

## Core Value

One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions — with zero organizational effort from the user.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Text capture from Expo app routes through Orchestrator → Classifier → filed to Cosmos DB
- [ ] Voice capture transcribed by Perception Agent, then classified and filed
- [ ] Photo/video capture processed by Perception Agent (vision + transcription)
- [ ] Classifier Agent classifies into People/Projects/Ideas/Admin with confidence scoring
- [ ] Low-confidence captures trigger clarification conversation with the user (HITL)
- [ ] Action Agent sharpens vague thoughts into executable next actions for Projects/Admin
- [ ] Cross-references extracted (people mentioned in projects, projects mentioned with people)
- [ ] Daily digest delivered at 6:30 AM CT with top actions, blockers, and wins (<150 words)
- [ ] Weekly review digest on Sunday 9 AM CT
- [ ] Ad-hoc "what's on my plate" queries answered via Digest Agent
- [ ] Entity Resolution Agent runs nightly to merge duplicate People records
- [ ] Evaluation Agent produces weekly system health reports (Phase 4)
- [ ] AG-UI protocol streams real-time agent handoff visibility to the app
- [ ] OpenTelemetry tracing across all agent handoffs
- [ ] Push notifications only for clarification requests and digests

### Out of Scope

- Multi-user / multi-tenancy — single-user system for Will only
- Offline capture — requires connectivity
- Real-time chat — not core to the capture loop
- Cost ceiling optimization — optimize for capability
- Full-text search — deferred to Phase 4
- Share sheet extension — deferred to Phase 4
- Video keyframe extraction — deferred to Phase 4

## Context

**Who:** Will Macdonald — Microsoft Manufacturing Industry Advisor (MedTech focus) by day, AI/Python hobbyist developer by night. Child at Lane Tech, does woodworking.

**Problem:** Traditional note-taking systems fail because they require organizational effort at capture time. Open cognitive loops pile up across work and personal life. The brain is for thinking, not storage.

**Learning goal:** This is explicitly a learning project for multi-agent orchestration patterns using Microsoft Agent Framework. The architecture (7 agents, handoff pattern, AG-UI, OpenTelemetry) is chosen to deeply learn these patterns, not because a simpler architecture couldn't work.

**Agent team:**
1. **Orchestrator** — routes input to the right specialist
2. **Perception** — converts voice/image/video to text
3. **Classifier** — classifies into buckets, files records, owns clarification
4. **Action** — sharpens vague thoughts into concrete next actions (Projects/Admin only)
5. **Digest** — composes daily/weekly briefings
6. **Entity Resolution** — nightly People record reconciliation
7. **Evaluation** — weekly system health assessment (Phase 4)

**Data model:** Cosmos DB with 5 containers (Inbox, People, Projects, Ideas, Admin), all partitioned by `/userId`. Minimalist fields — "painfully small" to ensure adoption.

**Existing decisions:** 18 design decisions already resolved in the PRD covering auth (API key), entity resolution (lazy nightly), mode dimension, offline (not needed), cost (no cap), digest timing (6:30 AM CT), notifications (silent except HITL/digests), and architecture choices.

## Constraints

- **Tech stack**: Microsoft Agent Framework (Python), Azure OpenAI GPT-5.2, Expo/React Native, Azure Container Apps, Cosmos DB, Blob Storage
- **Protocol**: AG-UI (SSE event stream) for agent-to-frontend communication
- **LLM**: Azure OpenAI GPT-4o (with Vision for Perception Agent, Whisper for transcription)
- **Platform**: iOS and Android via Expo
- **Single user**: No multi-tenancy design needed — hardcode `userId: "will"`
- **Observability**: OpenTelemetry built into Agent Framework, DevUI for development
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

---
*Last updated: 2026-02-21 after requirements definition (LLM changed to GPT-4o)*
