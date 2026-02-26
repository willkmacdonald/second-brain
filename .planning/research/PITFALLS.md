# Pitfalls Research

**Domain:** Foundry Agent Service migration — adding AzureAIAgentClient + Connected Agents to an existing FastAPI multi-agent system
**Researched:** 2026-02-25
**Confidence:** MEDIUM-HIGH — Foundry Agent Service SDK is RC1 (February 2026); Connected Agents pattern is evolving rapidly; core API behavior is documented but real-world migration experience is limited

---

## Critical Pitfalls

### Pitfall 1: HandoffBuilder Is Fundamentally Incompatible with AzureAIAgentClient

**What goes wrong:**
You swap `AzureOpenAIChatClient` for `AzureAIAgentClient` in the constructor, keep the existing `HandoffBuilder` + `AGUIWorkflowAdapter`, and expect the multi-agent pipeline to keep working. It fails with HTTP 400 Invalid Payload errors during the second agent invocation. The Orchestrator runs fine; the Classifier never receives the handoff.

**Why it happens:**
`HandoffBuilder` works by injecting synthetic transfer tools that intercept and re-route conversation history between agents in-process. `AzureAIAgentClient` routes tool calls through the Foundry Agent Service REST API, which applies strict JSON schema validation. When `HandoffBuilder` serializes conversation history to pass to the Classifier, the payload fails Azure's schema validation: missing `type` properties on message objects, content arrays lacking required `annotations` fields, `input` structured as an array when the API expects a string. This was confirmed in agent-framework GitHub issue #3097 — the root cause is that `HandoffBuilder` was designed for local Chat Completions payloads, not the Foundry Runs API.

**How to avoid:**
Treat `HandoffBuilder` + `AGUIWorkflowAdapter` as dead code from the start of this migration. Do not attempt to use them with `AzureAIAgentClient`. The replacement is one of:
1. **Connected Agents** (Foundry-native): Register the Classifier as a Connected Agent tool on the Orchestrator. The service routes invocations server-side.
2. **Sequential agent calls** (code-based): Call Orchestrator's `agent.run()`, inspect the result, then call Classifier's `agent.run()` with the output. Your FastAPI endpoint manages the chain.
3. **Workflows** (Agent Framework): Use Graph-based Workflows from `agent-framework-core` instead of `HandoffBuilder` — documented to support HITL and checkpointing.

For the Second Brain's sequential capture pipeline (Orchestrator → Classifier), option 2 is the simplest and most testable bridge. Connected Agents is the goal but adds setup complexity.

**Warning signs:**
- HTTP 400 errors with "invalid payload" or "type required" messages during multi-agent runs
- Orchestrator completes successfully but Classifier never fires
- Errors only appear when conversation history has content from a previous agent turn
- Tests with a single agent pass; multi-agent tests fail

**Phase to address:**
Migration Phase 1 (single agent baseline). Verify the Classifier alone works with `AzureAIAgentClient` before attempting any multi-agent pattern. Never carry `HandoffBuilder` into a Foundry client context.

---

### Pitfall 2: Tools Must Be Registered at Agent Creation Time, Not at Runtime

**What goes wrong:**
You create the `AzureAIAgentClient` and attach tools during `agent.run()` by passing them as kwargs or at call time. The tools are silently ignored, or the client logs a warning that "Azure AI Agent Service does not support runtime tool changes." The Classifier agent runs without its classification tools, falls back to text generation, and produces responses instead of calling `classify_and_file`.

**Why it happens:**
`AzureOpenAIChatClient` allowed tools to be supplied at call time — they were sent as part of the Chat Completions API payload. `AzureAIAgentClient` creates a server-side agent resource at startup (via `project_client.agents.create_agent()`). The tools are registered on that server-side resource at creation time. Once the agent is created, the service controls tool execution — you cannot change the tool list without updating the agent resource. The Agent Framework RC1 docs explicitly state this: "AzureAIClient now logs a warning when runtime tools or structured_output differ from the agent's creation-time configuration."

**How to avoid:**
Always pass tools to `as_agent()` or `create_agent()` at the moment the server-side agent resource is created, not when `run()` is called:

```python
# WRONG: tools at run time
agent = client.as_agent(name="Classifier", instructions="...")
await agent.run("Classify this", tools=[classify_and_file])  # ignored

# CORRECT: tools at creation time
agent = client.as_agent(
    name="Classifier",
    instructions="...",
    tools=[classify_and_file, request_misunderstood, mark_as_junk]
)
await agent.run("Classify this")
```

For the Second Brain, this means `ClassificationTools` must be wired to the Classifier at the lifespan startup before the agent is registered with Foundry.

**Warning signs:**
- "does not support runtime tool changes" in application logs
- Agent produces text responses but never calls classification tools
- Tools work with `AzureOpenAIChatClient` but vanish with `AzureAIAgentClient`
- `ToolCallStartEvent` events are absent from the SSE stream

**Phase to address:**
Migration Phase 1. Verify `classify_and_file` appears in tool call events during a single-agent Classifier test before building anything else.

---

### Pitfall 3: The `should_cleanup_agent=True` Default Destroys Persistent Agent Value

**What goes wrong:**
`AzureAIAgentClient` defaults to `should_cleanup_agent=True`. Every time the context manager exits — including on every FastAPI lifespan shutdown — it deletes the server-side agent resource. On each restart you get a new agent with a new ID. Your Foundry portal shows an ever-growing list of deleted agents, or you hit the agent limit. More critically: if you stored the agent ID to reference it elsewhere (Connected Agents, portal link, observability filter), that ID is now invalid.

**Why it happens:**
The default is designed for single-script use where you create, use, and delete an agent in one execution. FastAPI's lifespan pattern exits on shutdown — triggering cleanup. The agent that was persistent through the day's operation is deleted when the Container App scales to zero overnight, restarted fresh the next morning with a different ID.

**How to avoid:**
For long-lived FastAPI deployments, use one of these patterns:

**Option A — Persistent agent by ID (recommended):**
Create agents once manually (via SDK or portal), store their IDs in environment variables, and reference them with `agent_id=`:
```python
client = AzureAIAgentClient(
    credential=credential,
    agent_id=settings.classifier_agent_id,  # env var: CLASSIFIER_AGENT_ID
    should_cleanup_agent=False  # Never delete externally-managed agents
)
```

**Option B — Upsert pattern on startup:**
At startup, check if an agent with your expected name already exists. If yes, use it. If no, create it. Store the ID in the app state.

For the Second Brain, Option A is the correct approach: create Orchestrator and Classifier agents once during infrastructure setup (Phase 1), store their IDs as environment variables, and reference them by ID in the deployed application.

**Warning signs:**
- Azure portal shows many agents named "Orchestrator" or "Classifier" from previous runs
- Agent IDs change on every Container App restart
- Connected Agent configurations break after restarts because the sub-agent ID changed
- Foundry portal shows deleted agents accumulating

**Phase to address:**
Migration Phase 1 (Infrastructure Setup). Establish the agent creation/ID management strategy before writing any application code that creates agents.

---

### Pitfall 4: Connected Agents Cannot Call Local Python Functions

**What goes wrong:**
You register the Classifier as a Connected Agent on the Orchestrator. The Orchestrator successfully invokes the Classifier. But the Classifier's local Python functions (`classify_and_file`, `request_misunderstood`, `mark_as_junk`) do not execute. The Classifier runs but calls to these functions produce no results — they're not in the required_action loop because Connected Agents have a different execution model.

**Why it happens:**
The official Connected Agents documentation states: "Connected agents cannot call local functions using the function calling tool." Connected Agents delegates to sub-agents via the Foundry service's internal routing — sub-agent tool calls are processed remotely, not in your FastAPI process. The sub-agent's `requires_action` state (which is how local Python tools are called in the standard polling model) is handled server-side in the Connected Agents pattern, not exposed to your application code.

This is the critical limitation for the Second Brain: the Classifier's ability to call `classify_and_file` (which writes to Cosmos DB in your FastAPI process) is incompatible with the Connected Agents pattern as documented.

**How to avoid:**
Two strategies depending on the migration path chosen:

**Strategy A — Use Foundry-hosted tools instead of local functions:**
Replace `classify_and_file` with an Azure Function or Azure Logic App that writes to Cosmos DB. The Classifier calls the Azure Function (a hosted tool Foundry supports). This is the architecturally correct solution but requires additional infrastructure.

**Strategy B — Code-based orchestration (avoids Connected Agents):**
Do not use Connected Agents for the Orchestrator → Classifier handoff. Instead, in your FastAPI endpoint, call the Orchestrator's `agent.run()` to get routing intent, then call the Classifier's `agent.run()` based on the result. Local tools execute normally in this model because the Classifier runs via your code, not via Foundry-managed routing. This preserves the local Cosmos DB tools.

For the Second Brain in v2.0, Strategy B is recommended. The local tool calls (Cosmos DB writes) are the core of the capture pipeline. The Connected Agents limitation blocks Strategy A without additional infrastructure work.

**Warning signs:**
- Sub-agent tools never execute when using Connected Agents
- No `ToolCallStartEvent` events from the Classifier when it runs as a connected agent
- The Classifier produces text but never files anything to Cosmos DB
- Foundry portal shows agent invocations but no tool calls within sub-agent runs

**Phase to address:**
Migration Phase 2 (Multi-Agent Pattern). Make the code-based vs Connected Agents decision explicit before beginning multi-agent implementation. Do not spend time implementing Connected Agents if local Python function tools are required.

---

### Pitfall 5: HITL Flow Is Broken by Server-Managed Threads

**What goes wrong:**
The existing HITL flow works by pausing the workflow (via `request_misunderstood` tool), saving the `inbox_item_id` from the SSE stream, and resuming via a separate `/api/ag-ui/follow-up` POST that re-runs the workflow with combined text. With Foundry Agent Service, conversation state lives in server-managed threads. When you create a new `agent.run()` call for the follow-up, Foundry creates a new run on the same thread — but the thread's message history now includes the full Orchestrator→Classifier exchange from the first pass, which confuses the Classifier.

**Why it happens:**
With `AzureOpenAIChatClient`, each request to `/api/ag-ui/follow-up` creates a fresh in-memory workflow with no knowledge of the previous run. The combined text string was the only context. With `AzureAIAgentClient`, threads persist server-side. A new run on the same thread gives the agent its full conversation history, including the original misunderstood classification attempt. The Classifier may try to continue from where it left off rather than re-classify from scratch.

**How to avoid:**
Two options:

**Option A — New thread per follow-up (recommended for v2.0):**
Always create a fresh thread for the follow-up classification run. Pass the combined text (original + follow-up) as the user message to the new thread. This is functionally identical to the v1 behavior — no conversation history contamination. The trade-off is no conversational continuity across HITL rounds, but the Second Brain's current HITL flow already re-runs classification from scratch.

**Option B — Thread continuation (if continuity is desired):**
Store the Foundry thread ID from the first run. In the follow-up, add a new message to the same thread and create a new run. The agent has full context. This requires careful prompt engineering to prevent the Classifier from re-examining its previous (wrong) decision.

For the Second Brain, Option A matches the existing behavior most closely. The `follow_up_misunderstood` endpoint currently combines original text + follow-up into a new message and re-runs classification fresh.

The `/api/ag-ui/respond` (bucket selection) endpoint is unaffected — it does not use the agent at all; it's a direct Cosmos DB write.

**Warning signs:**
- Follow-up classification always returns the same (wrong) bucket as the first pass
- The Classifier asks "What did you mean by X?" again on the second round when it already knows
- Thread message count grows unexpectedly on HITL-heavy captures
- Agent responses reference "as I mentioned earlier" when the earlier mention was in a different conversation

**Phase to address:**
Migration Phase 3 (HITL validation). After migrating the single-agent baseline, verify HITL flows with new thread-per-follow-up strategy before declaring v2.0 complete.

---

### Pitfall 6: Credential Scope Change Breaks Local Development

**What goes wrong:**
The existing codebase uses `DefaultAzureCredential()` (sync, from `azure.identity`) for `AzureOpenAIChatClient`. `AzureAIAgentClient` requires `AsyncTokenCredential` — specifically from `azure.identity.aio`. If you pass the sync credential, the client either silently falls back to a broken auth state or raises a `TypeError` at runtime. In local development with `az login`, the `AzureCliCredential` from `azure.identity.aio` works — but in Container Apps with managed identity, you need `ManagedIdentityCredential` from the async namespace.

**Why it happens:**
`AzureAIAgentClient` is designed as an async client throughout. The RC1 release unified credential handling: all Azure clients now accept `AsyncTokenCredential`. The sync `DefaultAzureCredential` was previously used because `AzureOpenAIChatClient` accepted it. This is a silent breaking change for anyone who copies the existing credential setup without reading the type signature.

The Python 2026 Significant Changes guide explicitly documents this: the unified `credential` parameter now requires `AsyncTokenCredential` or callable token provider for all Azure AI clients.

**How to avoid:**
Replace all credential imports:
```python
# OLD (sync — will not work with AzureAIAgentClient)
from azure.identity import DefaultAzureCredential

# NEW (async — required for AzureAIAgentClient)
from azure.identity.aio import DefaultAzureCredential

# Or for specific contexts:
from azure.identity.aio import AzureCliCredential  # local dev with az login
from azure.identity.aio import ManagedIdentityCredential  # Container Apps
```

Use `async with` for credential lifecycle:
```python
async with DefaultAzureCredential() as credential:
    client = AzureAIAgentClient(credential=credential, ...)
```

In FastAPI's `lifespan`, create the credential in the `async with` block and close it at shutdown. Do NOT share the same credential object between `AzureAIAgentClient` and other sync Azure clients (Key Vault, Cosmos DB) — they need separate credential instances.

**Warning signs:**
- `TypeError: argument of type 'DefaultAzureCredential' is not iterable` or similar
- Authentication works in unit tests but fails when the FastAPI lifespan runs
- Key Vault fetch succeeds (sync credential) but Foundry agent creation fails (async credential mismatch)
- Works locally with `az login` but fails in Container Apps

**Phase to address:**
Migration Phase 1 (Infrastructure Setup). Update credential handling before writing any Foundry-specific code.

---

### Pitfall 7: RBAC Assignment Has Two Scopes — Both Required

**What goes wrong:**
You create the AI Foundry project, assign yourself "Azure AI User" at the project level, and try to create agents via SDK. You get 403 Forbidden. Or: you get agent creation to work but deployed Container Apps returns 401. Or: local dev works but managed identity in production fails.

**Why it happens:**
Foundry Agent Service RBAC has two distinct scopes that are both required:

1. **Developer/user principal**: The human developer's Entra ID account needs "Azure AI User" on the Foundry project resource to create and manage agents via SDK or portal.
2. **Application/managed identity**: The Container App's system-assigned managed identity needs "Azure AI User" on the Foundry project resource to make Foundry API calls at runtime.

These are separate role assignments at the same resource scope. Assigning to one does not affect the other. Additionally, the Foundry project's managed identity (not the Container App's) also needs access to the underlying Azure OpenAI resource — this is a third assignment many people miss.

**How to avoid:**
Before writing any code, assign all three:
1. **Developer's Entra ID** → "Azure AI User" on the Foundry project
2. **Container App's managed identity** → "Azure AI User" on the Foundry project
3. **Foundry project's managed identity** → "Cognitive Services User" (or equivalent) on the Azure OpenAI resource

Verify each assignment independently:
- SDK creates agent successfully (proves developer assignment)
- Agent list call returns agents (proves Foundry project connection)
- Deployed Container App can create a run (proves managed identity assignment)

**Warning signs:**
- 403 Forbidden when calling `project_client.agents.create_agent()` locally
- Works locally (`AzureCliCredential`) but 401 in Container Apps (`ManagedIdentityCredential`)
- Agent creation succeeds but runs fail with "model deployment not found"
- Foundry portal shows agents but SDK returns empty list

**Phase to address:**
Migration Phase 1 (Infrastructure Setup). Do all role assignments before writing a single line of SDK code. Document the specific resource IDs and role assignments for the project.

---

### Pitfall 8: `AGUIWorkflowAdapter` Event Filtering Is Workflow-Specific Logic That Doesn't Port

**What goes wrong:**
The existing `AGUIWorkflowAdapter` (340+ lines) contains deeply workflow-specific logic: Orchestrator echo filtering, Classifier text buffering (chain-of-thought suppression), `function_call.name` inspection to detect classification outcome, custom event emission (`CLASSIFIED`, `MISUNDERSTOOD`). When you replace the workflow with `AzureAIAgentClient` streaming, the event surface changes. `WorkflowEvent`, `executor_invoked`, `executor_completed` are gone. The stream now emits `AgentResponseUpdate` objects with different content types. The custom adapter's filtering logic references internal framework types that no longer exist.

**Why it happens:**
`AGUIWorkflowAdapter` was written for `Workflow` (the `HandoffBuilder` output), which emits `WorkflowEvent` types. `AzureAIAgentClient` streaming uses the Foundry Runs API event stream, which produces `AgentResponseUpdate` with content typed differently. The adapter's `isinstance(event, WorkflowEvent)` checks will never match; the step event generation from `executor_invoked` / `executor_completed` will never fire.

**How to avoid:**
Treat the adapter as a complete rewrite, not a migration. The new AG-UI endpoint must:
1. Call the Orchestrator agent via `agent.run(..., stream=True)`
2. Iterate `AgentResponseUpdate` objects from the Foundry stream
3. Inspect `update.contents` for `function_call` content to detect tool invocations
4. Emit `StepStartedEvent` / `StepFinishedEvent` for each agent boundary (synthetic, since Foundry doesn't emit these)
5. Emit `CLASSIFIED` / `MISUNDERSTOOD` custom events based on tool call detection

The core logic (detect classification tool, filter echo, emit custom events) is reusable — but it must be adapted for the new stream type. Budget significant time for this rewrite and test it thoroughly against the mobile client.

**Warning signs:**
- Empty SSE streams despite agents running successfully
- `isinstance(event, WorkflowEvent)` is always False
- StepStarted/StepFinished events never appear in the mobile app
- CLASSIFIED custom events never arrive even when Cosmos DB shows a successful write

**Phase to address:**
Migration Phase 2 (Single Agent + AG-UI). Rewrite the SSE streaming layer as part of the Classifier-only migration, before attempting multi-agent patterns.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Creating agents at every startup instead of using persistent IDs | No env var management needed | New agent created on every deploy; IDs drift; Connected Agents point to stale IDs; portal fills with duplicates | Never. Store agent IDs as env vars from day one. |
| Using sync `DefaultAzureCredential` with `AzureAIAgentClient` | Copy-paste from existing code | Auth fails silently or with cryptic errors; works locally, breaks in Container Apps | Never. Use `azure.identity.aio` from the start. |
| Keeping `HandoffBuilder` during early migration "just in case" | Preserve existing orchestration | `HandoffBuilder` and `AzureAIAgentClient` cannot coexist. Dead code confuses debugging. | Never. Delete `HandoffBuilder` code when the Foundry client is introduced. |
| Skipping thread cleanup for development | Faster iteration | Thousands of orphaned Foundry threads accumulate; portal becomes unusable for debugging; potential future storage costs | Acceptable during initial development; add cleanup before first real use. |
| Using Connected Agents before verifying local tool compatibility | "Proper" architecture sooner | Local function tools don't execute through Connected Agents; hours lost debugging a fundamental limitation | Never. Verify local tool execution works with the chosen pattern before building multi-agent. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `AzureAIAgentClient` + FastAPI lifespan | Creating client inside endpoint handler on every request | Create client once in `lifespan()`, store on `app.state`. Client is reusable across requests. |
| Foundry threads + Cosmos DB Inbox items | Using Foundry thread ID as the document ID for Cosmos DB | They are separate concepts with separate IDs. Cosmos DB has `inbox_item_id` (your UUID). Foundry has `thread_id` (service-managed). Never conflate them. |
| `should_cleanup_agent` | Default `True` deletes agent on `close()` | Set `should_cleanup_agent=False` for agents created externally (by ID). Only use `True` for throwaway test agents. |
| Credential + agent client context | Closing credential before closing agent client | Close agent client first, then credential. The client needs the credential active for cleanup API calls. |
| Voice capture + Foundry agents | Trying to pass audio bytes through the agent | Voice capture path does NOT change. Audio → Blob Storage → Whisper → transcription text → agent. The agent only sees text. |
| Connected Agents + tool names | Using function names like `classify_and_file` as connected agent tool names | Connected Agent tool names must be "letters and underscores only." Hyphens cause API errors. Use `classify_and_file` (underscores only). |
| Multi-agent + AG-UI thread_id | Generating a new `thread_id` for every endpoint call | The `thread_id` in AG-UI SSE events must be stable for the duration of a capture session (initial run + any follow-up HITL). Generate once per capture, carry it through all follow-up calls. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `DefaultAzureCredential` probing all credential sources | 2-5 second latency on first request after cold start in Container Apps | Use `ManagedIdentityCredential` directly in Container Apps — skip the credential chain probing | Every cold start; worse with scale-to-zero configuration |
| Creating a new `AgentsClient` per request | Rate limit errors; 429s under load; connection overhead | Create one `AgentsClient` in lifespan, share across requests via `app.state` | Under any concurrent load |
| Polling for run completion without streaming | Each capture takes 3-5 seconds of silent waiting while polling; users see no progress | Use `agent.run(..., stream=True)` to get real-time events; stream through AG-UI as they arrive | From the first user interaction |
| Run expiration at 10 minutes | HITL flows that wait >10 minutes for user response find the run has expired | HITL in the Second Brain does NOT pause a Foundry run; it's implemented as a separate new run on follow-up. The 10-minute limit is for tool output submission, not conversation pauses. | Not applicable to this system's HITL pattern |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing `AZURE_AI_PROJECT_ENDPOINT` containing project name in client-visible logs | Exposes project endpoint URL — low-sensitivity but bad hygiene | Log agent IDs and run IDs, not the full project endpoint. |
| Using `AzureCliCredential` in Container Apps deployment | Container Apps does not have `az login` state; all requests fail | Use `ManagedIdentityCredential` explicitly in production. `DefaultAzureCredential` will eventually find the managed identity but adds cold-start latency. |
| Same managed identity for multiple Azure resources with different access levels | Overly-permissive managed identity if it can access both Foundry and Key Vault at admin level | Principle of least privilege: grant the Container App's managed identity only "Azure AI User" on Foundry, only "Key Vault Secrets User" on Key Vault. Nothing more. |

---

## "Looks Done But Isn't" Checklist

- [ ] **Agent persistence**: `agent.run()` returns a result — but verify the agent was NOT recreated (check Foundry portal; agent ID should be stable across restarts if using `agent_id=`)
- [ ] **Tool execution**: The Classifier runs and returns a response — but verify `classify_and_file` actually wrote a document to Cosmos DB (check Cosmos DB Data Explorer, not just the SSE response)
- [ ] **Connected Agents tool execution**: Connected Agent invokes the sub-agent — but verify local Python functions actually executed (they won't; see Pitfall 4). Look for Cosmos DB writes as the ground truth.
- [ ] **HITL thread isolation**: Follow-up classification succeeds — but verify the second run did NOT see conversation history from the first run contaminating its classification decision
- [ ] **Streaming event completeness**: SSE stream shows `RUN_FINISHED` — but verify `CLASSIFIED` or `MISUNDERSTOOD` custom events were also emitted (they're emitted AFTER the agent run, at the end of the adapter's generator)
- [ ] **Managed identity in Container Apps**: Works locally with `AzureCliCredential` — but test explicitly with the Container App's managed identity by checking Azure Monitor logs for auth errors after deployment
- [ ] **Thread accumulation**: Application runs cleanly — but check Foundry portal thread count after 20 test runs; orphaned threads should be visible and manageable

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| HandoffBuilder incompatibility discovered after major build | HIGH | Stop, delete `HandoffBuilder` / `AGUIWorkflowAdapter` code, choose new multi-agent pattern (code-based orchestration or Workflows), rebuild AG-UI adapter. Budget 1-2 days. |
| Tool registration at runtime discovered late | LOW | Move tool assignment from `run()` call to `as_agent()` call. Requires updating agent creation code only. |
| Agent accumulation (hundreds of stale agents in portal) | LOW | Batch delete via SDK loop: `for agent in project_client.agents.list(): project_client.agents.delete_agent(agent.id)`. Add ID management going forward. |
| RBAC misconfiguration in production | MEDIUM | Add correct role assignment via Azure portal or `az role assignment create`. Container App restart picks up new permissions. |
| HITL conversations contaminated by thread history | MEDIUM | Update follow-up endpoint to always create new Foundry thread (not add to existing). Deploy updated endpoint. Existing orphaned threads have no cost impact. |
| `AGUIWorkflowAdapter` does not produce events after Foundry migration | HIGH | Full rewrite of streaming adapter for `AgentResponseUpdate` event types. The filtering logic is sound; only the event type handling needs replacement. Budget 1 day. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| HandoffBuilder incompatibility | Phase 1 (delete HandoffBuilder before starting) | No `HandoffBuilder` import anywhere in codebase |
| Runtime tool registration | Phase 1 (single-agent Classifier baseline) | `classify_and_file` appears in tool call events; Cosmos DB shows new documents |
| `should_cleanup_agent` defaults | Phase 1 (agent ID management) | Foundry portal shows exactly 2 agents (Orchestrator, Classifier) that persist across restarts |
| Connected Agents + local tools | Phase 2 (multi-agent pattern decision) | Explicit decision documented: code-based orchestration OR Azure Functions for Cosmos DB tools |
| HITL thread contamination | Phase 3 (HITL validation) | Follow-up classification uses fresh Foundry thread; verified by inspecting thread message history |
| Async credential mismatch | Phase 1 (credential audit) | All credential imports from `azure.identity.aio`; tested in Container Apps before phase ends |
| RBAC gaps | Phase 1 (infrastructure setup) | SDK creates agent locally; Container App creates agent in staging before code review |
| AGUIWorkflowAdapter rewrite | Phase 2 (streaming layer) | Mobile app receives CLASSIFIED event after Cosmos DB write; MISUNDERSTOOD event triggers follow-up UI |

---

## Sources

- [Python 2026 Significant Changes Guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — HIGH confidence, official Microsoft docs updated 2026-02-21
- [AzureAIAgentClient Class Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) — HIGH confidence, official API reference; documents `should_cleanup_agent` default
- [Microsoft Foundry Agents Documentation](https://learn.microsoft.com/en-us/agent-framework/agents/providers/azure-ai-foundry) — HIGH confidence, official docs updated 2026-02-17
- [Connected Agents How-To](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — HIGH confidence; documents "cannot call local functions" limitation explicitly
- [Function Calling with Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools-classic/function-calling?view=foundry-classic) — HIGH confidence; documents polling/requires_action pattern and 10-minute run expiration
- [Foundry Agent Service Quotas and Limits](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/quotas-limits?view=foundry-classic) — HIGH confidence; documents 128 tool limit, 100,000 message thread limit
- [RBAC for Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry?view=foundry-classic) — HIGH confidence; documents "Azure AI User" role requirements
- [agent-framework GitHub Issue #3097](https://github.com/microsoft/agent-framework/issues/3097) — HIGH confidence; confirms HandoffBuilder + AzureAIClient 400 error root cause
- [Connected Agents Removed from New Portal](https://learn.microsoft.com/en-us/answers/questions/5631003/new-ai-foundry-experience-no-more-connected-agents) — MEDIUM confidence; Q&A forum; documents Connected Agents removal from new portal experience
- [Agent Accumulation Discussion](https://github.com/orgs/azure-ai-foundry/discussions/18) — MEDIUM confidence; community discussion confirming agent accumulation pattern and reuse workaround
- [AzureAIClient Runtime Tool Warning](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — HIGH confidence; documents "logs warning when runtime tools differ from creation-time configuration"

---
*Pitfalls research for: Foundry Agent Service migration — Second Brain v2.0*
*Researched: 2026-02-25*
