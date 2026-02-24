# Project Research Summary

**Project:** Active Second Brain
**Domain:** Multi-agent personal knowledge management / AI-powered capture-and-intelligence system
**Researched:** 2026-02-21
**Confidence:** MEDIUM-HIGH

## Executive Summary

The Active Second Brain is a multi-agent capture-and-intelligence system built around a fundamentally different philosophy than existing PKM tools: zero organizational friction at capture time, with AI agents handling all classification and enrichment in the background. The recommended approach is a Python backend using Microsoft Agent Framework (RC, API-stable) with a FastAPI + AG-UI SSE endpoint serving an Expo React Native mobile app. Seven specialist agents (Orchestrator, Perception, Classifier, Action, Digest, Entity Resolution, Evaluation) work in a handoff mesh, each with a focused responsibility, backed by Azure Cosmos DB and Blob Storage. The full stack is aligned with your existing Azure expertise and global preferences.

The core competitive insight is clear: no existing PKM tool combines multimodal capture + AI classification + human-in-the-loop clarification + action sharpening + personal CRM + automated digest in a single system. Competitors (Mem 2.0, Tana, Notion AI, Capacities, Reflect) each cover 2-3 of these capabilities; the Active Second Brain integrates all of them. The deliberate tradeoffs — no offline mode, no rich editor, no folder taxonomy — are not weaknesses but the mechanism by which the product maintains focus on its core value: capturing a thought in under 3 seconds and having agents do the rest.

The primary risk is not technical — it is behavioral. Research on PKM system failure consistently identifies "system works technically but user stops using it" as the dominant failure mode. The architecture is intentionally complex (7 agents, multi-agent orchestration) because the learning goal matters, but every technical decision must be subordinated to the daily capture experience. A system that processes 10 captures per day is more valuable than one that has 7 agents deployed but processes 0. Build the capture-classify loop first, prove you use it daily, then expand.

## Key Findings

### Recommended Stack

The backend centers on Microsoft Agent Framework (1.0.0b260210, released RC 2026-02-18) with FastAPI and the AG-UI protocol for real-time streaming from agents to the mobile client. The framework provides first-class handoff orchestration, built-in OpenTelemetry tracing, and a one-line FastAPI integration (`add_agent_framework_fastapi_endpoint`). GPT-5.2 (GA on Azure AI Foundry since Dec 2025) handles all LLM inference. Azure Cosmos DB (serverless, NoSQL API) stores all structured data across 5 containers; Azure Blob Storage handles binary media. The mobile app uses Expo SDK 54 with `react-native-sse` for the AG-UI SSE client — CopilotKit has no native React Native support (confirmed by GitHub issue #1892, open and unresolved as of Feb 2026).

The stack has no low-confidence technology choices with the exception of two points: the `azure-cosmos` version needs validation on install, and the React Native AG-UI client requires a custom implementation since no official package exists. Everything else — Agent Framework, FastAPI, Expo SDK 54, Azure services — is verified from official sources. AutoGen and Semantic Kernel are confirmed deprecated and merged into Agent Framework; do not use them.

**Core technologies:**
- **Microsoft Agent Framework 1.0.0b260210**: Multi-agent handoff orchestration — unified successor to AutoGen + Semantic Kernel, API-stable RC with full 1.0 feature set
- **FastAPI + AG-UI**: HTTP API server + real-time SSE streaming — first-party integration via `agent-framework-ag-ui`, one-line registration
- **Azure OpenAI (GPT-5.2)**: LLM inference for all agents — enterprise-grade, structured outputs, reliable tool use, GA on Azure AI Foundry
- **Expo SDK 54 + React Native 0.81**: Mobile capture frontend — New Architecture enabled, `TextDecoderStream` support for SSE, latest stable
- **Azure Cosmos DB (serverless)**: Document storage for all captures and records — JSON-native, vector search support, single-partition serverless is cost-appropriate for single user
- **Azure Blob Storage**: Binary media storage — voice recordings and photos upload directly; agents receive blob URLs
- **Azure Container Apps**: Backend hosting — scale-to-zero, managed identity, your existing experience, ~$5-15/month single user

### Expected Features

The feature research reveals a clear split between what creates the core value proposition and what creates complexity without proportional benefit. The 4-bucket model (People, Projects, Ideas, Admin) is deliberately simpler than competitors' taxonomy systems — this simplicity is the feature, not a limitation.

**Must have (table stakes) — P1:**
- Text capture via Expo app (validates full pipeline end-to-end)
- Voice capture with Whisper transcription (table stakes in 2026 for any capture app)
- Automatic AI classification into 4 buckets with confidence scoring
- AG-UI real-time feedback showing agent chain (builds trust through visibility)
- Human-in-the-loop clarification when confidence is low (prevents misclassification poisoning early data)
- Capture confirmation UX with instant acknowledgment (<200ms "captured")
- Cross-device sync (Cosmos DB as single source of truth; mobile is thin client)

**Should have (competitive advantage) — P2:**
- Photo capture with GPT-5.2 Vision processing (unique among competitors)
- Action sharpening (vague -> concrete next actions — no competitor has a dedicated action agent)
- Daily digest (<150 words, 6:30 AM — the concise output constraint is a design decision preventing information overload)
- Basic keyword search across Cosmos DB indexed fields (table stakes, don't defer to Phase 4)
- Cross-reference extraction linking People and Projects from captures
- Data export as JSON (prevents lock-in anxiety, trivial to build)
- Push notifications for digest and HITL clarification

**Defer (v2+) — P3:**
- Entity Resolution Agent (needs 10+ People records to be useful)
- Weekly review automation (needs 2+ weeks of data history)
- System Evaluation Agent (needs 4+ weeks of data across all agents — meta-evaluation of a nascent system produces noise)
- Full-text/semantic search with embeddings
- Video capture and keyframe extraction

**Explicitly excluded (anti-features):**
Folder/tag taxonomy, rich-text editor, bi-directional graph view, offline mode, custom bucket types, real-time collaboration, calendar integration, web clipper, template system, gamification. These are deliberate non-features that keep the product focused.

### Architecture Approach

The architecture is a single FastAPI application deployed on Azure Container Apps, exposing an AG-UI SSE endpoint that drives a handoff mesh of 5 real-time agents (Orchestrator, Perception, Classifier, Action, Digest) plus 2 standalone scheduled agents (Entity Resolution nightly, Evaluation weekly). The mobile app is a thin capture client that uploads binary media to Blob Storage first, then sends the blob URL through the AG-UI channel. Structured data lives in 5 Cosmos DB containers (Inbox, People, Projects, Ideas, Admin) partitioned by `/userId`. All agents share a tool library (`cosmos.py`, `blob.py`, `transcription.py`, `vision.py`) via Agent Framework's `@tool` decorator. Background agents (Entity Resolution, Evaluation) are explicitly excluded from the handoff mesh and run as standalone scheduled tasks — including them in the mesh broadcasts every user message to them unnecessarily.

**Major components:**
1. **Expo App** — Capture surface (text/voice/photo), AG-UI SSE client via `react-native-sse`, digest viewer; thin client, all intelligence is backend
2. **FastAPI + AG-UI Endpoint** — Single HTTP entry point; `add_agent_framework_fastapi_endpoint(app, workflow, "/")` registers the entire handoff workflow
3. **Handoff Workflow (5-agent mesh)** — Orchestrator triages → Perception transcribes media → Classifier files to bucket → Action sharpens → Digest answers queries; built with `HandoffBuilder`
4. **Shared Tool Library** — `@tool` functions for Cosmos DB CRUD, Blob read, Whisper transcription, Vision analysis; shared across agents
5. **Cosmos DB (5 containers)** — Persistent structured storage; Inbox is transient staging, 4 final containers hold classified records
6. **Blob Storage** — Raw media storage; Expo uploads directly via SAS token, Perception Agent reads by URL
7. **Scheduled Agents** — Entity Resolution (nightly) and Evaluation (weekly) run outside the handoff mesh, triggered by APScheduler or ACA scheduled tasks
8. **OpenTelemetry** — Built into Agent Framework; zero-config tracing across handoffs; essential for debugging multi-agent failures

### Critical Pitfalls

1. **The "Bag of Agents" trap** — Building all 7 agents before 1 works reliably. Multi-agent systems show up to 17x error amplification without proven coordination. Prevention: Build Classifier alone first (text in → Cosmos DB record), prove it works with 50+ real captures, then add Orchestrator in front, then Perception. Phase 1 ends with exactly 1 agent processing real data end-to-end.

2. **AG-UI React Native gap** — No first-party React Native AG-UI client exists (issue #510 is in-progress, no timeline). Prevention: Accept you will build a custom SSE client using `react-native-sse`. Phase 1 should use simple REST + SSE without AG-UI abstractions; add AG-UI typed events only after the transport works reliably on both iOS and Android physical devices.

3. **Expo SSE blocking in dev builds** — `ExpoRequestCdpInterceptor` blocks `text/event-stream` responses in Android debug builds, causing indefinite hangs. Prevention: Validate SSE with a health-check endpoint on a physical Android device as the first thing done in the mobile project, before any agent integration.

4. **Synchronous capture processing** — Running the full agent chain synchronously while the user waits. A 3-4 agent chain with GPT-5.2 takes 5-15 seconds. Prevention: Write to Inbox immediately (return <500ms confirmation), process agent chain asynchronously. Capture UX must never block on classification.

5. **Building a system you admire instead of one you use** — The engineering complexity (7 agents, OpenTelemetry, AG-UI streaming) can become the goal. Prevention: Track "captures per day" as the primary metric. If 0 for 3 consecutive days, stop feature work and fix UX. Phase 1 must end with daily real-world usage, not "technically works."

## Implications for Roadmap

Based on research, the architecture's build order, feature dependencies, and pitfall-to-phase mapping converge on a clear 4-phase structure.

### Phase 1: Foundation — Capture-Classify Core Loop

**Rationale:** Every downstream feature depends on the Cosmos DB data layer, the AG-UI SSE transport, and a working Classifier agent. The pitfalls research is unambiguous: prove one agent works with real data before building the second. Architecture research specifies the exact build order: FastAPI shell + AG-UI → Cosmos DB data layer → Expo AG-UI client → Classifier agent. These must be sequential.

**Delivers:** A usable daily capture system. Text input on the Expo app → Orchestrator routing → Classifier filing → Cosmos DB record, with AG-UI SSE showing agent activity and instant capture confirmation. HITL clarification for low-confidence classifications. Basic keyword search. Data export.

**Features from FEATURES.md:** Text capture, automatic 4-bucket classification with confidence scoring, AG-UI real-time feedback, HITL clarification, capture confirmation UX, basic keyword search, data export JSON.

**Stack elements:** Agent Framework (Classifier only initially), FastAPI + AG-UI endpoint, Cosmos DB 5 containers with correct partition keys, Expo SDK 54, `react-native-sse`, Azure OpenAI GPT-5.2.

**Avoids:** Bag of Agents trap (only Classifier + Orchestrator by end of phase), Expo SSE blocking (validated on Android before any agent work), synchronous capture processing (async from day 1), wrong Cosmos DB partition key (decided before first `container.create()` call).

**Research flag:** This phase has well-documented patterns. Agent Framework handoff docs + Cosmos DB SDK docs cover it. No additional research needed before starting.

**Phase 1 success criteria:** You use the app daily for real captures. Not "it works technically."

---

### Phase 2: Multimodal Input + Action Pipeline

**Rationale:** Once text classification is trusted (50+ real captures, >80% accuracy), add voice and photo input. These require Blob Storage integration and the Perception Agent. The Action Agent depends on Classifier working correctly — it cannot sharpen what isn't classified. Features research confirms these are P1-P2 priorities.

**Delivers:** Full multimodal capture (text/voice/photo) with action sharpening for Projects/Admin captures. Daily digest. Push notifications.

**Features from FEATURES.md:** Voice capture + Whisper transcription, photo capture + GPT-5.2 Vision, action sharpening (vague → concrete next actions), daily digest (<150 words, 6:30 AM), push notifications for digest and HITL.

**Stack elements:** Perception Agent + Blob Storage integration, Action Agent added to handoff mesh, Digest Agent (on-demand + scheduled), APScheduler for digest cron, Expo Push Notifications, Expo Audio (`useAudioRecorder`), Expo Camera (`CameraView`).

**Implements:** Media Upload → Blob Storage → Perception Agent pattern (Architecture Pattern 3). Add OpenTelemetry custom spans before adding the 3rd agent (per pitfall warning).

**Avoids:** AG-UI React Native gap (custom SSE client already proven in Phase 1 before typed AG-UI events are added), context loss during handoffs (integration test verifying context survives Orchestrator → Classifier → Action chain), model tiering for cost control (not every agent needs GPT-5.2 — evaluate GPT-4o-mini for Classifier).

**Research flag:** Whisper integration for voice transcription may need targeted research. The audio trimming requirement (Whisper 25MB limit, charge per minute) has specific handling needs. Recommend a focused research spike on Whisper + `expo-audio` integration before Phase 2 starts.

---

### Phase 3: Intelligence Layer — Cross-References + People CRM

**Rationale:** Cross-reference extraction and personal CRM features require existing People and Projects records to match against — this is a hard dependency. Entity Resolution requires 10+ People records to be meaningful. These features depend on data accumulation from Phase 1 and Phase 2 usage.

**Delivers:** Automatic relationship tracking (People mentioned in captures → People records updated), cross-reference extraction linking People ↔ Projects, nightly Entity Resolution deduplication, weekly review automation.

**Features from FEATURES.md:** Cross-reference extraction, personal CRM with auto-tracking from captures, Entity Resolution Agent (nightly), weekly review (Digest Agent weekly mode), share sheet extension (if desired).

**Stack elements:** Entity Resolution Agent (standalone scheduled, not in handoff mesh), Classifier Agent extended with cross-reference extraction tools, APScheduler nightly cron, Cosmos DB change feed or "dirty" flag pattern to scope Entity Resolution to modified records only.

**Avoids:** Entity Resolution scanning full People container on every run (use change feed or dirty flag — pitfall identified in performance traps). HITL clarification backlog growing (auto-classify with best guess after 24 hours, never permanent "pending" state).

**Research flag:** Entity Resolution fuzzy name matching algorithm needs research. The conservative merge strategy (flag ambiguous, don't auto-merge) is correct, but the matching threshold and deduplication logic are non-trivial. Recommend research-phase before starting Entity Resolution agent implementation.

---

### Phase 4: System Intelligence — Evaluation + Polish

**Rationale:** The Evaluation Agent requires 4+ weeks of operational data across all agents plus OpenTelemetry traces to produce meaningful insights. This is correctly deferred. Semantic search requires sufficient data for embeddings to be useful. This phase also addresses any UX polish needed based on actual usage patterns discovered in Phases 1-3.

**Delivers:** System self-evaluation (classification accuracy tracking, action completion rates, stale content detection), semantic search with embeddings, video capture and keyframe extraction, full OpenTelemetry production observability.

**Features from FEATURES.md:** Evaluation Agent (weekly health reports), full-text/semantic search, video capture + keyframes, any deferred P3 features based on actual usage needs.

**Stack elements:** Evaluation Agent (standalone scheduled), Cosmos DB vector embedding search (support added in azure-cosmos 4.7.0+), OpenTelemetry sampling configured for production (10-20% tail-based), Batch API for Digest and Evaluation agents (50% cost reduction for async non-real-time work).

**Avoids:** OpenTelemetry overhead at full fidelity in production (configure sampling before this phase; 18-49% CPU overhead measured at full trace fidelity).

**Research flag:** Cosmos DB vector search integration for semantic search needs research — the API has changed across SDK versions. Recommend research-phase specifically for the vector embedding approach before implementation.

---

### Phase Ordering Rationale

- **Phase 1 before anything**: The Cosmos DB schema and AG-UI SSE transport are foundational dependencies. Wrong partition key requires container recreation and data migration. Broken SSE means nothing works. These must be solved first, and validated with real daily usage before adding complexity.
- **Phase 2 requires Phase 1 data**: The Action Agent needs classified captures to sharpen. Perception Agent outputs feed into the same Classifier. Daily digest needs captures to summarize — an empty digest kills the habit loop.
- **Phase 3 requires accumulated People/Projects data**: Cross-reference extraction is useless without existing records to match against. Entity Resolution on 2 People records is pointless. This phase only delivers value after Phase 1-2 have generated real data.
- **Phase 4 requires full operational history**: Evaluation Agent producing insights about a system that has been running for days, not weeks, generates noise. Semantic search requires enough captures for embeddings to cluster meaningfully.

### Research Flags

**Needs research-phase before implementation:**
- **Phase 2** (Whisper + expo-audio integration): Audio trimming, ambient noise handling, domain-specific vocabulary (proper nouns, technical terms). This has real-world gotchas not covered by official docs.
- **Phase 3** (Entity Resolution algorithm): Fuzzy name matching thresholds, conservative merge strategy implementation, Cosmos DB change feed pattern for incremental processing.
- **Phase 4** (Cosmos DB vector search): API surface has changed across SDK versions; embedding strategy for personal capture data needs validation.

**Standard patterns — skip research-phase:**
- **Phase 1** (FastAPI + AG-UI + Cosmos DB + Expo): All of this is covered by official Microsoft Learn documentation and well-established patterns. Docs are complete and high-quality.
- **Phase 2** (Blob Storage + Perception Agent): Standard Azure pattern, mature SDK, well-documented. Exception: Whisper integration (flagged above).
- **Phase 2** (Action Agent): Standard handoff pattern; well-documented in Agent Framework. Prompt engineering is the main challenge, not integration.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core technologies verified from official sources: Agent Framework RC announcement, Expo SDK 54 changelog, Azure service SDKs. Two LOW-confidence items: azure-cosmos latest version (validate on install) and React Native AG-UI client (confirmed must be custom-built). |
| Features | MEDIUM-HIGH | Competitor analysis is thorough (15 PKM tools surveyed). Feature prioritization is grounded in real patterns from Mem, Tana, Notion AI, Capacities, Reflect. The "anti-features" section is exceptionally well-reasoned. Lower confidence on emergent AI-agentic features (HITL UX patterns, action sharpening UX) which are novel and less battle-tested. |
| Architecture | MEDIUM | Agent Framework handoff pattern and AG-UI FastAPI integration are HIGH confidence (official docs with Python examples). Mobile AG-UI client is MEDIUM confidence (custom implementation required, no production examples found). The 5-container Cosmos DB design and media-to-Blob pattern are HIGH confidence standard patterns. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls (Bag of Agents, Expo SSE blocking, async capture processing) are grounded in primary sources (GitHub issues, official docs, Agent Framework release notes). The "shelfware" pitfall is grounded in research on PKM failure patterns. Some cost estimates (17x error amplification) come from non-peer-reviewed articles — treat as directionally correct, not precise. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **React Native AG-UI client maturity**: Issue #510 is in-progress with no timeline. If it ships during Phase 1-2 development, evaluate adopting it. If not, the custom `react-native-sse` approach is validated and sufficient. Monitor monthly.
- **Agent Framework 1.0 GA timing**: The RC is API-stable and has all 1.0 features complete (per RC announcement). GA will follow but has no confirmed date. Build against the RC; the upgrade to GA should be a package version bump only. Pin to `1.0.0b260210` until GA ships.
- **GPT-5.2 pricing for multi-agent chains**: Actual cost per capture will only be known after Phase 1 usage. The pitfalls research flags 4 LLM calls per capture as the baseline. Monitor with per-agent token logging from day 1. If costs exceed $50/month, implement model tiering (GPT-4o-mini for Classifier).
- **Whisper accuracy for domain-specific vocabulary**: Medical technology terms, woodworking terminology, personal names. Cannot be assessed without testing. Phase 1 text-only validation avoids this; Phase 2 voice capture must be tested in real environments before committing to the Whisper-as-sole-transcription approach.
- **Cosmos DB partition key decision**: The research identifies `/userId` as functionally a constant (cardinality of 1), recommending evaluation of hierarchical partition keys (`/userId` + `/type`). This must be decided before Phase 1 data layer implementation — it cannot be changed without container recreation.

## Sources

### Primary (HIGH confidence)
- [Microsoft Agent Framework RC Announcement (Feb 18, 2026)](https://devblogs.microsoft.com/foundry/microsoft-agent-framework-reaches-release-candidate) — RC status, API stable
- [agent-framework on PyPI](https://pypi.org/project/agent-framework/) — Version 1.0.0b260210
- [AG-UI Integration with Agent Framework (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/) — Official AG-UI + FastAPI integration
- [Microsoft Agent Framework: Handoff Orchestration](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) — HandoffBuilder Python examples
- [AG-UI Protocol Overview](https://docs.ag-ui.com/introduction) — Protocol specification
- [Expo SDK 54 Changelog](https://expo.dev/changelog/sdk-54) — React Native 0.81, TextDecoderStream, New Architecture
- [azure-cosmos on PyPI](https://pypi.org/project/azure-cosmos/) — Version 4.14.0
- [azure-identity on PyPI](https://pypi.org/project/azure-identity/) — Version 1.16.1
- [CopilotKit React Native Support Issue #1892](https://github.com/CopilotKit/CopilotKit/issues/1892) — Confirms no native RN support
- [AG-UI React Native Client Issue #510](https://github.com/ag-ui-protocol/ag-ui/issues/510) — In-progress, no timeline
- [Expo SSE Blocking Issue #27526](https://github.com/expo/expo/issues/27526) — Confirmed bug in dev builds
- [Cosmos DB Partitioning (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning) — Partitioning patterns
- [Cosmos DB Anti-Patterns (Microsoft DevBlog)](https://devblogs.microsoft.com/cosmosdb/antipatterns-on-azure-cosmos-db/) — Official anti-patterns
- [OpenTelemetry AI Agent Observability](https://opentelemetry.io/blog/2025/ai-agent-observability/) — Official OpenTelemetry blog
- [Agent Framework Release Notes](https://github.com/microsoft/agent-framework/releases) — context_provider bug fix #3721

### Secondary (MEDIUM confidence)
- [Building an AI Agent Server with AG-UI and Microsoft Agent Framework (baeke.info)](https://baeke.info/2025/12/07/building-an-ai-agent-server-with-ag-ui-and-microsoft-agent-framework/) — Real-world AG-UI + Agent Framework implementation
- [Forte Labs: Test-Driving Second Brain Apps](https://fortelabs.com/blog/test-driving-a-new-generation-of-second-brain-apps-obsidian-tana-and-mem/) — Mem, Tana, Obsidian comparison
- [12 Common PKM Mistakes](https://www.dsebastien.net/12-common-personal-knowledge-management-mistakes-and-how-to-avoid-them/) — Anti-patterns informing anti-features section
- [17x Error Amplification in Multi-Agent Systems](https://towardsdatascience.com/why-your-multi-agent-system-is-failing-escaping-the-17x-error-trap-of-the-bag-of-agents/) — Research article
- [react-native-sse on npm](https://www.npmjs.com/package/react-native-sse) — SSE implementation for React Native
- [Buildin.AI: Best 15 Second Brain Apps in 2026](https://buildin.ai/blog/best-second-brain-apps) — Feature comparison

### Tertiary (LOW confidence — needs validation)
- azure-cosmos 4.14.0 version: Reported in Visual Studio Magazine article; validate with `uv pip install azure-cosmos` before assuming version.
- Azure OpenAI hidden cost estimates (15-40% above advertised): Community blog; use as directional warning, not precise budget.
- CopilotKit React Native support: Could not find evidence of official RN client beyond the open GitHub issue. Custom SSE client is the safe assumption.

---
*Research completed: 2026-02-21*
*Ready for roadmap: yes*
