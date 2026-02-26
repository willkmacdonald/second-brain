# Feature Research

**Domain:** Azure AI Foundry Agent Service migration (multi-agent capture app)
**Researched:** 2026-02-25
**Confidence:** HIGH — all critical claims verified against official Microsoft docs (updated 2026-02-17 to 2026-02-26)

---

## Context: What This Research Covers

This is a migration milestone, not a new product. v1 features (text/voice capture, HITL, AG-UI streaming, inbox) already exist and are NOT being rebuilt. This research answers: what does migrating from `AzureOpenAIChatClient + HandoffBuilder` to `AzureAIAgentClient` (Foundry Agent Service) actually change, what stays the same, and what are the open questions resolved by evidence.

---

## Feature Landscape

### Table Stakes (Must Work After Migration)

Features that already exist and must continue to work identically after migration. Missing any = regression.

| Feature | Why Table Stakes | Complexity | Migration Notes |
|---------|-----------------|------------|-----------------|
| Text capture → Orchestrator → Classifier → Cosmos DB | Core pipeline; entire product fails without it | MEDIUM | Client swap + workflow replacement. Tool functions unchanged. |
| Voice capture → Perception → classify pipeline | Existing feature; voice users notice immediately | LOW | Perception step stays synthetic (not a Foundry agent). No change needed. |
| HITL: low-confidence captures filed as pending, inbox bucket buttons | Existing HITL path; users depend on it | MEDIUM | Cosmos DB path unchanged. No agent involvement in the respond endpoint. |
| HITL: misunderstood captures → conversational follow-up | Existing HITL path; involves re-running the workflow | HIGH | CUSTOM EVENT detection approach must survive. See Q2 below. |
| AG-UI SSE streaming (StepStarted, StepFinished, Custom events) | Mobile app depends on AG-UI protocol exactly | HIGH | Streaming surface changes: no WorkflowEvent in direct agent.run(). Custom event emission strategy must be rebuilt around WorkflowBuilder events. |
| Inbox view: list, detail cards, swipe-to-delete | Cosmos DB reads; no agent involvement | LOW | Zero change — pure Cosmos DB layer. |
| Recategorize from inbox (bucket buttons) | HITL respond endpoint — no agent involvement | LOW | Zero change — direct Cosmos DB write, no workflow needed. |
| API key auth middleware | Security boundary | LOW | Zero change — middleware unchanged. |

### Differentiators (What the Migration Enables)

New capabilities that become possible after migrating to Foundry Agent Service. Not strictly required for parity, but the whole point of the migration.

| Feature | Value Proposition | Complexity | Migration Notes |
|---------|-------------------|------------|-----------------|
| Persistent agents (server-registered with IDs) | Agents survive restarts; visible in AI Foundry portal; manageable without code changes | MEDIUM | Create agents once in lifespan() using `AIProjectClient.agents.create_agent()`. Store agent IDs on `app.state`. The `as_agent()` async context manager creates + deletes — NOT suitable for a long-running server. |
| Server-managed conversation threads (`AgentSession` with `service_session_id`) | Conversation history lives in Foundry service, not ephemeral memory. Multi-turn interactions (misunderstood follow-up) can resume the same thread. | MEDIUM | AG-UI supports service-managed session continuity as of 1.0.0b260116. Thread IDs map to `service_session_id` in `AgentSession`. Coexists with Cosmos DB — different concerns. |
| Portal visibility: view agents, threads, tool calls in AI Foundry portal | Debugging and monitoring without log grep. See classification outcomes, token usage, agent handoffs. | LOW | Requires AI Foundry project + Azure AI User RBAC. No code change. Zero friction visibility. |
| Application Insights observability: per-agent traces, token usage, cost | Real metrics vs log-scraping. Run rates, errors, cost per classification. | MEDIUM | Requires `APPLICATIONINSIGHTS_CONNECTION_STRING` env var. `configure_otel_providers()` already called at startup — just needs the connection string. Real-time cost charts in Foundry portal. |
| Content safety filters applied at service boundary | Built-in content moderation without custom code | LOW | Automatic once on Foundry. Configurable via RAI policy in portal. No code needed. |
| Enterprise identity: Entra ID, RBAC, audit logs | Production-grade security posture | LOW | Already using `DefaultAzureCredential`. RBAC role change: Cognitive Services User → Azure AI User. |

### Anti-Features (Avoid These During Migration)

Features that seem like obvious improvements but create problems in the migration context.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Connected Agents: Orchestrator → Classifier via Foundry-native invocation | Seems like the "right" Foundry architecture. Portal-visible agent-to-agent calls. | Official docs confirm: "Connected agents cannot call local functions using the function calling tool." The Classifier's entire value is its `@tool` decorated Python functions (`classify_and_file`, `request_misunderstood`, `mark_as_junk`). Moving these to Azure Functions adds significant infrastructure complexity and a new failure domain. | Use `WorkflowBuilder` with `AzureAIAgentClient` agents + local tool execution. Foundry-registered agents + local tool execution + server-managed threads = full observability value without Connected Agents constraints. |
| Rewrite AG-UI adapter to use `workflow.as_agent()` + `add_agent_framework_fastapi_endpoint()` | Simpler, uses framework helper | The framework's `add_agent_framework_fastapi_endpoint` suppresses the custom CLASSIFIED/MISUNDERSTOOD/UNRESOLVED events the mobile app depends on. Also loses Classifier chain-of-thought buffering and outcome detection logic. | Keep the custom AG-UI endpoint and `_stream_sse` pipeline. Replace the `AGUIWorkflowAdapter` internals (client + workflow builder) while preserving the external interface. |
| Use Foundry threads as the conversation data store | Server-managed threads seem like they could replace Cosmos DB | Foundry threads are LLM conversation context (ephemeral, bounded to a session). Cosmos DB inbox items are domain data (persistent, user-queryable, pageable). They serve different purposes. Using Foundry threads as the primary data store would break inbox queries, pagination, and all domain queries. | Use Foundry threads for classification conversation context only. Cosmos DB remains the source of truth for all domain data. These coexist without conflict. |
| Create agents fresh on every request | Simpler lifecycle, no persistent state to manage | Defeats the purpose of Foundry's persistent agent feature. Creates a new agent registration per request — accumulates in portal, incurs overhead, loses traceability. | Create agents once at startup in `lifespan()`, store IDs on `app.state`, reference by ID on every request. Delete on shutdown if ephemerality is intentional. |
| Migrate all 7 planned agents simultaneously | "Complete the architecture" | Phases 3-7 agents (Action, Digest, Entity Resolution, Evaluation) do not exist yet. Migrating non-existent agents wastes time and creates dead code. | Migrate only Orchestrator + Classifier (the two that exist). Other agents follow the same pattern when built in future milestones. |

---

## Resolved Open Questions

The 5 open questions from `fas-rearchitect.md` are answered here with evidence from official docs.

### Q1: Connected Agents + HITL

**Question:** How does `request_info` (pause for user input) work with Connected Agents?

**Answer:** Not applicable for this project. Connected Agents **cannot call local function tools**. The official docs state: "Connected agents cannot call local functions using the function calling tool. We recommend using the OpenAPI tool or Azure Functions instead."

The HITL pattern is implemented entirely through local `@tool` functions (`request_misunderstood` writes to Cosmos DB, returns inbox item ID). Since Connected Agents cannot use these tools, Connected Agents is not a viable orchestration path for Orchestrator → Classifier unless tools are moved to Azure Functions or OpenAPI endpoints.

HITL itself (low-confidence inbox + respond endpoint, misunderstood follow-up endpoint) does NOT involve the Foundry agent at the pause/resume step. The `respond` and `follow-up` endpoints write directly to Cosmos DB — they do not call the agent. HITL works identically regardless of which agent client is used for the initial classification run.

**Confidence:** HIGH
**Source:** https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents

### Q2: AG-UI Adapter Changes

**Question:** What changes with `AzureAIAgentClient` streaming?

**Answer:** With `AzureAIAgentClient` + `WorkflowBuilder`, streaming produces `WorkflowEvent` objects — the same event surface the current `AGUIWorkflowAdapter` already handles. Event types (`"output"`, `"executor_invoked"`, `"executor_completed"`, `"request_info"`) are produced identically whether the agents are backed by `AzureOpenAIChatClient` or `AzureAIAgentClient`. The `_stream_updates` method processes this same `WorkflowEvent` + `AgentResponseUpdate` contract.

The key change: `AGUIWorkflowAdapter._create_workflow()` replaces `HandoffBuilder` with `WorkflowBuilder`. The adapter's external `run(stream=True)` interface is preserved. The outcome detection logic (function_call.name inspection for CLASSIFIED/MISUNDERSTOOD/UNRESOLVED events), chain-of-thought buffering, and clean result construction are all preserved.

Additional: AG-UI supports service-managed session continuity as of 1.0.0b260116. The `thread_id` from the AG-UI request can be preserved as the `service_session_id`, enabling thread resumption across HTTP requests for multi-turn HITL flows.

**Confidence:** HIGH — docs confirmed WorkflowEvent surface unchanged between providers.
**Source:** https://learn.microsoft.com/en-us/agent-framework/workflows/agents-in-workflows

### Q3: Agent Lifecycle Management

**Question:** Create at deploy time? At startup? How to handle instruction updates?

**Answer:**
- **Recommended pattern (startup):** Create agents in the FastAPI `lifespan()` context manager using `AIProjectClient.agents.create_agent()`. Store returned agent IDs on `app.state`. Reference by ID on every request. Delete on shutdown.
- **Why NOT the async context manager pattern:** `AzureAIAgentClient(...).as_agent(name, instructions)` used as `async with` creates AND deletes the agent when the context exits. This creates + destroys the agent per-request if used in request handlers — not what we want.
- **Why NOT pre-created by ID:** Storing agent IDs in env vars means instruction updates require a manual API call or portal edit. Startup creation is simpler for a learning project — instructions are always current after each deploy.
- **Instruction updates:** If created at startup, each deploy re-creates with current instructions. If created by ID, portal or API update required when instructions change.

**Confidence:** HIGH — official docs show both patterns with code examples.
**Sources:**
- https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/azure-ai-foundry-agent
- https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/manage-hosted-agent

### Q4: Thread Management

**Question:** Server-managed threads vs Cosmos DB inbox items — how do they coexist?

**Answer:** They serve different purposes and coexist without conflict:

- **Foundry threads** (`AgentSession` with `service_session_id`): LLM conversation context. The agent's memory for "what was said in this conversation." Scoped to a classification session (one capture → one thread). The `service_session_id` can be stored and reused to resume a thread for multi-turn HITL follow-up.
- **Cosmos DB inbox items**: Domain data. The classified capture as a business object with status, bucket, confidence, filed record ID. Queryable by the inbox view. Persistent indefinitely.

A capture flow uses both: one Foundry thread (conversation context for classification) + one Cosmos DB inbox document (the result). The thread ID and inbox item ID are separate identifiers serving separate concerns. The `request_misunderstood` tool writes to Cosmos DB; the follow-up endpoint can resume the Foundry thread via `service_session_id` to maintain LLM conversation context.

**Confidence:** HIGH
**Source:** https://learn.microsoft.com/en-us/agent-framework/agents/conversations/session

### Q5: Tool Execution — Local or Server-Side?

**Question (implicit from fas-rearchitect.md):** `@tool` decorated functions — do they execute locally or server-side?

**Answer:** **Local execution, always.** Even with `AzureAIAgentClient`, Python `@tool` functions execute in the FastAPI process. The Foundry service requests the tool call (returns a tool_call event), the local process executes the function and returns the result, the service incorporates the result and continues. This is the same tool call loop as OpenAI function calling.

The HandoffBuilder constraint is that it requires agents with "local tools execution" — this means `AzureAIAgentClient` agents CAN be used with HandoffBuilder because their tools still execute locally. However, HandoffBuilder uses synthetic handoff tool calls to route between agents, which conflicts with the server-side tool call management in `AzureAIAgentClient`. The safer replacement is `WorkflowBuilder` which uses direct edges rather than synthetic tool calls.

Connected Agents is different: subagent invocation is server-side, which is why local Python functions are excluded.

**Confidence:** HIGH — function calling docs confirm local execution loop.
**Source:** https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/function-calling?view=foundry

---

## Critical Breaking Change: AgentThread → AgentSession

**The current codebase uses `AgentThread` throughout.** This was removed as a breaking change in `1.0.0b260212` (February 2026). The framework is now at Release Candidate status (1.0.0rc1, 2026-02-19), so `AgentSession` is the stable API.

| Old API | New API |
|---------|---------|
| `AgentThread` | `AgentSession` |
| `agent.get_new_thread()` | `agent.create_session()` |
| `agent.get_new_thread(service_thread_id=...)` | `agent.get_session(service_session_id=...)` |
| `thread=thread` in `agent.run()` | `session=session` in `agent.run()` |
| `from agent_framework import AgentThread` | `from agent_framework import AgentSession` |

**Affected files:** `workflow.py` (uses `AgentThread` type hints and `get_new_thread()`), `main.py` (calls `workflow_agent.get_new_thread()`).

This breaking change must be addressed during migration regardless of which agent client is used. It is not optional — the RC packages removed `AgentThread`.

**Source:** https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes

---

## Package Dependency Changes

The migration requires adding `agent-framework-azure-ai` to `pyproject.toml`. The current `pyproject.toml` has `agent-framework-orchestrations` (for `HandoffBuilder`) but not `agent-framework-azure-ai` (for `AzureAIAgentClient`).

| Package | Current Status | After Migration |
|---------|---------------|-----------------|
| `agent-framework-ag-ui` | In pyproject.toml | Keep — unchanged |
| `agent-framework-orchestrations` | In pyproject.toml | Keep (HandoffBuilder still available; WorkflowBuilder may be in core) OR remove if WorkflowBuilder is in agent-framework core |
| `agent-framework-azure-ai` | NOT in pyproject.toml | **Add** — provides `AzureAIAgentClient` |
| `azure-ai-projects` | NOT in pyproject.toml | **Add** — provides `AIProjectClient` for agent lifecycle management |

Also: `azure_openai_endpoint` and `azure_openai_chat_deployment_name` in `config.py` become `azure_ai_project_endpoint` and `azure_ai_model_deployment_name`.

---

## Feature Dependencies

```
[Foundry Infrastructure Setup]
    └──required by──> [AzureAIAgentClient initialization]
                          └──required by──> [Persistent Orchestrator agent]
                          └──required by──> [Persistent Classifier agent]
                                                └──required by──> [WorkflowBuilder orchestration]
                                                                       └──required by──> [AG-UI streaming]
                                                                       └──required by──> [HITL classification flows]

[AgentThread → AgentSession migration]
    └──required by──> [Any agent.run() call — breaking change in RC packages]

[Application Insights connection string]
    └──enables──> [Foundry portal traces and token usage metrics]

[Connected Agents]
    └──conflicts with──> [Local @tool functions on Classifier]
    (NOT viable without moving tools to Azure Functions — v3.0+ concern)

[WorkflowBuilder]
    └──replaces──> [HandoffBuilder] for Foundry agents
    └──preserves──> [Same WorkflowEvent stream surface for AGUIWorkflowAdapter]
```

### Dependency Notes

- **Foundry Infrastructure is Day 1 blocker:** AI Foundry project + Azure AI User RBAC + Application Insights must exist before any agent code can be tested. Infrastructure setup is Phase 1, not Phase 3.
- **AgentThread removal is a prerequisite:** RC packages break any code using `AgentThread`. Must migrate `workflow.py` and `main.py` before or during client migration.
- **WorkflowBuilder replaces HandoffBuilder for Foundry agents:** HandoffBuilder's synthetic tool call approach conflicts with server-side tool management in AzureAIAgentClient. WorkflowBuilder uses direct edges and is confirmed compatible via official Python samples.
- **AG-UI custom events depend on workflow event inspection:** The CLASSIFIED/MISUNDERSTOOD/UNRESOLVED events are detected by inspecting `function_call.name` in the workflow event stream. This pattern is preserved with WorkflowBuilder because the same `WorkflowEvent` types are emitted for tool calls.
- **HITL respond/follow-up endpoints are independent:** These endpoints write directly to Cosmos DB and do not invoke the agent. They are unaffected by the client migration.

---

## MVP Definition

### Launch With (v2.0 — migration parity)

The migration is complete when all of these are true:

- [ ] AI Foundry project created, Application Insights connected, RBAC configured (Azure AI User role)
- [ ] `agent-framework-azure-ai` and `azure-ai-projects` added to `pyproject.toml`
- [ ] `azure_ai_project_endpoint` and `azure_ai_model_deployment_name` in `config.py` + `.env`
- [ ] `AzureAIAgentClient` replaces `AzureOpenAIChatClient` in `main.py` lifespan
- [ ] Orchestrator + Classifier created as persistent Foundry agents at startup (visible in portal)
- [ ] `WorkflowBuilder` replaces `HandoffBuilder` in `AGUIWorkflowAdapter._create_workflow()`
- [ ] `AgentThread` → `AgentSession` migration complete in `workflow.py` and `main.py`
- [ ] All three HITL paths verified: low-confidence pending → inbox bucket buttons → classify; misunderstood → follow-up; recategorize
- [ ] AG-UI SSE streaming verified: StepStarted/StepFinished, CLASSIFIED, MISUNDERSTOOD, UNRESOLVED custom events unchanged
- [ ] Application Insights traces visible in AI Foundry portal for a classification run
- [ ] Token usage and cost metrics visible for at least one run

### Add After Validation (v2.x)

- [ ] Thread resumption via `service_session_id` for misunderstood follow-up (Foundry remembers classification context, not just Cosmos DB)
- [ ] Foundry portal evaluation run (baseline quality metrics now that traces exist)
- [ ] Content safety RAI policy configured

### Future Consideration (v3.0+)

- [ ] Move `classify_and_file` / `request_misunderstood` / `mark_as_junk` to Azure Functions — prerequisite for Connected Agents
- [ ] Connected Agents: Orchestrator as Foundry-native orchestrator, Classifier as connected subagent
- [ ] Action Agent (sharpens vague thoughts) — new agent, same Foundry pattern
- [ ] Additional agents from PRD (Digest, Entity Resolution, Evaluation)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Foundry infrastructure setup | LOW (invisible) | MEDIUM | P1 — Day 1 blocker |
| AzureAIAgentClient + persistent agents | LOW (invisible to end user) | MEDIUM | P1 — core migration goal |
| WorkflowBuilder replacement for HandoffBuilder | LOW (invisible) | MEDIUM | P1 — HandoffBuilder incompatibility risk |
| AgentThread → AgentSession migration | LOW (invisible) | LOW | P1 — breaking change in RC packages |
| Application Insights observability | MEDIUM (Will only) | LOW | P1 — explicit learning goal |
| Portal agent/thread visibility | MEDIUM (Will only) | LOW | P1 — explicit learning goal |
| AG-UI streaming parity | HIGH (users notice if broken) | MEDIUM | P1 — must not regress |
| HITL flow parity | HIGH (users notice if broken) | LOW | P1 — must not regress |
| Thread resumption via service_session_id | LOW (subtle) | MEDIUM | P2 — enhancement |
| Content safety RAI policy | LOW | LOW | P2 — good practice |
| Connected Agents pattern | LOW (invisible) | HIGH | P3 — requires Azure Functions infrastructure |

**Priority key:**
- P1: Required for v2.0 to be called complete
- P2: Add when core is stable and verified
- P3: Requires additional infrastructure or is future milestone work

---

## Sources

- [Azure AI Foundry Agents — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/azure-ai-foundry-agent) — AzureAIAgentClient patterns, async context manager, streaming, tools (updated 2026-02-17)
- [How to use Connected Agents — Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — Connected Agents, Python SDK, **local function limitation confirmed** (updated 2026-02-25)
- [HandoffBuilder Orchestrations — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/handoff) — HandoffBuilder, local tools requirement, HITL tool approval, autonomous mode (updated 2026-02-13)
- [Agents in Workflows — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/workflows/agents-in-workflows) — **WorkflowBuilder + AzureAIAgentClient integration confirmed**, Python samples (updated 2026-02-26)
- [Python 2026 Significant Changes — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — **AgentThread removal**, AgentSession API, WorkflowBuilder changes, credential parameter changes (updated 2026-02-23)
- [Running Agents — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/agents/running-agents) — ResponseStream, AgentResponseUpdate, streaming surface (updated 2026-02-13)
- [Human-in-the-Loop Workflows — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) — request_info pattern, WorkflowBuilder HITL, response_handler
- [Human-in-the-Loop with AG-UI — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/integrations/ag-ui/human-in-the-loop) — AG-UI HITL, approval_mode, @tool decorator patterns
- [Function Calling — Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/function-calling?view=foundry) — Local function execution pattern, tool call loop, 10-minute run expiration (updated 2026-02-25)
- [Agent Session — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/agents/conversations/session) — AgentSession, service_session_id, serialization (updated 2026-02-13)
- [Agent Providers Overview — Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/agent-types/) — Provider comparison matrix, function tool support per provider
- [Application Insights for AI Agents](https://learn.microsoft.com/en-us/azure/azure-monitor/app/agents-view) — Observability, token usage, cost tracking, fleet monitoring
- [GitHub Issue #3097 — HandoffBuilder + AzureAIClient payload error](https://github.com/microsoft/agent-framework/issues/3097) — HandoffBuilder compatibility evidence

---
*Feature research for: Azure AI Foundry Agent Service migration — The Active Second Brain v2.0*
*Researched: 2026-02-25*
