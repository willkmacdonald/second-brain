# Project Research Summary

**Project:** Active Second Brain — Foundry Agent Service Migration (v2.0)
**Domain:** Azure AI Foundry Agent Service migration of an existing FastAPI multi-agent capture system
**Researched:** 2026-02-25
**Confidence:** HIGH — all four researchers independently verified findings against official Microsoft Learn docs (updated 2026-02-13 to 2026-02-26)

## Executive Summary

This is a targeted migration, not a rebuild. The existing capture pipeline (text/voice input, HITL classification, Cosmos DB storage, AG-UI SSE streaming to the Expo mobile app) stays functionally identical. What changes is the agent infrastructure underneath it: `AzureOpenAIChatClient` + `HandoffBuilder` are replaced by `AzureAIAgentClient` backed by Azure AI Foundry Agent Service. The goals are persistent server-registered agents, server-managed conversation threads, and Application Insights observability — none of which affect end-user behavior.

The single biggest finding across all four researchers is unanimous and well-sourced: **Connected Agents cannot call local Python `@tool` functions**. The official Microsoft docs state this explicitly. Since the Classifier agent's entire value is its three `@tool` functions that write to Cosmos DB (`classify_and_file`, `request_misunderstood`, `mark_as_junk`), Connected Agents is not a viable orchestration pattern for this system without first moving those functions to Azure Functions — a v3.0 concern. The recommended approach for v2.0 is direct `AzureAIAgentClient` on the Classifier, with the Orchestrator eliminated, and code-based request routing in the FastAPI endpoint replacing the `HandoffBuilder` multi-agent chain.

The migration is simpler than originally planned. The `HandoffBuilder` + `AGUIWorkflowAdapter` complex is replaced by a single `FoundrySSEAdapter` of approximately 100-150 lines that wraps one `classifier_agent.run()` call. The Orchestrator agent can be eliminated entirely. The core outcome-detection logic (inspecting `function_call.name` to emit `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED` custom events) is preserved verbatim — only the surrounding framework event types change. Three mandatory breaking changes must be addressed regardless of architecture choice: `AgentThread` → `AgentSession` migration, sync → async credential (`azure.identity.aio`), and `HandoffBuilder` removal. These are prerequisites to any Foundry client code working at all on the RC packages.

## Key Findings

### Recommended Stack

The existing validated stack (FastAPI, Expo/React Native, Cosmos DB, Blob Storage, Azure Container Apps, uv, Ruff) is unchanged. The migration adds three packages: `agent-framework-azure-ai` (RC1, install with `--prerelease=allow`), `azure-ai-projects>=1.0.0` (GA), and `azure-monitor-opentelemetry>=1.8.6` (GA). The `azure-ai-agents>=1.1.0` package should be pinned explicitly as it is a transitive dependency of `azure-ai-projects`. No packages are removed from `pyproject.toml`, though `agent-framework-orchestrations` can be removed once `HandoffBuilder` is deleted.

A new Azure resource type is required: a **Microsoft Foundry Account** (`Microsoft.CognitiveServices/accounts`), distinct from the old hub-based `Microsoft.MachineLearningServices/workspaces`. The project endpoint format is `https://<account>.services.ai.azure.com/api/projects/<project>`. Application Insights requires a connection string in `APPLICATIONINSIGHTS_CONNECTION_STRING`. The existing Azure OpenAI resource and deployment remain in use for Whisper transcription — these are separate concerns.

**Core technologies added:**
- `agent-framework-azure-ai` (RC1): Provides `AzureAIAgentClient` — the Foundry-backed agent client replacing `AzureOpenAIChatClient`
- `azure-ai-projects` (GA 1.0.0): `AIProjectClient` for agent lifecycle management (create, list, delete persistent agents)
- `azure-monitor-opentelemetry` (GA 1.8.6): One-call Application Insights setup via `configure_azure_monitor()`
- Microsoft Foundry Account + Project: New Azure resource providing the project endpoint, server-managed threads, and portal observability

**Version compatibility note:** RC2 (Feb 26, 2026) is the current release of `agent-framework-core`. The `agent-framework-azure-ai` RC2 status is unconfirmed — it may still be on RC1. Validate with `uv pip show agent-framework-azure-ai` after install.

### Expected Features

**Must have (table stakes — must not regress after migration):**
- Text capture → Classifier → Cosmos DB: core pipeline, same user-facing behavior
- Voice capture → Perception (Blob + Whisper) → Classifier → Cosmos DB: Perception step unchanged
- HITL low-confidence: pending inbox items, bucket buttons for re-categorization (direct Cosmos write, no agent involved)
- HITL misunderstood: conversational follow-up endpoint (re-runs classification with fresh Foundry thread)
- AG-UI SSE streaming: `StepStarted`, `StepFinished`, `CLASSIFIED`, `MISUNDERSTOOD`, `UNRESOLVED` custom events unchanged
- Inbox CRUD: zero change, pure Cosmos DB layer

**Should have (migration differentiators — the point of the migration):**
- Persistent agents visible in AI Foundry portal with stable IDs across restarts
- Server-managed conversation threads (`AgentSession` with `service_session_id`)
- Application Insights traces: per-run token usage, cost, classification outcomes visible in portal
- Content safety RAI policy (automatic once on Foundry, zero code)

**Defer to v2.x (post-parity enhancements):**
- Thread resumption via `service_session_id` for misunderstood follow-up (Foundry remembers context)
- Foundry portal evaluation runs for baseline quality metrics

**Defer to v3.0+:**
- Connected Agents pattern (requires moving `classify_and_file` etc. to Azure Functions first)
- Action Agent, Digest Agent, Entity Resolution Agent (do not exist yet; same Foundry pattern when built)

### Architecture Approach

The migration collapses the two-agent HandoffBuilder chain (Orchestrator → Classifier) into a single persistent `AzureAIAgentClient`-backed Classifier agent. The Orchestrator is eliminated — it was only needed to route to the Classifier, and with code-based orchestration the FastAPI endpoint calls the Classifier directly. The `AGUIWorkflowAdapter` (340 lines, HandoffBuilder-dependent) is replaced with a `FoundrySSEAdapter` (~100-150 lines) that wraps `classifier_agent.run(stream=True)`. The adapter's outcome detection logic (inspect `function_call.name` for `classify_and_file`/`request_misunderstood`/`mark_as_junk`), text buffering, and custom event emission are preserved verbatim. The adapter is a rewrite of the surrounding plumbing, not of the detection logic.

**Major components that change:**
1. `main.py` lifespan — replace `AzureOpenAIChatClient` construction with `AzureAIAgentClient`; use `should_cleanup_agent=False`; store `classifier_agent` and `ai_client` on `app.state`
2. `agents/workflow.py` — full replacement: `AGUIWorkflowAdapter` → `FoundrySSEAdapter`
3. `config.py` — add `azure_ai_project_endpoint`, `azure_ai_model_deployment_name`, `azure_ai_classifier_agent_id`, `applicationinsights_connection_string`
4. `agents/orchestrator.py` — deleted (Orchestrator eliminated)
5. `agents/classifier.py` — import swap: `AzureOpenAIChatClient` → `AzureAIAgentClient`

6. `tools/transcription.py` — rewritten: `transcribe_audio` becomes a `@tool` using `gpt-4o-transcribe` via `AsyncAzureOpenAI` (replaces sync Whisper via Cognitive Services). The Classifier agent calls this tool when processing voice input.
7. `agents/perception.py` — deleted (Perception Agent eliminated; transcription is now a tool callable by Classifier)
8. Middleware — `AgentMiddleware` for audit logging, `FunctionMiddleware` for tool validation/timing (e.g., `TranscriptionGuardMiddleware` validates file extension and size before calling `gpt-4o-transcribe`)

**Components that do not change (majority of codebase):**
- `tools/classification.py` — all `@tool` functions unchanged
- `db/cosmos.py`, `db/blob_storage.py` — unchanged
- `api/inbox.py`, `api/health.py`, `auth.py` — unchanged
- Mobile Expo app — unchanged
- AG-UI SSE protocol and event format — unchanged
- `/api/ag-ui/respond` endpoint — unchanged (direct Cosmos write, no agent involvement)

**Key patterns confirmed:**
- `AzureAIAgentClient` requires `azure.identity.aio.DefaultAzureCredential` (async), not the sync variant
- `should_cleanup_agent=False` is mandatory for persistent agents in a FastAPI lifespan
- Tools must be registered at `as_agent()` creation time, not at `run()` call time
- Store `ai_client` on `app.state` alongside `classifier_agent` to keep the HTTP connection alive
- HITL follow-up: always create a fresh Foundry thread (new `thread_id`) to avoid conversation history contamination from the first failed classification pass
- Transcription is a `@tool` callable by the agent, using `gpt-4o-transcribe` via `AsyncAzureOpenAI` — the agent decides when to transcribe, not the endpoint code
- Three middleware layers available: `AgentMiddleware` (whole run), `FunctionMiddleware` (tool calls), `ChatMiddleware` (LLM API calls) — use `call_next()` pattern to proceed or block
- Middleware can be added at agent creation time AND per-run (for dynamic behavior)

### Critical Pitfalls

All pitfalls are HIGH confidence, sourced from official docs or confirmed GitHub issues (issue #3097 for HandoffBuilder incompatibility, official Connected Agents docs for local function limitation).

1. **HandoffBuilder is fundamentally incompatible with `AzureAIAgentClient`** — HandoffBuilder's synthetic transfer tools fail Azure's JSON schema validation (HTTP 400, "invalid payload") when the Foundry service validates the conversation history payload. Do not attempt to use HandoffBuilder with any Foundry client. Delete it before writing any migration code. The architecture fix is to eliminate HandoffBuilder entirely and call the Classifier directly.

2. **Connected Agents cannot call local `@tool` functions** — Official docs state this explicitly. Sub-agent tool calls in Connected Agents are handled server-side; the FastAPI process never receives the `requires_action` callback. The Classifier's Cosmos DB writes will silently never execute. Do not use Connected Agents in v2.0. This is the unanimous finding across all four research files.

3. **`should_cleanup_agent=True` (default) destroys agent persistence** — The default context manager deletes the Foundry agent on exit. Every Container App restart creates a new agent with a new ID, accumulating stale agents in the portal and invalidating any stored ID references. Always pass `should_cleanup_agent=False` for long-lived FastAPI deployments.

4. **Sync `DefaultAzureCredential` fails with `AzureAIAgentClient`** — `AzureAIAgentClient` requires `AsyncTokenCredential` from `azure.identity.aio`. Passing the sync credential causes silent auth failures or `TypeError` at runtime. Update all credential imports before writing any Foundry client code.

5. **RBAC requires three separate role assignments** — Developer Entra ID → Azure AI User on Foundry project; Container App managed identity → Azure AI User on Foundry project; Foundry project managed identity → Cognitive Services User on Azure OpenAI resource. Missing any one causes 403/401 errors that appear only in specific contexts (local dev vs. deployed).

6. **`AGUIWorkflowAdapter` is a complete rewrite, not a migration** — The existing adapter references `WorkflowEvent`, `executor_invoked`, `executor_completed` types that do not exist in the `AzureAIAgentClient` stream. The stream produces `AgentResponseUpdate` objects. The detection logic is reusable; all event-type handling must be rewritten around `AgentResponseUpdate`.

## Implications for Roadmap

Based on combined research, the migration decomposes into four natural phases. The hard dependency ordering is: infrastructure before code, credentials before client, client before adapter, adapter before HITL validation.

### Phase 1: Infrastructure and Prerequisites
**Rationale:** Nothing else can be tested without a Foundry project endpoint, RBAC assignments, and Application Insights connection string. The RC breaking changes (`AgentThread` → `AgentSession`, sync → async credential) must also be applied before any Foundry client code compiles. This phase has no code risk — it is environment setup and surgical API updates. It also includes deleting `HandoffBuilder` and `AGUIWorkflowAdapter` before they can cause confusion.
**Delivers:** Working Foundry project with model deployment; Application Insights instance connected; `AgentThread` → `AgentSession` migration complete in `workflow.py` and `main.py`; async credentials in place (`azure.identity.aio`); `HandoffBuilder` and `AGUIWorkflowAdapter` deleted; new env vars in `.env` and `config.py`; `agent-framework-azure-ai` installed and import verified
**Avoids:** Pitfall 4 (credential), Pitfall 5 (RBAC) — all three role assignments before a single SDK call; RC breaking changes that silently break the existing codebase

### Phase 2: Single-Agent Classifier Baseline
**Rationale:** Before touching `main.py` or the SSE adapter, validate that `AzureAIAgentClient` can authenticate to Foundry, create a persistent Classifier agent, and execute local `@tool` functions. Specifically: confirm that `classify_and_file` writes to Cosmos DB when called by the Foundry service. This is the highest-risk validation step — if tool execution does not work as documented, the architecture needs to change. A standalone test script (not FastAPI) validates this independently without risk to the running service.
**Delivers:** Classifier agent visible in Foundry portal with stable ID across restarts; `classify_and_file` confirmed executing locally during a Foundry-managed run; agent ID captured for `AZURE_AI_CLASSIFIER_AGENT_ID` env var; `classifier.py` updated with `AzureAIAgentClient`; `should_cleanup_agent=False` confirmed working
**Avoids:** Pitfall 2 (tool execution confirmed before building the adapter); Pitfall 3 (agent ID management strategy locked in); discovery of fundamental incompatibility after a full adapter rewrite

### Phase 3: FoundrySSEAdapter and FastAPI Integration
**Rationale:** With the Classifier baseline confirmed, replace the AG-UI plumbing. `HandoffBuilder` and `AGUIWorkflowAdapter` are already gone. The `FoundrySSEAdapter` is a focused rewrite (~100-150 lines) that wires `classifier_agent.run(stream=True)` to the existing `_stream_sse()` helper in `main.py`. The outcome-detection logic, text buffering, and custom event emission are copied from the old adapter and adapted for `AgentResponseUpdate` event types. Wire into `main.py` lifespan. End-to-end test: text capture → SSE stream → Cosmos DB write → `CLASSIFIED` event received by mobile app. Then validate voice capture (Perception step → same adapter).
**Delivers:** `FoundrySSEAdapter` replacing `AGUIWorkflowAdapter`; `main.py` lifespan migrated to `AzureAIAgentClient`; Orchestrator deleted; text and voice capture pipelines working end-to-end; `CLASSIFIED`/`MISUNDERSTOOD`/`UNRESOLVED` custom events verified against mobile app; `_stream_sse()` and `_convert_update_to_events()` helpers unchanged
**Uses:** `AzureAIAgentClient`, `should_cleanup_agent=False`, `AgentSession`, `AgentResponseUpdate` stream
**Avoids:** Pitfall 6 (AGUIWorkflowAdapter rewrite correctly scoped); HITL thread isolation strategy decided before implementation

### Phase 4: HITL Validation and Observability
**Rationale:** HITL flows are the highest functional risk because they depend on the adapter's custom event emission and thread management. Validate all three HITL paths explicitly: low-confidence pending → inbox bucket buttons; misunderstood → follow-up (fresh thread confirmed); recategorize. Then wire Application Insights and verify traces and token usage appear in the Foundry portal. This phase completes the v2.0 definition of done.
**Delivers:** All three HITL flows verified end-to-end; HITL follow-up confirmed using fresh Foundry threads (no conversation history contamination); Application Insights traces visible in portal for a classification run; token usage and cost metrics confirmed; v2.0 migration declared complete
**Uses:** `configure_azure_monitor()` with `APPLICATIONINSIGHTS_CONNECTION_STRING`; fresh `thread_id` generation on follow-up endpoint

### Phase Ordering Rationale

- Phase 1 before everything else: The Foundry project endpoint must exist before any SDK call. The RC breaking changes cause import errors in the existing codebase. Three-scope RBAC must be complete before local dev validation is meaningful. There is zero ambiguity about this ordering.
- Phase 2 before Phase 3: Tool execution must be confirmed in isolation via standalone test script. If `classify_and_file` does not execute locally with `AzureAIAgentClient`, the architecture is wrong and Phase 3 would need to be redesigned. Isolation catches this failure before a full adapter rewrite, saving significant time.
- Phase 3 before Phase 4: The `FoundrySSEAdapter` must exist for HITL flows to be testable. HITL validation is meaningless against the old adapter (which is already deleted by Phase 1).
- Observability in Phase 4: Application Insights is a one-line setup (`configure_azure_monitor()`). It does not block migration completion but should be confirmed working before v2.0 is declared done.

### Research Flags

All four phases can proceed without additional research-phase invocations. The migration is well-documented in official Microsoft Learn sources updated through February 2026.

**Phases with standard patterns — skip research-phase:**
- **Phase 1:** Entirely mechanical changes (package install, env vars, API migration). All changes are in the official 2026 Significant Changes migration guide.
- **Phase 2:** `AzureAIAgentClient` + local `@tool` pattern is documented in official samples with code. No ambiguity.
- **Phase 3:** `FoundrySSEAdapter` design is clear. `AgentResponseUpdate` event types are confirmed stable across providers in official AG-UI integration docs.
- **Phase 4:** HITL thread strategy (fresh thread per follow-up) is explicitly chosen based on research. Application Insights is `configure_azure_monitor()` with one env var.

**One empirical validation needed during Phase 2 (not a research-phase, a smoke test):**
- Confirm that `classifier_agent.run(stream=True)` emits `AgentResponseUpdate` objects (not `WorkflowEvent` types) when using `AzureAIAgentClient`. The docs say this, and the `AgentResponseUpdate` stream surface is confirmed unchanged across providers in official docs. Verify empirically during Phase 2 standalone testing before writing the `FoundrySSEAdapter` event handler in Phase 3.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified on PyPI with confirmed versions. `agent-framework-azure-ai` RC2 status is the only open item — minor, just confirm installed version after install. |
| Features | HIGH | All 5 open questions from `fas-rearchitect.md` answered with official source citations. Connected Agents limitation confirmed from four independent sources. Migration scope (only Orchestrator + Classifier exist; migrate only those) is unambiguous. |
| Architecture | HIGH | `FoundrySSEAdapter` design derived from official `AgentResponseUpdate` streaming docs. `should_cleanup_agent=False` confirmed in API reference. Orchestrator elimination follows directly and cleanly from the Connected Agents ruling. Component boundary analysis is high confidence — SDK source inspection confirmed `AzureAIAgentClient` lazy import from `agent_framework_azure_ai`. |
| Pitfalls | HIGH | 8 critical pitfalls documented with official sources, warning signs, recovery strategies, and phase-to-pitfall mapping. All four research files independently reach the same conclusions on the top three pitfalls (HandoffBuilder incompatibility, Connected Agents local function limitation, `should_cleanup_agent` default). |

**Overall confidence: HIGH**

### Gaps to Address

Three items require empirical validation during execution. None are blockers for planning.

- **`agent-framework-azure-ai` RC2 version:** RC2 release notes do not explicitly confirm `agent-framework-azure-ai` was updated alongside `agent-framework-core`. Run `uv pip show agent-framework-azure-ai` after install and note the actual version. Both RC1 and RC2 are compatible with the migration approach — this is a version-tracking item, not an architectural risk.

- **Streaming event types from `AzureAIAgentClient`:** During Phase 2 standalone testing, confirm that `classifier_agent.run(stream=True)` produces `AgentResponseUpdate` objects. This is documented but worth confirming empirically before writing the `FoundrySSEAdapter` event handler in Phase 3. It takes five minutes to verify and removes ambiguity from the Phase 3 implementation.

- **Foundry project vs. existing Azure OpenAI resource:** Confirm whether an existing Azure OpenAI resource can be wired to a new Foundry project, or whether a separate model deployment is needed within the Foundry project. The endpoint format `https://<account>.services.ai.azure.com/api/projects/<project>` is distinct from `https://<resource>.openai.azure.com/`. Whisper stays on the Azure OpenAI endpoint; the Classifier agent uses the Foundry project endpoint. Validate both can coexist in the same Container App deployment before Phase 1 is declared complete.

## Sources

### Primary (HIGH confidence — official Microsoft Learn, updated Feb 2026)

- [AzureAIAgentClient API Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient) — constructor params, `should_cleanup_agent`, `as_agent()`
- [Microsoft Foundry Agents with Agent Framework](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-ai-foundry) — `AzureAIAgentClient` quickstart, lifespan pattern, env vars (updated 2026-02-23)
- [Python 2026 Significant Changes Guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — RC1 breaking changes: `AgentThread` → `AgentSession`, unified credential, `pydantic-settings` removal (updated 2026-02-23)
- [Connected Agents How-To](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — local function limitation explicitly stated (updated 2026-02-25)
- [Agents in Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/agents-in-workflows) — `WorkflowBuilder` + `AzureAIAgentClient` confirmed compatible (updated 2026-02-26)
- [Foundry Agent Service Quickstart](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/quickstart?view=foundry-classic) — project endpoint format, RBAC roles, model deployment
- [RBAC for Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry?view=foundry-classic) — "Azure AI User" role requirements and scope
- [Function Calling with Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/function-calling?view=foundry) — local execution loop, `requires_action` pattern (updated 2026-02-25)
- [azure-ai-projects on PyPI](https://pypi.org/project/azure-ai-projects/) — Version 1.0.0 GA (July 2025)
- [azure-monitor-opentelemetry on PyPI](https://pypi.org/project/azure-monitor-opentelemetry/) — Version 1.8.6 (February 2026)
- [Agent Framework Releases (GitHub)](https://github.com/microsoft/agent-framework/releases) — RC1 (Feb 20, 2026), RC2 (Feb 26, 2026)

### Secondary (MEDIUM confidence — GitHub issues, community sources)

- [Issue #3097: HandoffBuilder + AzureAIClient Invalid Payload](https://github.com/microsoft/agent-framework/issues/3097) — HandoffBuilder incompatibility root cause confirmed, resolved Feb 9 via PR #4083; architecture is still incompatible by design
- [Connected Agents Removed from New Portal](https://learn.microsoft.com/en-us/answers/questions/5631003/new-ai-foundry-experience-no-more-connected-agents) — Community Q&A confirming deprecation in new Foundry experience
- [Agent Accumulation Discussion](https://github.com/orgs/azure-ai-foundry/discussions/18) — Community confirmation of agent accumulation with `should_cleanup_agent` default
- Local SDK inspection: `second-brain/backend/.venv/.../agent_framework/azure/__init__.py` — confirmed `AzureAIAgentClient` lazy import from `agent_framework_azure_ai`; confirmed package not yet installed in current venv

---
*Research completed: 2026-02-25*
*Ready for roadmap: yes*
