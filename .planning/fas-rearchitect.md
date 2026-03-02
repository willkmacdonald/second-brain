# Rearchitecture: Foundry Agent Service

## Why

The project's goal is to learn Microsoft Agent Framework and multi-agent systems. The current implementation uses `AzureOpenAIChatClient` with `HandoffBuilder` — this is purely local orchestration. Agents are Python objects in memory, no infrastructure awareness, no service-level management. It's a sophisticated chat completion chain, not a managed multi-agent system.

`AzureAIAgentClient` (Foundry Agent Service) is the infrastructure layer that makes "multi-agent" mean something real: persistent agents, server-managed threads, tool orchestration, observability, content safety, portal management.

## Current State

- **Client**: `AzureOpenAIChatClient` (Chat Completions API — simplest option, wrong for learning goals)
- **Orchestration**: `HandoffBuilder` from `agent-framework-orchestrations` — local synthetic tool calls to transfer control between agents
- **Agents**: Orchestrator + Classifier, defined as in-memory Python objects via `chat_client.as_agent()`
- **Tools**: `@tool` decorated functions (classify_and_file, request_misunderstood, mark_as_junk) — execute locally in FastAPI process
- **Streaming**: Custom `AGUIWorkflowAdapter` wraps `Workflow` for SSE streaming via AG-UI protocol
- **State**: Cosmos DB for captures/classification, but conversation state is ephemeral (no server-side threads)
- **Observability**: OpenTelemetry configured but no Foundry-level tracing, no portal visibility
- **Key file**: `backend/src/second_brain/agents/workflow.py` lines 126-140 — HandoffBuilder is the core orchestration

## Target State

- **Client**: `AzureAIAgentClient` from `agent-framework-azure-ai` (Foundry Agent Service)
- **Orchestration**: Connected Agents (Foundry-native agent-to-agent invocation, server-managed)
- **Agents**: Persistent, server-registered agents with IDs — visible in AI Foundry portal
- **Tools**: Same `@tool` functions, but tool execution managed by the service (define locally, service orchestrates the call loop)
- **Streaming**: AG-UI still works — `agent.run(..., stream=True)` produces same `AgentResponseUpdate` type
- **State**: Server-managed threads for conversation history + Cosmos DB for domain data (captures, classifications)
- **Observability**: Application Insights integration, per-agent run/error rates, token usage, cost tracking, conversation-level tracing in Foundry portal

## What Foundry Agent Service Adds

1. **Persistent agents** — registered server-side with IDs, survive restarts, manageable from portal
2. **Server-side threads** — conversation history managed by the service, not your code
3. **Server-side tool orchestration** — service manages tool call → execute → return loop with retries
4. **Connected Agents** — agents invoke other agents as tools, service tracks the interaction
5. **Built-in content safety** — filters applied automatically at the service boundary
6. **Portal management** — view/edit agents, browse threads, inspect tool calls, run evaluations
7. **Application Insights** — traces, metrics, logs auto-exported; run rates, token usage, cost computed
8. **Enterprise identity** — Entra ID, RBAC, audit logs baked into agent lifecycle
9. **Server-side hosted tools** — code interpreter, file search, web search, Logic Apps, Azure Functions, SharePoint, OpenAPI

## Breaking Change: HandoffBuilder → Connected Agents

`HandoffBuilder` injects synthetic transfer tools that must be intercepted locally — incompatible with `AzureAIAgentClient` where tool calls route through the server. The entire `AGUIWorkflowAdapter` and `_create_workflow()` pattern in `workflow.py` must be replaced.

**Connected Agents** is Foundry's native multi-agent pattern:
- Agent A has Agent B registered as a "connected agent" (tool)
- When Agent A decides to invoke Agent B, the service handles the invocation
- The service tracks the interaction, logs it, traces it
- Visible in the portal as agent-to-agent communication

## Infrastructure Requirements

| Resource | Current | Needed |
|---|---|---|
| Azure OpenAI resource | Yes | Yes (models still deployed here) |
| AI Foundry project | No | **Yes** — required for Agent Service |
| Application Insights | No | **Yes** — for Foundry observability |
| Endpoint format | `https://<resource>.openai.azure.com/` | `https://<resource>.services.ai.azure.com/api/projects/<project-id>` |
| RBAC | Cognitive Services User | **Azure AI User** on project |
| Package | `agent-framework-core` + `agent-framework-orchestrations` | `agent-framework-azure-ai` (adds `azure-ai-agents`) |

## What Changes

| Component | Current | After |
|---|---|---|
| `main.py` client creation | `AzureOpenAIChatClient(credential, endpoint, deployment)` | `AzureAIAgentClient(credential, project_endpoint, model_deployment)` |
| `orchestrator.py` | `chat_client.as_agent(name, instructions)` | `ai_client.as_agent(name, instructions)` — but now server-registered |
| `classifier.py` | `chat_client.as_agent(name, instructions, tools=[...])` | Same pattern, but tools registered server-side |
| `workflow.py` | `HandoffBuilder` + `AGUIWorkflowAdapter` (340+ lines) | **Replace entirely** — Connected Agents pattern or custom orchestration |
| `config.py` | `azure_openai_endpoint`, `azure_openai_chat_deployment_name` | `azure_ai_project_endpoint`, `azure_ai_model_deployment_name` |
| `.env` / deployed env | OpenAI endpoint only | Foundry project endpoint + Application Insights connection string |
| Agent lifecycle | Ephemeral (created per-process) | Persistent (created once, referenced by ID) |
| Conversation state | Ephemeral (in-memory per request) | Server-managed threads |
| Credential | `DefaultAzureCredential()` sync | `DefaultAzureCredential()` async (`azure.identity.aio`) |

## What Does NOT Change

- `@tool` decorated functions (classify_and_file, etc.) — same decorator, same pattern
- Cosmos DB data layer — domain data storage unchanged
- Blob Storage for voice capture — unchanged
- Mobile app — AG-UI SSE streaming interface is the same
- AG-UI protocol — `agent.run(..., stream=True)` produces same events
- Expo app code — zero changes needed

## Migration Approach

### Phase 1: Foundry Infrastructure Setup
- Create AI Foundry project
- Configure Application Insights
- Set up RBAC (Azure AI User)
- Deploy model in Foundry project
- Validate connectivity

### Phase 2: Single Agent Migration
- Migrate Classifier agent to `AzureAIAgentClient`
- Register as persistent agent
- Verify tools work through server-side execution
- Verify portal visibility
- Test streaming

### Phase 3: Multi-Agent with Connected Agents
- Replace `HandoffBuilder` + `AGUIWorkflowAdapter` with Connected Agents pattern
- Orchestrator invokes Classifier as a connected agent
- Verify end-to-end capture flow
- Verify HITL still works

### Phase 4: Observability + Cleanup
- Configure Application Insights tracing
- Verify traces visible in Foundry portal
- Remove old `HandoffBuilder` / `AGUIWorkflowAdapter` code
- Update deployed environment

## Open Questions

1. **Connected Agents + HITL**: Current HITL flow uses `request_info` events from the workflow to pause for user input. How does this work with Connected Agents? Need to research.
2. **AG-UI adapter**: Current custom `AGUIWorkflowAdapter` wraps `Workflow` stream. With Connected Agents, the streaming surface changes — need to understand what events are emitted.
3. **Agent lifecycle management**: Create agents at deploy time? At startup? How to handle agent updates when instructions change?
4. **Thread management**: Server-managed threads vs our Cosmos DB inbox items — how do these coexist? One source of truth for conversations?
5. **Cost**: Foundry Agent Service pricing vs current Chat Completions pricing — any significant difference?

## Key Research Needed

Before planning, research these specifically:
- Connected Agents Python SDK examples and patterns
- HITL (human-in-the-loop) with Foundry Agent Service
- AG-UI integration with `AzureAIAgentClient` agents
- Agent lifecycle management best practices (persistent vs ephemeral)
- Foundry project setup for existing Azure OpenAI resources

## Files to Read for Context

- `backend/src/second_brain/agents/workflow.py` — current HandoffBuilder orchestration (THE file that gets replaced)
- `backend/src/second_brain/agents/orchestrator.py` — agent definition
- `backend/src/second_brain/agents/classifier.py` — agent definition + tool binding
- `backend/src/second_brain/tools/classification.py` — @tool functions
- `backend/src/second_brain/main.py` — client creation (line 254), agent wiring (lines 268-276), AG-UI endpoints
- `backend/src/second_brain/config.py` — settings that need new env vars
- `.planning/research/ARCHITECTURE.md` — original architecture research (recommended AzureOpenAIResponsesClient, but learning goals point to AzureAIAgentClient)
- `.planning/research/STACK.md` — stack decisions
- `.planning/STATE.md` — current project state

## Session Notes (2026-02-25)

- Phase 05 UAT paused at Test 3 (2 passed, 1 issue — blob upload ContentSettings bug fixed and deployed, awaiting retest)
- Phase 05 Plan 03 (mobile voice recording) was executed but no SUMMARY.md exists
- The blob ContentSettings fix was committed and deployed (commit `3fa279a`)
- `voice-recordings` container was created in `wkmshareddata` storage account
- Local `.env` updated with `BLOB_STORAGE_URL` and `AZURE_OPENAI_WHISPER_DEPLOYMENT_NAME`
- Decision: rearchitect toward Foundry Agent Service rather than simple client swap
