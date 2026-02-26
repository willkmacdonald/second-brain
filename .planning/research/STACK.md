# Stack Research

**Domain:** Multi-agent personal knowledge management / second brain system
**Project:** Active Second Brain — Foundry Agent Service Migration
**Researched:** 2026-02-25
**Confidence:** HIGH for packages and versions; MEDIUM for orchestration strategy (Connected Agents vs HandoffBuilder interaction requires validation)

---

## Context: What This Covers

This is a migration-focused stack update. The existing validated stack (FastAPI, Expo/React Native, Cosmos DB, Blob Storage, Azure Container Apps, Ruff, uv) is unchanged. This document covers **only what changes or gets added** for the migration from `AzureOpenAIChatClient` + `HandoffBuilder` (local orchestration) to `AzureAIAgentClient` (Azure AI Foundry Agent Service) with Connected Agents, persistent agents, server-managed threads, and Application Insights observability.

---

## Packages: What Changes

### Add These Packages

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `agent-framework-azure-ai` | `1.0.0rc1` (RC, install `--pre`) | Provides `AzureAIAgentClient` and `AzureAIProjectAgentProvider` | The Agent Framework package that wires the Python framework to the Foundry Agent Service. Not included in the base `agent-framework-core`. Promoted to RC alongside `agent-framework-core` on Feb 19, 2026. |
| `azure-ai-projects` | `1.0.0` (GA) | `AIProjectClient` for agent lifecycle management (create, delete, list persistent agents and threads) | Required for managing agent resources in Foundry. The `AzureAIAgentClient` can accept a pre-created `AIProjectClient` for lifecycle control. Released July 2025 as stable GA. |
| `azure-ai-agents` | `1.1.0` (GA) | Lower-level Foundry Agents SDK (threads, runs, messages, `ConnectedAgentTool`) | Pulled in transitively by `azure-ai-projects` but pin it explicitly for `ConnectedAgentTool` model imports. Released August 2025 as GA. |
| `azure-monitor-opentelemetry` | `1.8.6` (GA) | Application Insights via OpenTelemetry distro (`configure_azure_monitor()`) | One-call setup for traces, logs, and metrics routed to Application Insights. The official Azure Monitor distro supercedes the deprecated `azure-monitor-opentelemetry-distro` package. Released February 4, 2026. |

### Keep These Packages (No Change)

| Package | Notes |
|---------|-------|
| `agent-framework-core` | Still required — provides `Agent`, `Message`, `tool`, `HandoffBuilder`, sessions |
| `agent-framework-orchestrations` | Still required — `HandoffBuilder` remains the local orchestration layer |
| `agent-framework-ag-ui` | Still required — AG-UI SSE endpoint unchanged |
| `azure-identity` | Still required — `DefaultAzureCredential` / `AzureCliCredential` |
| `azure-cosmos`, `azure-storage-blob`, `azure-keyvault-secrets` | All unchanged |
| `openai` | Still required for Whisper transcription (separate from Agent Framework) |
| `fastapi`, `uvicorn`, `aiohttp` | Unchanged |
| `pydantic-settings`, `python-dotenv` | Note: Agent Framework RC dropped `pydantic-settings` from its own internals (replaced with TypedDict + `load_settings()`), but your own `Settings` class still uses `pydantic-settings` normally |

### Remove or Avoid

| Package | Why |
|---------|-----|
| Nothing is removed from `pyproject.toml` | The migration adds packages; existing packages stay |
| `azure-monitor-opentelemetry-distro` | Deprecated name — the current package is `azure-monitor-opentelemetry` |

---

## pyproject.toml Changes

```toml
dependencies = [
    # Agent Framework + AG-UI (RC - requires --prerelease=allow)
    "agent-framework-ag-ui",
    "agent-framework-orchestrations",
    # NEW: Foundry Agent Service integration
    "agent-framework-azure-ai",
    # Azure services (existing)
    "azure-cosmos",
    "azure-identity",
    "azure-keyvault-secrets",
    "azure-storage-blob",
    # NEW: Foundry Agent lifecycle management
    "azure-ai-projects>=1.0.0",
    "azure-ai-agents>=1.1.0",
    # NEW: Application Insights via OTel distro
    "azure-monitor-opentelemetry>=1.8.6",
    # Unchanged
    "aiohttp",
    "python-multipart",
    "pydantic-settings",
    "python-dotenv",
]
```

Install:

```bash
uv pip install agent-framework-azure-ai --prerelease=allow
uv pip install "azure-ai-projects>=1.0.0" "azure-ai-agents>=1.1.0"
uv pip install "azure-monitor-opentelemetry>=1.8.6"
```

---

## Azure Resources: What Must Be Provisioned

This is the most significant non-code change. Foundry Agent Service requires a **Microsoft Foundry resource** (new type), not a hub-based project.

### New Azure Resources Required

| Resource | Type | Notes |
|----------|------|-------|
| Microsoft Foundry Account | `Microsoft.CognitiveServices/accounts` | New resource type (NOT the old `Microsoft.MachineLearningServices/workspaces` Hub). Created via Foundry portal or `az cognitiveservices account create`. |
| Foundry Project | Child of the Foundry Account | Provides the project endpoint in the format `https://<account>.services.ai.azure.com/api/projects/<project>` |
| Model Deployment | GPT-5.2 or gpt-4o | Deployed within the Foundry project. The deployment name becomes `MODEL_DEPLOYMENT_NAME` env var. |
| Application Insights | `Microsoft.Insights/components` | Connected to the Container App for observability. Connection string goes in env var `APPLICATIONINSIGHTS_CONNECTION_STRING`. |

### RBAC Roles Required

| Role | Scope | Purpose |
|------|-------|---------|
| `Azure AI User` | Foundry Project scope | Required for creating/running agents. Minimum: `agents/*/read`, `agents/*/action`, `agents/*/delete` |
| `Azure AI Account Owner` (or Contributor) | Subscription scope | Required for the identity that creates the Foundry resource and project |

### Environment Variables: New Additions

| Variable | Format | Source |
|----------|--------|--------|
| `AZURE_AI_PROJECT_ENDPOINT` | `https://<account>.services.ai.azure.com/api/projects/<project>` | Foundry portal → Project overview → Libraries → Foundry |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | e.g. `gpt-4o` or `gpt-5.2-2025-12-11` | Foundry portal → Models + Endpoints |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `InstrumentationKey=...;IngestionEndpoint=...` | Azure portal → Application Insights → Overview |

**Existing variables that stay:**

`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `COSMOS_*`, `AZURE_STORAGE_*`, `KEY_VAULT_URI` — all unchanged (AzureOpenAIChatClient for non-Foundry agents, Cosmos, Blob all continue using their existing env vars).

---

## SDK Integration Points

### AzureAIAgentClient vs AzureOpenAIChatClient

| Aspect | `AzureOpenAIChatClient` (current) | `AzureAIAgentClient` (migration target) |
|--------|----------------------------------|----------------------------------------|
| Package | `agent-framework-core` | `agent-framework-azure-ai` |
| Thread management | Local (in-memory `AgentSession`) | Server-side (Foundry stores threads in the service) |
| Agent persistence | Ephemeral (recreated per request) | Persistent (agent has a stable ID in Foundry) |
| Credential param | `credential=` (since RC1 unified cred) | `credential=` (same unified pattern) |
| Import | `from agent_framework.azure import AzureOpenAIChatClient` | `from agent_framework.azure import AzureAIAgentClient` |
| HandoffBuilder compat | Fully supported | Conditionally supported — resolved as of Feb 9, 2026 (issue #3097 closed). Validate with RC2. |
| Runtime tool override | Supported | NOT supported — tools are set at agent creation time. Foundry logs a warning if you try. Use `AzureOpenAIResponsesClient` if dynamic tool overrides are needed. |
| Connected Agents | Not applicable | Supported via `ConnectedAgentTool` from `azure-ai-agents` |

### AzureAIAgentClient: Core Usage Pattern

```python
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

# Simplest form: uses AZURE_AI_PROJECT_ENDPOINT + AZURE_AI_MODEL_DEPLOYMENT_NAME env vars
async with (
    DefaultAzureCredential() as credential,
    AzureAIAgentClient(credential=credential).as_agent(
        name="TriageAgent",
        instructions="You are a capture triage agent...",
        tools=[my_tool],
    ) as agent,
):
    result = await agent.run("Classify this capture")
```

### Connected Agents Pattern (multi-agent orchestration)

Used when the Foundry service manages delegation — the parent agent calls subagents as tools.

```python
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ConnectedAgentTool
from azure.identity.aio import DefaultAzureCredential

async with (
    DefaultAzureCredential() as credential,
    AIProjectClient(
        endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=credential,
    ) as project_client,
):
    # Create a persistent subagent
    voice_agent = await project_client.agents.create_agent(
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        name="voice_classifier",
        instructions="You classify voice captures into knowledge categories.",
    )

    # Wire it as a tool for the parent agent
    connected_voice = ConnectedAgentTool(
        id=voice_agent.id,
        name="voice_classifier",
        description="Classifies voice captures into categories",
    )

    # Parent agent with Connected Agent tool
    parent_agent = await project_client.agents.create_agent(
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        name="triage_orchestrator",
        instructions="Route captures to specialist agents.",
        tools=connected_voice.definitions,
    )
```

**CRITICAL LIMITATION:** Connected Agents have a maximum depth of 2. A parent agent can have multiple subagent siblings, but subagents cannot have their own subagents. Exceeding this depth results in `Assistant Tool Call Depth Error`. For 7 agents with hierarchy deeper than parent + siblings, use HandoffBuilder (client-side) instead of Connected Agents (server-side).

### Application Insights: One-Line Setup

```python
from azure.monitor.opentelemetry import configure_azure_monitor

# Called once at app startup (before FastAPI app creation)
configure_azure_monitor(
    connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"]
)
```

Agent Framework's existing OpenTelemetry integration automatically routes spans to Application Insights once `configure_azure_monitor()` is called. No changes to agent code.

### RC1 Breaking Change: Credential Pattern

The RC1 release (Feb 19, 2026) unified credential handling across all Azure packages. If any existing code uses the old `azure_ad_token_provider` pattern, it must be updated:

```python
# BEFORE (will fail on RC1+)
from azure.identity import AzureCliCredential, get_bearer_token_provider
token_provider = get_bearer_token_provider(AzureCliCredential(), "https://cognitiveservices.azure.com/.default")
client = AzureOpenAIChatClient(azure_ad_token_provider=token_provider, ...)

# AFTER (RC1+ unified pattern)
from azure.identity import AzureCliCredential
client = AzureOpenAIChatClient(credential=AzureCliCredential(), ...)
```

### RC1 Breaking Change: Session API

```python
# BEFORE (removed in python-1.0.0b260212)
thread = agent.get_new_thread()
response = await agent.run("Hello", thread=thread)

# AFTER
session = agent.create_session()
response = await agent.run("Hello", session=session)
```

---

## Orchestration Strategy: HandoffBuilder vs Connected Agents

The migration has a choice between two multi-agent patterns, and the choice depends on depth requirements:

| Strategy | When to Use | Pros | Cons |
|----------|-------------|------|------|
| **HandoffBuilder (local)** | Multi-agent flows with >2 hierarchy levels, or when agents need local function tools | Unlimited depth, full function tool support, works today | Orchestration happens in the backend container (no Foundry dashboard visibility) |
| **Connected Agents (server-side)** | Flat multi-agent: 1 parent + N subagents (max depth 2) | Foundry manages threads, dashboard observability, no orchestration code | Max depth 2, subagents CANNOT call local function tools (must use OpenAPI or Azure Functions instead) |

**Recommendation:** Use `AzureAIAgentClient` for all agents (for persistent state and server-managed threads), but keep `HandoffBuilder` for local orchestration if the current 7-agent system has any nesting deeper than parent + flat siblings. Only migrate to Connected Agents if the architecture is verified to be depth ≤ 2 AND agents do not need local Python function tools.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `agent-framework-core 1.0.0rc1` | `agent-framework-azure-ai 1.0.0rc1` | Both promoted to RC1 together on Feb 19, 2026. Install same RC tag. |
| `agent-framework-core 1.0.0rc2` | `agent-framework-azure-ai` (rc2) | RC2 released Feb 26, 2026. `agent-framework-azure-ai` not explicitly listed in rc2 release notes — may still be on rc1. Verify with `uv pip show agent-framework-azure-ai` after install. |
| `azure-ai-projects 1.0.0` | `azure-ai-agents 1.1.0` | `azure-ai-agents` is a dependency of `azure-ai-projects`. Pin both to avoid drift. |
| `azure-monitor-opentelemetry 1.8.6` | `opentelemetry-sdk` (any recent) | The distro pins its own OTel SDK. Do not manually pin `opentelemetry-sdk` in your `pyproject.toml` — let the distro control it to avoid conflicts. |
| `AzureAIAgentClient` | Python `>=3.10` | Same as `agent-framework-core` minimum. |
| `azure-ai-projects 1.0.0` | Python `>=3.9` | Broader than Agent Framework — no conflict. |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `azure-monitor-opentelemetry-distro` | Deprecated package name | `azure-monitor-opentelemetry` |
| Direct `opentelemetry-sdk` pin in `pyproject.toml` | Version conflicts with `azure-monitor-opentelemetry` distro's internal pins | Let the distro manage OTel versions |
| Hub-based AI Foundry project (old type) | Deprecated — hub-based projects cannot use current SDK or REST API versions (since May 2025) | New Microsoft Foundry resource (`Microsoft.CognitiveServices/accounts`) |
| `azure-ai-agents` as the sole agent management SDK (bypassing Agent Framework) | Bypasses the Agent Framework session, middleware, streaming, and AG-UI integration | `AzureAIAgentClient` from `agent-framework-azure-ai` wrapping `azure-ai-projects` |
| `AzureOpenAIAssistantsClient` | Older Assistants API client, separate from Foundry Agent Service | `AzureAIAgentClient` |

---

## Sources

### HIGH Confidence (Official docs, PyPI, official release notes)

- [agent-framework-azure-ai API Reference (Microsoft Learn)](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) — `AzureAIAgentClient` class, constructor params, `as_agent()` usage, credential pattern
- [Microsoft Foundry Agents with Agent Framework (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-ai-foundry) — `AzureAIAgentClient` quickstart, environment variables, `AzureAIProjectAgentProvider`, persistent agent lifecycle, updated 2026-02-23
- [Python 2026 Significant Changes Guide (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — RC1 breaking changes: unified credential parameter, `AgentThread`→`AgentSession`, exception hierarchy redesign, `pydantic-settings` removal from AF internals
- [Agent Framework Releases — python-1.0.0rc2 (GitHub)](https://github.com/microsoft/agent-framework/releases) — RC2 Feb 26, 2026; RC1 Feb 20, 2026; lists packages promoted to RC
- [HandoffBuilder Documentation (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff) — HandoffBuilder with `AzureOpenAIChatClient`, Python code examples with `from agent_framework.azure import AzureOpenAIChatClient`
- [Connected Agents How-To (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — `ConnectedAgentTool`, max depth 2 limitation, no local function tools, Python code with `azure-ai-projects`, updated 2026-02-25
- [Foundry Agent Service Quickstart (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/quickstart?view=foundry-classic) — `PROJECT_ENDPOINT` format `https://<account>.services.ai.azure.com/api/projects/<project>`, `MODEL_DEPLOYMENT_NAME`, RBAC roles, `azure-ai-projects` install
- [azure-ai-projects on PyPI](https://pypi.org/project/azure-ai-projects/) — Version 1.0.0 GA, released July 31, 2025
- [azure-ai-agents on PyPI](https://pypi.org/project/azure-ai-agents/) — Version 1.1.0, released August 5, 2025
- [azure-monitor-opentelemetry on PyPI](https://pypi.org/project/azure-monitor-opentelemetry/) — Version 1.8.6, released February 4, 2026

### MEDIUM Confidence (GitHub issues, community sources)

- [Issue #3097: HandoffBuilder + AzureAIClient Invalid Payload (GitHub)](https://github.com/microsoft/agent-framework/issues/3097) — Bug where HandoffBuilder failed with 400 errors when using Azure Foundry v2 client. Marked RESOLVED/COMPLETED Feb 9, 2026, via PR #4083 (reasoning model serialization fix). Validate against RC1/RC2 before committing to HandoffBuilder + AzureAIAgentClient in production.
- [Providers Overview (Microsoft Learn)](https://learn.microsoft.com/en-us/agent-framework/agents/providers/) — Feature matrix: all providers (Azure OpenAI, Foundry, Anthropic, etc.). Foundry provider listed as "Persistent server-side agents with managed chat history."

### LOW Confidence (Needs validation)

- `agent-framework-azure-ai` RC2 status: RC2 release notes (Feb 26, 2026) mention `agent-framework-azure-ai-search` improvements but do not explicitly list `agent-framework-azure-ai` as updated. May still be on RC1. Validate actual installed version after `uv pip install agent-framework-azure-ai --prerelease=allow`.
- HandoffBuilder + `AzureAIAgentClient` in production: Issue #3097 is closed as of Feb 9, but it involved earlier beta versions. The fix landed in RC1 via PR #4083. This combination has not been validated in this specific project. Phase 1 should include an integration test before committing to the architecture.

---

*Stack research for: Active Second Brain — Foundry Agent Service migration (AzureAIAgentClient + Connected Agents + Application Insights)*
*Researched: 2026-02-25*
