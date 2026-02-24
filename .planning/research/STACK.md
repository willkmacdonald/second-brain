# Stack Research

**Domain:** Multi-agent personal knowledge management / second brain system
**Project:** Active Second Brain
**Researched:** 2026-02-21
**Confidence:** MEDIUM-HIGH (Agent Framework is Release Candidate, not GA; AG-UI protocol still evolving)

---

## Recommended Stack

### Core Technologies — Backend (Python)

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Microsoft Agent Framework (Python) | 1.0.0b260210 (RC) | Multi-agent orchestration, handoff patterns | The official Microsoft successor to Semantic Kernel + AutoGen. Unified Python/.NET API, built-in handoff/sequential/concurrent/group-chat orchestration, OpenTelemetry tracing, AG-UI integration. Released as RC on 2026-02-18 — API surface is stable and all 1.0 features complete. | HIGH |
| FastAPI | >=0.129.0 | HTTP API server, AG-UI SSE endpoint | Agent Framework's AG-UI integration (`agent-framework-ag-ui`) uses FastAPI natively via `add_agent_framework_fastapi_endpoint()`. ASGI = async, type hints, dependency injection. Already your default web framework. | HIGH |
| Azure OpenAI (via Agent Framework) | GPT-5.2 (2025-12-11) | LLM for all 7 agents | GPT-5.2 is GA on Azure AI Foundry since Dec 2025. Purpose-built for enterprise agent scenarios — structured outputs, reliable tool use, governed integrations. Agent Framework's `AzureOpenAIChatClient` connects directly. | HIGH |
| AG-UI Protocol (Python SDK) | ag-ui-protocol 0.1.11 | Frontend-backend streaming protocol | Open, lightweight, event-based protocol for real-time agent-to-UI communication over SSE. First-party integration with Agent Framework via `agent-framework-ag-ui` package. Pydantic models for all events. 3.9M monthly PyPI downloads — strong adoption. | MEDIUM |
| Python | >=3.12 | Runtime | Agent Framework requires 3.10+. Python 3.12 recommended for performance improvements (per-interpreter GIL, faster comprehensions). 3.13 acceptable if available. | HIGH |

### Core Technologies — Mobile (Expo/React Native)

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Expo SDK | 54 | Mobile app framework | Latest stable SDK (with React Native 0.81, React 19.1). New Architecture enabled by default. Precompiled RN for iOS = faster builds. `TextDecoderStream`/`TextEncoderStream` added to native runtime for fetch streaming (critical for SSE). | HIGH |
| React Native | 0.81 (via Expo SDK 54) | Cross-platform native UI | Bundled with Expo SDK 54. New Architecture is the only supported path going forward (Legacy removed in SDK 55). | HIGH |
| expo-router | v6 (via Expo SDK 54) | File-based navigation | Built into Expo SDK 54. File-based routing, typed routes, deep linking. Link previews, server middleware support. | HIGH |
| expo-audio | latest (via SDK 54) | Voice capture/recording | Replaces deprecated `expo-av` (removed in SDK 55). `useAudioRecorder` hook + `RecordingPresets`. The only supported audio library going forward. | HIGH |
| expo-camera | latest (via SDK 54) | Photo capture | `CameraView` component for photo/video. Config plugin support for permissions. | HIGH |
| react-native-sse | >=1.x | AG-UI SSE client | EventSource implementation for React Native. Uses XMLHttpRequest — no native module required. Works with Expo. Needed because React Native lacks native EventSource. | MEDIUM |

### Core Technologies — Azure Storage

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Azure Cosmos DB (NoSQL API) | Python SDK azure-cosmos >=4.14.0 | Document storage (captures, records, agent state) | Serverless mode for single-user = minimal cost. JSON-native, flexible schema for evolving capture types. Vector embedding support (4.7.0+) for future semantic search. Async client available. | HIGH |
| Azure Blob Storage | Python SDK azure-storage-blob >=12.27.1 | Media storage (voice recordings, photos) | Standard object storage for binary media. SAS token generation for mobile upload. Lifecycle policies for cost control. | HIGH |

### Core Technologies — Infrastructure

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Azure Container Apps | N/A (managed service) | Hosting the FastAPI + Agent backend | Scale-to-zero (single user = near-zero idle cost). Managed identity for Azure services. Custom domains with free managed TLS. Dapr sidecar available if needed. You already have ACA experience from prior projects. | HIGH |
| Azure Identity | azure-identity >=1.16.1 | Authentication to all Azure services | `DefaultAzureCredential` for local dev (az login) and production (managed identity). Single auth pattern across Cosmos, Blob, OpenAI. | HIGH |

### Supporting Libraries — Python Backend

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| agent-framework-core | 1.0.0b260210 | Core agent abstractions, chat clients | Always — base package for Agent, Message, tools |
| agent-framework-orchestrations | --pre | Workflow orchestration (Sequential, Handoff, etc.) | When composing multi-agent workflows (your 7-agent handoff pattern) |
| agent-framework-ag-ui | --pre | AG-UI FastAPI endpoint integration | When exposing agents via AG-UI protocol to the mobile app |
| pydantic | >=2.12.5 | Data validation, API models | Always — Agent Framework and AG-UI both depend on Pydantic v2 |
| pydantic-settings | >=2.13.1 | Environment variable configuration | For loading `.env` configuration cleanly |
| python-dotenv | >=1.0.0 | .env file loading | Local development env var loading |
| uvicorn | >=0.30.0 | ASGI server | Running the FastAPI app locally and in containers |
| gunicorn | >=22.0.0 | Production ASGI process manager | Production deployment with uvicorn workers |
| ruff | >=0.8.0 | Linting + formatting | Always — per your global CLAUDE.md preferences |
| pytest | >=8.0.0 | Testing framework | Always — for agent and integration tests |
| httpx | >=0.27.0 | Async HTTP client | Agent Framework uses httpx internally; also useful for testing AG-UI endpoints |
| opentelemetry-sdk | >=1.27.0 | Distributed tracing | Agent Framework has built-in OpenTelemetry support. Use for debugging multi-agent flows |

### Supporting Libraries — Mobile

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| expo-file-system | latest (SDK 54) | File operations | Handling captured media before upload. New API is now the default (old API at `expo-file-system/legacy`). |
| expo-secure-store | latest (SDK 54) | Secure credential storage | Storing user API tokens/auth tokens on device |
| expo-image | latest (SDK 54) | Optimized image display | Rendering captured photos and thumbnails in the app |
| @tanstack/react-query | >=5.x | Server state management | Caching and syncing capture data with backend |
| zustand | >=5.x | Client state management | Local UI state, capture queue management |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package management | Your preferred package manager. `uv pip install`, `uv venv`. |
| EAS Build | Expo cloud builds | For creating development and production builds. Free tier available. |
| Docker | Container builds | For building ACA container images locally. |
| Azure CLI | Azure resource management | `az containerapp up` for deployment. `az login` for local auth. |
| AG-UI Dojo | Agent testing UI | Interactive test environment at dojo.ag-ui.com. Clone AG-UI repo for local testing. |

---

## Installation

### Python Backend

```bash
# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Core Agent Framework (RC - requires --pre)
uv pip install agent-framework --pre

# Or selective install (lighter)
uv pip install agent-framework-core --pre
uv pip install agent-framework-orchestrations --pre
uv pip install agent-framework-ag-ui --pre

# Azure services
uv pip install azure-cosmos azure-storage-blob azure-identity

# Server
uv pip install fastapi uvicorn gunicorn

# Configuration
uv pip install pydantic-settings python-dotenv

# Observability
uv pip install opentelemetry-sdk opentelemetry-exporter-otlp

# Dev dependencies
uv pip install ruff pytest pytest-asyncio httpx
```

### Mobile App

```bash
# Create Expo project (SDK 54)
npx create-expo-app@latest active-second-brain --template blank-typescript

# Core dependencies
npx expo install expo-router expo-audio expo-camera expo-file-system expo-secure-store expo-image

# SSE client for AG-UI
npm install react-native-sse

# State management
npm install @tanstack/react-query zustand

# Dev dependencies
npm install -D typescript @types/react
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Microsoft Agent Framework | LangGraph (Python) | If you need more granular control over graph-based agent flows, or if Agent Framework 1.0 GA is delayed and you need production-ready now. LangGraph is mature and has its own AG-UI integration (`ag-ui-langgraph`). |
| Microsoft Agent Framework | CrewAI | If you want a more opinionated multi-agent framework with role-based agents. Less flexible than Agent Framework's handoff pattern but faster to prototype. |
| Microsoft Agent Framework | OpenAI Agents SDK | If you were using OpenAI directly (not Azure). The OpenAI Agents SDK (0.9.3) implements the Swarm/handoff pattern natively. Not ideal for Azure OpenAI. |
| AG-UI Protocol | Custom WebSocket | If you need full-duplex communication (e.g., real-time collaborative editing). AG-UI over SSE is simpler and sufficient for agent streaming. |
| Expo SDK 54 | React Native CLI + bare workflow | Only if you need native modules not supported by Expo. SDK 54 covers audio, camera, file system. Expo simplifies builds and OTA updates. |
| Azure Cosmos DB | Azure Table Storage | If your data is simple key-value and you want absolute minimum cost. Cosmos gives you richer queries, vector search, and future-proofing. |
| Azure Cosmos DB | PostgreSQL (Azure Flexible Server) | If you prefer SQL and relational modeling. Cosmos is better for flexible schemas and JSON documents typical of knowledge management. |
| react-native-sse | @copilotkit/react-native | CopilotKit does NOT have official React Native support (React + Angular only as of Feb 2026). Do not use for mobile. |
| zustand | Redux Toolkit | Only if you need middleware-heavy state management. Zustand is simpler for a single-user mobile app. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| AutoGen (standalone) | Deprecated. Merged into Microsoft Agent Framework. Migration guides available. AutoGen docs still exist but point to Agent Framework. | Microsoft Agent Framework |
| Semantic Kernel (standalone) | Merged into Agent Framework. Semantic Kernel was the "enterprise" path; Agent Framework is the convergence. | Microsoft Agent Framework |
| expo-av | Deprecated in SDK 53, removed from Expo Go. Will be fully removed in SDK 55. | expo-audio (recording), expo-video (playback) |
| CopilotKit for mobile | No React Native support. CopilotKit targets React web + Angular only. | Direct AG-UI SSE integration with react-native-sse |
| Flask/Django for API | No native async. Agent Framework requires async patterns (all agents are async). FastAPI is the only supported AG-UI integration. | FastAPI |
| LangChain (full framework) | Heavy, opinionated, unnecessary abstraction when using Agent Framework directly. Agent Framework already handles prompt management, tool calling, and orchestration. | Agent Framework + direct Azure OpenAI |
| firebase/react-native-firebase | Google ecosystem. Adds complexity when you are already on Azure. | Azure Cosmos DB + Blob Storage |
| API keys for Azure auth | Fragile, security risk, not rotatable via managed identity. | DefaultAzureCredential (azure-identity) |
| expo-file-system/legacy | Old API, will be removed in SDK 55. | expo-file-system (new default API in SDK 54) |
| JSC (JavaScriptCore) | First-party support removed from React Native 0.81. Community-maintained, no config plugin yet. | Hermes (default, bundled with React Native) |

---

## Stack Patterns by Variant

**For local development (Will's machine):**
- Use `AzureCliCredential` via `az login` (DefaultAzureCredential picks this up)
- Run FastAPI with `uvicorn server:app --reload --port 8000`
- Use Expo Go or dev client on physical device for mobile testing
- Cosmos DB emulator OR serverless tier for dev

**For production (Azure Container Apps):**
- Use managed identity (DefaultAzureCredential picks this up automatically on ACA)
- Run with `gunicorn -k uvicorn.workers.UvicornWorker`
- Scale-to-zero with min replicas = 0 (single user, intermittent usage)
- Custom domain with managed TLS certificate

**For AG-UI integration:**
- Backend: `add_agent_framework_fastapi_endpoint(app, agent, "/agent")` — one line
- Mobile: POST to `/agent` endpoint, consume SSE stream via `react-native-sse`
- Thread IDs maintained automatically by AG-UI protocol for conversation continuity

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| agent-framework 1.0.0b260210 | Python >=3.10 | Tested with 3.10, 3.11, 3.12. Recommend 3.12. |
| agent-framework 1.0.0b260210 | pydantic >=2.11.2 | ag-ui-protocol requires pydantic <3.0.0,>=2.11.2 |
| agent-framework-ag-ui --pre | FastAPI >=0.100.0 | Uses FastAPI's native SSE support |
| azure-cosmos >=4.14.0 | Python >=3.8 | Async client requires aiohttp |
| azure-storage-blob >=12.27.1 | Python >=3.8 | Supports service version 2026-02-06 |
| azure-identity >=1.16.1 | Python >=3.8 | DefaultAzureCredential chain |
| Expo SDK 54 | React Native 0.81, React 19.1 | New Architecture only (Legacy Architecture final in SDK 54) |
| Expo SDK 54 | Node >=20.19.4 | Minimum Node version bumped |
| Expo SDK 54 | TypeScript ~5.9.2 | Recommended TypeScript version |
| react-native-sse | Expo SDK 54 | JS-only, no native module needed |

---

## Key Architecture Decisions Driven by Stack

1. **Async everywhere in Python**: Agent Framework is fully async. FastAPI is async. Cosmos DB has async client. This is non-negotiable — every I/O operation must use `await`.

2. **AG-UI over SSE, not WebSockets**: The AG-UI protocol uses HTTP POST + SSE for streaming. This is simpler, firewall-friendly, and matches how Agent Framework's `agent-framework-ag-ui` package works. No WebSocket infrastructure needed.

3. **Handoff orchestration for 7 agents**: Agent Framework's `HandoffBuilder` or `SequentialBuilder` from `agent-framework-orchestrations` provides the pattern. Each agent gets `instructions` and `tools`, and the orchestrator manages delegation.

4. **Mobile captures go to Blob Storage first**: Voice recordings and photos upload directly to Azure Blob Storage (via SAS token generated by backend). Cosmos DB stores metadata + reference to blob URI. This keeps Cosmos costs low.

5. **Single FastAPI app serves everything**: One FastAPI application with multiple AG-UI endpoints (one per agent or one unified endpoint). No microservices needed for a single-user system.

---

## Sources

### HIGH Confidence (Official docs, PyPI, release announcements)
- [Microsoft Agent Framework RC Announcement (Feb 18, 2026)](https://devblogs.microsoft.com/foundry/microsoft-agent-framework-reaches-release-candidate) — RC status, API stable, 1.0 features complete
- [agent-framework on PyPI](https://pypi.org/project/agent-framework/) — Version 1.0.0b260210, Python >=3.10
- [AG-UI Integration with Agent Framework (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/) — Official AG-UI + FastAPI integration docs
- [AG-UI Getting Started (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/getting-started) — `agent-framework-ag-ui` package, SSE streaming, FastAPI endpoint
- [ag-ui-protocol on PyPI](https://pypi.org/project/ag-ui-protocol/) — Version 0.1.11, Pydantic >=2.11.2
- [GPT-5.2 on Azure AI Foundry (Dec 2025)](https://azure.microsoft.com/en-us/blog/introducing-gpt-5-2-in-microsoft-foundry-the-new-standard-for-enterprise-ai/) — GA availability
- [Expo SDK 54 Changelog](https://expo.dev/changelog/sdk-54) — React Native 0.81, React 19.1, TextDecoderStream support
- [azure-cosmos on PyPI](https://pypi.org/project/azure-cosmos/) — Version 4.14.0 with vector embeddings, semantic reranking
- [azure-storage-blob on PyPI](https://pypi.org/project/azure-storage-blob/) — Version 12.27.1 stable
- [azure-identity on PyPI](https://pypi.org/project/azure-identity/) — Version 1.16.1 stable
- [FastAPI on PyPI](https://pypi.org/project/fastapi/) — Version 0.129.0
- [Pydantic v2.12.5](https://pypi.org/project/pydantic/) — Latest stable

### MEDIUM Confidence (Community sources, blogs)
- [Building an AI Agent Server with AG-UI and Microsoft Agent Framework](https://baeke.info/2025/12/07/building-an-ai-agent-server-with-ag-ui-and-microsoft-agent-framework/) — Real-world AG-UI + Agent Framework implementation
- [Building Interactive Agent UIs with AG-UI (Microsoft Tech Community)](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-interactive-agent-uis-with-ag-ui-and-microsoft-agent-framework/4488249) — AG-UI patterns and architecture
- [react-native-sse on npm](https://www.npmjs.com/package/react-native-sse) — SSE implementation for React Native
- [AutoGen to Agent Framework Migration Guide](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/) — Handoff pattern documentation

### LOW Confidence (Needs validation)
- CopilotKit React Native support: Could not find evidence of official React Native client. Web (React) and Angular confirmed. Mobile AG-UI client must be custom-built with react-native-sse.
- azure-cosmos 4.14.0: Version reported by Visual Studio Magazine article (Oct 2025). PyPI page served cached 4.7.0 data. Validate with `uv pip install azure-cosmos` to confirm latest.

---

*Stack research for: Active Second Brain — multi-agent personal knowledge management system*
*Researched: 2026-02-21*
