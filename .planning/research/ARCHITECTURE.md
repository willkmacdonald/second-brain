# Architecture Research

**Domain:** Multi-agent personal knowledge management with mobile capture frontend
**Researched:** 2026-02-21
**Confidence:** MEDIUM — Agent Framework is pre-release (RC1 as of 2026-02-20); AG-UI Python integration is new; CopilotKit lacks native Expo support. Core patterns are documented by Microsoft, but real-world production examples with this exact stack are scarce.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CAPTURE LAYER (Mobile)                           │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Expo / React Native App                                        │   │
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐            │   │
│  │  │ Text   │  │ Voice  │  │ Photo/ │  │ Digest     │            │   │
│  │  │ Input  │  │ Record │  │ Video  │  │ Viewer     │            │   │
│  │  └───┬────┘  └───┬────┘  └───┬────┘  └─────┬──────┘            │   │
│  │      │            │           │              │                   │   │
│  │      └────────────┴─────┬─────┴──────────────┘                   │   │
│  │                         │                                        │   │
│  │                    AG-UI SSE Client                               │   │
│  │                  (react-native-sse)                               │   │
│  └─────────────────────────┬────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │ HTTP POST + SSE (AG-UI protocol)
                             │ API key in header
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AGENT LAYER (Azure Container Apps)                   │
│                                                                         │
│  ┌─── FastAPI + AG-UI Endpoint ──────────────────────────────────────┐  │
│  │  add_agent_framework_fastapi_endpoint(app, orchestrator, "/")     │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                             │                                           │
│  ┌──────────────────────────┴────────────────────────────────────────┐  │
│  │                    Handoff Workflow (Mesh)                         │  │
│  │                                                                    │  │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │  │
│  │  │ Orchestrator │───▶│  Perception  │───▶│  Classifier  │         │  │
│  │  │  (triage)    │    │ (media→text) │    │ (text→bucket)│         │  │
│  │  └──────┬───────┘    └──────────────┘    └──────┬───────┘         │  │
│  │         │                                        │                 │  │
│  │         │         ┌──────────────────┐          │                 │  │
│  │         │         │  Action Agent    │◀─────────┘                 │  │
│  │         │         │ (vague→concrete) │ (Projects/Admin only)      │  │
│  │         │         └──────────────────┘                            │  │
│  │         │                                                          │  │
│  │         ├──────────▶ Digest Agent (on-demand queries)              │  │
│  │         │                                                          │  │
│  │  ┌──────────────────────────────────────────────────────────┐     │  │
│  │  │  Background / Scheduled Agents (not in handoff mesh)     │     │  │
│  │  │  ┌────────────────────┐  ┌───────────────────────┐       │     │  │
│  │  │  │ Entity Resolution  │  │ Evaluation Agent      │       │     │  │
│  │  │  │ (nightly cron)     │  │ (weekly cron, Phase 4)│       │     │  │
│  │  │  └────────────────────┘  └───────────────────────┘       │     │  │
│  │  └──────────────────────────────────────────────────────────┘     │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─── OpenTelemetry ─────────────────────────────────────────────────┐  │
│  │  Traces across all agent handoffs (built into Agent Framework)    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
│   Azure OpenAI   │ │  Cosmos DB   │ │  Blob Storage    │
│   GPT-5.2        │ │  (NoSQL)     │ │  (media files)   │
│   Whisper        │ │  5 containers│ │  voice/photo/vid  │
│   Vision         │ │  /userId PK  │ │                  │
└──────────────────┘ └──────────────┘ └──────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Communicates With | Implementation |
|-----------|----------------|-------------------|----------------|
| **Expo App** | Capture text/voice/photo/video; display digests and HITL clarifications; stream agent handoff visibility | Agent Layer via AG-UI SSE | Expo SDK, `react-native-sse`, Expo Secure Store (API key), Expo AV (voice recording) |
| **FastAPI + AG-UI Endpoint** | Accept HTTP POST from mobile, stream SSE events back, route to Orchestrator agent | Expo App (SSE), Orchestrator Agent | `agent-framework-ag-ui`, FastAPI, `add_agent_framework_fastapi_endpoint()` |
| **Orchestrator Agent** | Triage incoming captures to the right specialist based on input type and content | Perception, Classifier, Digest, Action (via handoff) | `HandoffBuilder.with_start_agent(orchestrator)`, chat client agent with routing instructions |
| **Perception Agent** | Convert voice→text (Whisper), image/video→text (GPT-5.2 Vision) | Orchestrator (receives handoff), Classifier (hands off to), Blob Storage (reads media), Azure OpenAI | Agent with Whisper + Vision tools |
| **Classifier Agent** | Classify text into People/Projects/Ideas/Admin with confidence; file to Cosmos DB; trigger HITL if low confidence | Orchestrator (receives handoff), Action Agent (hands off to for Projects/Admin), Cosmos DB, User (HITL) | Agent with classification tools + Cosmos DB write tools |
| **Action Agent** | Sharpen vague project/admin captures into concrete next actions | Classifier (receives handoff), Cosmos DB (updates record) | Agent with action-sharpening instructions + Cosmos DB update tools |
| **Digest Agent** | Compose daily/weekly briefings; answer ad-hoc "what's on my plate" queries | Orchestrator (receives handoff for ad-hoc), Cosmos DB (reads all containers), Push notification service | Agent with Cosmos DB read tools, scheduled via cron |
| **Entity Resolution Agent** | Nightly merge of duplicate People records | Cosmos DB People container | Standalone agent, runs on schedule, not in handoff mesh |
| **Evaluation Agent** | Weekly system health report — handoff success rates, classification confidence distribution, capture volume | Cosmos DB, OpenTelemetry data | Phase 4, standalone scheduled agent |
| **Cosmos DB** | Persistent storage for all structured data (Inbox, People, Projects, Ideas, Admin) | All agents (read/write) | 5 containers, `/userId` partition key, serverless tier |
| **Blob Storage** | Store raw media files (voice recordings, photos, videos) | Perception Agent (reads), Expo App (uploads directly or via endpoint) | Container per media type or single container with virtual directories |
| **Azure OpenAI** | LLM inference (GPT-5.2), transcription (Whisper), vision analysis | All agents | `AzureOpenAIResponsesClient` via `agent-framework` |

## Recommended Project Structure

```
second-brain/
├── backend/                    # Python backend (Azure Container Apps)
│   ├── pyproject.toml          # uv project definition
│   ├── src/
│   │   └── second_brain/
│   │       ├── __init__.py
│   │       ├── main.py         # FastAPI app + AG-UI endpoint registration
│   │       ├── config.py       # Settings via pydantic-settings, env vars
│   │       ├── agents/         # Agent definitions
│   │       │   ├── __init__.py
│   │       │   ├── orchestrator.py   # Triage agent + handoff workflow builder
│   │       │   ├── perception.py     # Media → text conversion
│   │       │   ├── classifier.py     # Text → bucket classification
│   │       │   ├── action.py         # Vague → concrete actions
│   │       │   ├── digest.py         # Daily/weekly briefings
│   │       │   ├── entity_resolution.py  # Nightly People merge
│   │       │   └── evaluation.py     # Weekly system health (Phase 4)
│   │       ├── tools/          # @tool functions shared across agents
│   │       │   ├── __init__.py
│   │       │   ├── cosmos.py         # Cosmos DB CRUD operations
│   │       │   ├── blob.py           # Blob Storage read/upload
│   │       │   ├── transcription.py  # Whisper transcription
│   │       │   └── vision.py         # GPT Vision analysis
│   │       ├── models/         # Pydantic models for data
│   │       │   ├── __init__.py
│   │       │   ├── capture.py        # Inbox item schema
│   │       │   ├── people.py         # People record
│   │       │   ├── project.py        # Project record
│   │       │   ├── idea.py           # Idea record
│   │       │   └── admin.py          # Admin record
│   │       └── scheduling/     # Cron job definitions
│   │           ├── __init__.py
│   │           └── jobs.py           # Digest, entity resolution, evaluation schedules
│   ├── tests/
│   └── Dockerfile
├── mobile/                     # Expo React Native app
│   ├── app/                    # Expo Router file-based routing
│   │   ├── (tabs)/             # Tab navigation
│   │   │   ├── capture.tsx     # Main capture screen
│   │   │   ├── digest.tsx      # Digest viewer
│   │   │   └── history.tsx     # Past captures (Phase 3+)
│   │   └── _layout.tsx
│   ├── components/
│   │   ├── AgentStream.tsx     # AG-UI SSE client + event rendering
│   │   ├── CaptureButton.tsx   # One-tap capture
│   │   ├── VoiceRecorder.tsx   # Voice capture
│   │   └── MediaCapture.tsx    # Photo/video capture
│   ├── services/
│   │   ├── agui-client.ts      # AG-UI protocol client (HTTP POST + SSE parsing)
│   │   ├── api.ts              # Non-streaming API calls (media upload)
│   │   └── storage.ts          # Expo Secure Store for API key
│   ├── app.json
│   └── package.json
├── infra/                      # Azure infrastructure
│   ├── main.bicep              # Azure Container Apps, Cosmos DB, Blob Storage, OpenAI
│   └── parameters.json
└── .planning/                  # GSD planning files
```

### Structure Rationale

- **backend/src/second_brain/agents/**: Each agent is a module containing its agent definition, instructions, and handoff configuration. The Orchestrator module imports all others and wires the HandoffBuilder.
- **backend/src/second_brain/tools/**: Shared `@tool` functions that multiple agents use (e.g., `cosmos.py` is used by Classifier, Action, Digest, Entity Resolution). Agent Framework `@tool` decorator makes these callable by agents.
- **backend/src/second_brain/models/**: Pydantic models define the Cosmos DB document schemas. Used for validation both when writing to Cosmos and when returning data to the app.
- **mobile/services/agui-client.ts**: Custom AG-UI SSE client because CopilotKit does not yet support React Native/Expo natively (GitHub issue #1892 is open but unresolved). Uses `react-native-sse` for the SSE transport layer.
- **Monorepo**: Backend and mobile in one repo simplifies development for a solo developer. No need for a separate packages/ workspace pattern at this scale.

## Architectural Patterns

### Pattern 1: Handoff Orchestration (Mesh Topology)

**What:** Microsoft Agent Framework's `HandoffBuilder` creates a mesh of agents where each agent can transfer full task ownership to another. The Orchestrator is the `start_agent` that receives all user input. Unlike agent-as-tools (where a primary agent delegates subtasks and retains ownership), handoff transfers complete control — the receiving agent owns the conversation.

**When to use:** When specialist agents need full context and autonomy to complete their piece of the pipeline. The Second Brain capture flow is inherently sequential: Orchestrator triages → Perception transcribes → Classifier files → Action sharpens. Each handoff passes full context.

**Trade-offs:**
- Pro: Clean separation of concerns; each agent has focused instructions and tools
- Pro: HITL built into the pattern — when an agent doesn't hand off, it requests user input (perfect for Classifier's low-confidence clarification)
- Con: All agents share full conversation history (context synchronization broadcasts all messages). For 7 agents, this means message volume grows. Mitigate by keeping agent responses concise.
- Con: Handoff is interactive by default — if an agent doesn't call a handoff tool, the workflow pauses for human input. This is desirable for HITL but requires care in the "happy path" to ensure agents always hand off when they should.

**Example:**

```python
from agent_framework.orchestrations import HandoffBuilder

workflow = (
    HandoffBuilder(
        name="capture_pipeline",
        participants=[orchestrator, perception, classifier, action, digest],
    )
    .with_start_agent(orchestrator)
    # Orchestrator routes to Perception (media) or Classifier (text)
    .add_handoff(orchestrator, [perception, classifier, digest])
    # Perception always hands off to Classifier after transcription
    .add_handoff(perception, [classifier])
    # Classifier hands off to Action for Projects/Admin, or terminates
    .add_handoff(classifier, [action])
    # Action terminates after sharpening (no further handoff needed)
    .add_handoff(action, [])
    .build()
)
```

**Confidence:** HIGH — This is documented directly in [Microsoft Learn: Handoff Orchestration](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) with Python code examples.

### Pattern 2: AG-UI SSE Streaming (Server → Mobile)

**What:** The AG-UI protocol uses HTTP POST to send user messages and Server-Sent Events (SSE) to stream agent responses back. The Agent Framework provides `add_agent_framework_fastapi_endpoint()` which wraps a FastAPI endpoint that handles the full protocol: receiving messages, executing the agent/workflow, and streaming AG-UI events (RUN_STARTED, TEXT_MESSAGE_CONTENT, TOOL_CALL_START, etc.) back to the client.

**When to use:** For real-time visibility into agent processing. The mobile app sees which agent is active, what it's doing, and when it completes — not just a final result after a black-box delay.

**Trade-offs:**
- Pro: Open standard protocol with defined event types; framework handles event bridging automatically
- Pro: Thread IDs maintain conversation context across requests (essential for HITL follow-ups)
- Pro: SSE is firewall-friendly (regular HTTP), unlike WebSockets
- Con: CopilotKit (the primary AG-UI frontend framework) does not support React Native/Expo natively. Must build a custom SSE client using `react-native-sse`.
- Con: Known Expo issue: `ExpoRequestCdpInterceptor` can block SSE streams in dev mode (GitHub expo/expo#27526). Workaround: use `expo/fetch` polyfill.

**Example (server):**

```python
from fastapi import FastAPI
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint

app = FastAPI()
add_agent_framework_fastapi_endpoint(app, workflow, "/")
```

**Example (mobile — custom AG-UI SSE client):**

```typescript
import EventSource from 'react-native-sse';

function sendCapture(text: string, threadId?: string) {
  const es = new EventSource('https://api.example.com/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      messages: [{ role: 'user', content: text }],
      threadId,
    }),
  });

  es.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    switch (data.type) {
      case 'RUN_STARTED':
        setThreadId(data.threadId); // Persist for HITL follow-ups
        break;
      case 'TEXT_MESSAGE_CONTENT':
        appendDelta(data.delta);     // Stream text to UI
        break;
      case 'TOOL_CALL_START':
        showAgentActivity(data);     // "Classifier is analyzing..."
        break;
      case 'RUN_FINISHED':
        es.close();
        break;
    }
  });
}
```

**Confidence:** HIGH for server side (documented in [Microsoft Learn: AG-UI Getting Started](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started)). MEDIUM for mobile client (custom implementation needed; no official Expo AG-UI client exists).

### Pattern 3: Media Upload → Blob Storage → Perception Agent

**What:** Binary media (voice recordings, photos, videos) are uploaded to Azure Blob Storage first, then the Perception Agent is given a blob URL to process. This avoids sending large binary payloads through the AG-UI SSE channel.

**When to use:** Any capture that isn't plain text. Voice recordings from Expo AV, photos from the camera.

**Trade-offs:**
- Pro: Decouples media transport from agent conversation; AG-UI carries lightweight text/JSON only
- Pro: Blob Storage handles large files efficiently; async upload from Expo
- Pro: Perception Agent can re-process media if needed (URL persists)
- Con: Two-step flow (upload blob → send blob URL to agent) adds latency
- Con: Need to handle upload failures separately from agent failures

**Flow:**
```
Expo App                     Azure                      Agent Layer
   │                           │                            │
   │──── Upload media ────────▶│ Blob Storage               │
   │◀─── Return blob URL ──────│                            │
   │                           │                            │
   │──── POST {blobUrl} ──────────────────────────────────▶│ FastAPI
   │◀─── SSE stream ──────────────────────────────────────│ Orchestrator
   │     (RUN_STARTED,         │                            │──▶ Perception
   │      agent updates,       │     ◀── Read blob ─────────│    (Whisper/Vision)
   │      RUN_FINISHED)        │                            │──▶ Classifier
   │                           │                            │
```

**Confidence:** HIGH — Standard Azure pattern. `azure-storage-blob` async SDK is mature.

### Pattern 4: Cosmos DB Container-per-Bucket

**What:** Five Cosmos DB containers map directly to the data model: `Inbox`, `People`, `Projects`, `Ideas`, `Admin`. All partitioned by `/userId` (always `"will"` for this single-user system). The Inbox container is a transient staging area; items move to their final container after classification.

**When to use:** When data access patterns are bucket-centric (queries within a single bucket, not cross-bucket joins) and the schema differs across buckets.

**Trade-offs:**
- Pro: Clean mapping to the domain model; each container has its own schema
- Pro: `/userId` partition key means all data for a single user is in one logical partition — point reads are maximally efficient
- Pro: Serverless Cosmos DB pricing is ideal for single-user with bursty usage
- Con: Cross-container queries require multiple round trips (e.g., Digest Agent querying all four final containers)
- Con: Single partition key (`"will"`) means no horizontal scaling benefit — acceptable for single-user

**Example (tool for agents):**

```python
from azure.cosmos.aio import CosmosClient
from typing import Annotated
from agent_framework import tool

@tool
async def create_record(
    container_name: Annotated[str, "Target container: People, Projects, Ideas, or Admin"],
    record: Annotated[dict, "The record to create with required fields"],
) -> str:
    """Create a new record in the specified Cosmos DB container."""
    async with CosmosClient(endpoint, credential) as client:
        database = client.get_database_client("second-brain")
        container = database.get_container_client(container_name)
        result = await container.create_item(body={**record, "userId": "will"})
        return f"Created record {result['id']} in {container_name}"
```

**Confidence:** HIGH — Standard Cosmos DB pattern. [Microsoft Learn: Partitioning](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning) documents this approach.

## Data Flow

### Primary Capture Flow

```
User taps "Capture" in Expo App
    │
    ├── [Text] ──────────────────────────────────────────────────────────┐
    │                                                                     │
    ├── [Voice] ── Upload .m4a to Blob Storage ── Get blob URL ──────────┤
    │                                                                     │
    ├── [Photo] ── Upload .jpg to Blob Storage ── Get blob URL ──────────┤
    │                                                                     │
    └── [Video] ── Upload .mp4 to Blob Storage ── Get blob URL ──────────┤
                                                                          │
    HTTP POST to AG-UI endpoint (message + optional blob URL)             │
    ◀─────────────────────────────────────────────────────────────────────┘
         │
         ▼
    Orchestrator Agent (triage)
         │
         ├── Text input ──────────────────▶ Classifier Agent
         │                                       │
         └── Media input ──▶ Perception Agent    │
                                  │               │
                            (Whisper/Vision)       │
                                  │               │
                                  └──▶ Classifier Agent
                                            │
                                    Classify into bucket
                                            │
                                ┌───────────┼───────────┐
                                ▼           ▼           ▼
                          ┌─ High confidence ─┐   Low confidence
                          │                    │        │
                          ▼                    ▼        ▼
                    Projects/Admin         People/   HITL: request
                          │                Ideas     clarification
                          ▼                  │     from user via
                    Action Agent             │     AG-UI event
                    (sharpen into            │        │
                     next actions)           │        ▼
                          │                  │   User responds
                          ▼                  ▼        │
                    Write to Cosmos DB ◀──────────────┘
                    (final container)
                          │
                          ▼
                    RUN_FINISHED → SSE → Expo App shows confirmation
```

### Digest Flow

```
Scheduled trigger (6:30 AM CT daily / Sunday 9 AM weekly)
    OR
User asks "What's on my plate?" via Expo App
    │
    ▼
Digest Agent
    │
    ├── Read Projects container (active items, next actions)
    ├── Read People container (recent interactions, follow-ups)
    ├── Read Ideas container (recent captures)
    └── Read Admin container (pending tasks, deadlines)
    │
    ▼
Compose briefing (<150 words for daily)
    │
    ├── [Scheduled] ──▶ Push notification → Expo App
    └── [Ad-hoc] ──▶ SSE stream → Expo App (via AG-UI)
```

### Entity Resolution Flow (Nightly)

```
Cron trigger (nightly, e.g., 2 AM CT)
    │
    ▼
Entity Resolution Agent
    │
    ├── Read all People records from Cosmos DB
    ├── Identify duplicates (fuzzy name matching, overlapping context)
    ├── Merge records (keep most complete, link alternates)
    └── Write merged records back to Cosmos DB
    │
    ▼
Log results (merged count, skipped, conflicts)
```

### Key Data Flows

1. **Capture → Storage:** User input reaches Cosmos DB through a chain of 2-4 agents, each adding value (transcription, classification, action sharpening). The Inbox container holds the raw capture; the final container holds the classified, enriched record.
2. **Storage → Digest:** The Digest Agent pulls from all 4 final containers to compose briefings. This is a read-heavy fan-out pattern across containers.
3. **HITL Loop:** When the Classifier's confidence is low, the handoff workflow pauses and emits a `request_info` event. The AG-UI protocol carries this back to the Expo app as a message requiring user response. The user's reply flows back through HTTP POST → workflow resume.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user (current) | Single Container App instance (0.25 vCPU, 0.5 GB). Cosmos DB serverless. No caching needed. Total cost: ~$5-15/month. |
| 2-5 users | Add `/userId` filtering to all queries (already partitioned). Add authentication (swap API key for Azure AD). Minimal code changes. |
| 10+ users | Won't happen — this is explicitly single-user. If it did: move to provisioned Cosmos DB throughput, add response caching for digest queries, scale Container Apps horizontally. |

### Scaling Priorities

1. **First bottleneck:** LLM latency (GPT-5.2 calls). Each capture traverses 2-4 agents, each making at least one LLM call. Mitigate with concise agent instructions, streaming (already via AG-UI), and avoiding unnecessary handoffs.
2. **Second bottleneck:** Cosmos DB cold starts on serverless tier. First query after idle period has higher latency. Acceptable for single-user hobby project.

## Anti-Patterns

### Anti-Pattern 1: Sending Binary Media Through AG-UI

**What people do:** Encode voice recordings or images as base64 in the AG-UI message payload.
**Why it's wrong:** AG-UI is designed for lightweight JSON events over SSE. Large payloads block the stream, increase latency, and may exceed size limits. Agent Framework broadcasts messages to all agents in the handoff mesh — sending a 2MB voice recording to all 7 agents wastes context window tokens and increases cost.
**Do this instead:** Upload media to Blob Storage first. Send only the blob URL through AG-UI. The Perception Agent fetches the blob directly.

### Anti-Pattern 2: One Giant Agent Instead of Specialists

**What people do:** Build a single agent with huge instructions covering triage, classification, action sharpening, and digests, relying on one LLM call to do everything.
**Why it's wrong:** Instructions become unwieldy; the model loses focus. No observability into which "step" failed. No ability to add HITL at specific points. Defeats the learning goal of this project.
**Do this instead:** Use the handoff pattern with focused specialists. Each agent has a clear, testable responsibility.

### Anti-Pattern 3: Using CopilotKit Directly in Expo

**What people do:** Try to use CopilotKit's React hooks (`useCopilotChat`, `useAgent`) directly in a React Native/Expo app.
**Why it's wrong:** CopilotKit does not support React Native natively (GitHub issue CopilotKit/CopilotKit#1892). It depends on browser APIs (DOM, `EventSource`, `fetch` with streaming) that don't exist in React Native's JavaScript runtime. Polyfills are fragile.
**Do this instead:** Build a thin custom AG-UI SSE client using `react-native-sse`. The AG-UI protocol is simple enough (HTTP POST + SSE event parsing) that a purpose-built client is more reliable than fighting CopilotKit polyfills.

### Anti-Pattern 4: Putting Scheduled Agents in the Handoff Mesh

**What people do:** Include Entity Resolution and Evaluation agents in the HandoffBuilder workflow so the Orchestrator can "hand off" to them.
**Why it's wrong:** These agents run on schedules (nightly, weekly), not in response to user captures. Including them in the mesh means they receive every message broadcast (wasted context), and the Orchestrator gets confused about when to route to them.
**Do this instead:** Run Entity Resolution and Evaluation as standalone agents triggered by cron jobs (Azure Container Apps scheduled tasks or APScheduler within the FastAPI process). They share the same Cosmos DB tools but are not participants in the handoff workflow.

### Anti-Pattern 5: Shared Cosmos DB Client Across Requests

**What people do:** Create a single `CosmosClient` instance per request (or worse, create a new one per tool call).
**Why it's wrong:** Each `CosmosClient` manages its own connection pool and TCP connections. Creating per-request wastes resources and causes connection churn.
**Do this instead:** Initialize a single `CosmosClient` at application startup (FastAPI `lifespan` event) and inject it into agent tools via dependency injection or module-level singleton. The async `CosmosClient` from `azure.cosmos.aio` is designed for this pattern — it's thread-safe and manages connection pooling internally.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Azure OpenAI (GPT-5.2) | `AzureOpenAIResponsesClient` from `agent-framework` with `AzureCliCredential` (dev) or `ManagedIdentityCredential` (prod) | All agents share one client instance. API version must match deployment. |
| Azure OpenAI (Whisper) | Whisper transcription endpoint via Azure OpenAI Python SDK | Perception Agent calls this as a tool. Input: blob URL or audio bytes. |
| Cosmos DB (NoSQL) | `azure-cosmos` async SDK (`azure.cosmos.aio.CosmosClient`) | Singleton client, 5 container references. Point reads by `id + userId`. |
| Blob Storage | `azure-storage-blob` async SDK (`azure.storage.blob.aio.BlobServiceClient`) | Expo uploads media; Perception Agent reads media. SAS tokens for mobile upload. |
| Push Notifications | Expo Push Notification service (free tier) | Digest Agent sends push for scheduled briefings and HITL clarification requests. |
| OpenTelemetry | Built into Agent Framework; export to Azure Monitor / Application Insights | Zero-config tracing across handoffs. Add custom spans for Cosmos DB and Blob operations. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Expo App ↔ Agent Layer | AG-UI protocol (HTTP POST + SSE) | The only external API surface. Protected by API key header. |
| Agent Layer ↔ Cosmos DB | `azure-cosmos` async SDK (direct TCP) | Agents use shared `@tool` functions. No ORM — direct document operations. |
| Agent Layer ↔ Blob Storage | `azure-storage-blob` async SDK (HTTPS) | Perception Agent reads; Expo App writes (via SAS token or upload endpoint). |
| Agent ↔ Agent (handoff mesh) | Agent Framework internal (in-process message passing + context broadcast) | All within the same FastAPI process. No network calls between agents. |
| Scheduled Agents ↔ Cosmos DB | Same `@tool` functions, triggered by scheduler | Same process, same Cosmos client, different trigger mechanism. |

## Build Order (Dependencies Between Components)

The architecture implies this build sequence:

1. **FastAPI shell + single agent + AG-UI endpoint** — Prove the stack works: one agent that echoes input back via AG-UI SSE. Validates `agent-framework-ag-ui`, FastAPI, and SSE streaming.

2. **Cosmos DB data layer + Pydantic models** — Define the 5 container schemas, implement `@tool` CRUD functions. Required by every subsequent agent.

3. **Expo app with custom AG-UI client** — Build the mobile capture surface with `react-native-sse`. Connect to the FastAPI endpoint. Validates the full mobile → agent → response loop.

4. **Orchestrator + Classifier agents** — Wire the HandoffBuilder with Orchestrator routing text to Classifier. Classifier writes to Cosmos DB. This is the minimum viable capture pipeline.

5. **Perception Agent + Blob Storage** — Add voice and photo capture. Expo uploads to Blob Storage, sends URL to Orchestrator, which hands off to Perception, then Classifier.

6. **Action Agent** — Add to the handoff mesh. Classifier hands off Projects/Admin captures for action sharpening.

7. **HITL clarification loop** — Implement low-confidence handling: Classifier pauses, AG-UI streams clarification request to Expo, user responds, workflow resumes.

8. **Digest Agent** — Scheduled daily/weekly briefings + ad-hoc queries. Requires data in Cosmos DB from prior steps.

9. **Entity Resolution Agent** — Nightly People merge. Requires accumulated People data.

10. **Evaluation Agent** — Weekly health reports. Requires weeks of operational data + OpenTelemetry traces.

**Key dependency:** Steps 1-3 are the foundation and can partially overlap (backend and mobile can develop in parallel once the AG-UI contract is agreed). Steps 4-7 are the core capture pipeline and must be sequential. Steps 8-10 are additive and depend on data accumulation.

## Sources

- [Microsoft Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/) — HIGH confidence
- [Microsoft Agent Framework: Handoff Orchestration](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) — HIGH confidence, includes Python examples
- [AG-UI Integration with Agent Framework](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/) — HIGH confidence, official Microsoft docs
- [AG-UI Getting Started (Python)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started) — HIGH confidence, `add_agent_framework_fastapi_endpoint` API documented
- [AG-UI Protocol Overview](https://docs.ag-ui.com/introduction) — HIGH confidence, protocol specification
- [AG-UI Event Types](https://docs.ag-ui.com/concepts/events) — HIGH confidence, all 17+ event types documented
- [Agent Framework GitHub Repository](https://github.com/microsoft/agent-framework) — HIGH confidence, 51% Python codebase
- [CopilotKit React Native Support Issue #1892](https://github.com/CopilotKit/CopilotKit/issues/1892) — HIGH confidence, confirms no native RN support
- [react-native-sse npm package](https://www.npmjs.com/package/react-native-sse) — MEDIUM confidence, community package for SSE in RN
- [Expo SSE Issue #27526](https://github.com/expo/expo/issues/27526) — MEDIUM confidence, known dev-mode SSE blocker
- [Azure Cosmos DB Partitioning](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning) — HIGH confidence
- [Azure Cosmos DB Python SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/cosmos-readme) — HIGH confidence
- [Azure Blob Storage Python Upload](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-upload-python) — HIGH confidence

---
*Architecture research for: The Active Second Brain — multi-agent personal knowledge management*
*Researched: 2026-02-21*
