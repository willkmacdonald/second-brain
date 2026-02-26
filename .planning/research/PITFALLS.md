# Pitfalls Research

**Domain:** Adding proactive specialist agents, push notifications, geofencing, and scheduled execution to an existing FastAPI/Expo system with concurrent Foundry Agent Service migration
**Researched:** 2026-02-25
**Confidence:** MEDIUM-HIGH — Foundry Agent Service SDK is RC1; Connected Agents pattern is evolving rapidly. Push notification and geofencing pitfalls are well-documented. Proactive UX pitfalls are backed by CHI 2025 research. Cosmos DB concurrency is thoroughly documented.

---

## Critical Pitfalls

### Pitfall 1: HandoffBuilder Is Fundamentally Incompatible with AzureAIAgentClient

**What goes wrong:**
You swap `AzureOpenAIChatClient` for `AzureAIAgentClient` in the constructor, keep the existing `HandoffBuilder` + `AGUIWorkflowAdapter`, and expect the multi-agent pipeline to keep working. It fails with HTTP 400 Invalid Payload errors during the second agent invocation. The Orchestrator runs fine; the Classifier never receives the handoff.

**Why it happens:**
`HandoffBuilder` works by injecting synthetic transfer tools that intercept and re-route conversation history between agents in-process. `AzureAIAgentClient` routes tool calls through the Foundry Agent Service REST API, which applies strict JSON schema validation. When `HandoffBuilder` serializes conversation history to pass to the Classifier, the payload fails Azure's schema validation: missing `type` properties on message objects, content arrays lacking required `annotations` fields, `input` structured as an array when the API expects a string. Confirmed in agent-framework GitHub issue #3097.

**How to avoid:**
Treat `HandoffBuilder` + `AGUIWorkflowAdapter` as dead code from the start of this migration. The replacement is one of:
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

### Pitfall 2: Connected Agents Cannot Call Local Python Functions

**What goes wrong:**
You register the Classifier (or a specialist agent) as a Connected Agent on the Orchestrator. The Orchestrator successfully invokes the sub-agent. But the sub-agent's local Python functions (`classify_and_file`, `request_misunderstood`, `mark_as_junk`) do not execute. The agent runs but produces no Cosmos DB writes.

**Why it happens:**
The official Connected Agents documentation states explicitly: "Connected agents cannot call local functions using the function calling tool." Connected Agents delegates to sub-agents via the Foundry service's internal routing — sub-agent tool calls are processed remotely, not in your FastAPI process. The sub-agent's `requires_action` state (which is how local Python tools are called in the standard polling model) is handled server-side in the Connected Agents pattern, not exposed to your application code.

This is the critical limitation for the Second Brain: the specialist agents' ability to call tools that write to Cosmos DB in your FastAPI process is incompatible with the Connected Agents pattern as currently documented.

**How to avoid:**
For v2.0, use code-based orchestration (not Connected Agents) for any agent that calls local Python `@tool` functions. In your FastAPI endpoint, call each agent's `agent.run()` sequentially based on routing logic. Local tools execute normally in this model. Reserve Connected Agents for v3.0 when `classify_and_file` and similar tools are migrated to Azure Functions for server-side execution.

**Warning signs:**
- Sub-agent tools never execute when using Connected Agents
- No `ToolCallStartEvent` events from the sub-agent
- The sub-agent produces text responses but never writes to Cosmos DB
- Foundry portal shows agent invocations but no tool calls within sub-agent runs

**Phase to address:**
Foundry Migration Phase (multi-agent pattern decision). Make the code-based vs Connected Agents decision explicit before beginning multi-agent implementation. Do not invest time implementing Connected Agents if local Python function tools are required.

---

### Pitfall 3: The `should_cleanup_agent=True` Default Destroys Persistent Agent Value

**What goes wrong:**
`AzureAIAgentClient` defaults to `should_cleanup_agent=True`. Every time the FastAPI lifespan exits — including on Container App scale-to-zero — it deletes the server-side agent resource. On each restart you get a new agent with a new ID. Specialist agent IDs stored in connected agent registrations become invalid. The Foundry portal accumulates hundreds of deleted agent entries.

**Why it happens:**
The default is designed for single-script use where you create, use, and delete an agent in one execution. FastAPI's lifespan pattern exits on shutdown — triggering cleanup. The agent that was persistent through the day's operation is deleted when the Container App scales to zero overnight.

**How to avoid:**
For long-lived FastAPI deployments, use persistent agents by ID:
```python
client = AzureAIAgentClient(
    credential=credential,
    agent_id=settings.classifier_agent_id,  # env var: CLASSIFIER_AGENT_ID
    should_cleanup_agent=False  # Never delete externally-managed agents
)
```
Create specialist agents once during infrastructure setup, store their IDs as environment variables, and reference them by ID in the deployed application. This applies to ALL specialist agents (Admin Agent, Projects Agent, People Agent, Ideas Agent).

**Warning signs:**
- Azure portal shows many agents named "Classifier" or "Admin Agent" from previous runs
- Agent IDs change on every Container App restart
- Connected Agent configurations break after restarts because the sub-agent ID changed
- Foundry portal shows deleted agents accumulating rapidly

**Phase to address:**
Foundry Infrastructure Phase (before writing any agent creation code). Establish the agent creation and ID management strategy before implementation.

---

### Pitfall 4: Tools Must Be Registered at Agent Creation Time, Not at Runtime

**What goes wrong:**
You create the `AzureAIAgentClient` and attach tools during `agent.run()` by passing them as kwargs or at call time. The tools are silently ignored, or the client logs a warning that "Azure AI Agent Service does not support runtime tool changes." The specialist agent runs but never calls its domain tools — the Admin Agent produces text instead of calling `schedule_task`, the People Agent never calls `add_person_note`.

**Why it happens:**
`AzureOpenAIChatClient` allowed tools to be supplied at call time as part of the Chat Completions API payload. `AzureAIAgentClient` creates a server-side agent resource at startup. The tools are registered on that server-side resource at creation time and cannot be changed without updating the agent resource. The Agent Framework RC1 docs explicitly state this: "AzureAIClient now logs a warning when runtime tools or structured_output differ from the agent's creation-time configuration."

**How to avoid:**
Always pass tools to `as_agent()` or `create_agent()` at the moment the server-side agent resource is created:
```python
# WRONG: tools at run time
agent = client.as_agent(name="AdminAgent", instructions="...")
await agent.run("Schedule this task", tools=[schedule_task])  # silently ignored

# CORRECT: tools at creation time
agent = client.as_agent(
    name="AdminAgent",
    instructions="...",
    tools=[schedule_task, list_tasks, complete_task]
)
await agent.run("Schedule this task")
```
For the Second Brain, each specialist agent's full tool set must be wired at the lifespan startup before the agent is registered with Foundry.

**Warning signs:**
- "does not support runtime tool changes" in application logs
- Agent produces text responses but never calls domain tools
- Tools work with `AzureOpenAIChatClient` but vanish with `AzureAIAgentClient`
- `ToolCallStartEvent` events are absent from the SSE stream

**Phase to address:**
Single-Agent Baseline Phase. Verify each specialist agent's tools appear in tool call events before building the routing layer.

---

### Pitfall 5: `AGUIWorkflowAdapter` Event Filtering Does Not Port to Foundry Streaming

**What goes wrong:**
The existing `AGUIWorkflowAdapter` (340+ lines) contains workflow-specific logic: Orchestrator echo filtering, Classifier text buffering, `function_call.name` inspection to detect classification outcome, custom event emission (`CLASSIFIED`, `MISUNDERSTOOD`). When you replace the workflow with `AzureAIAgentClient` streaming, the event surface changes completely. `WorkflowEvent`, `executor_invoked`, `executor_completed` are gone. The `isinstance(event, WorkflowEvent)` checks never match; the stream produces no events to the mobile app.

**Why it happens:**
`AGUIWorkflowAdapter` was written for `Workflow` (the `HandoffBuilder` output), which emits `WorkflowEvent` types. `AzureAIAgentClient` streaming uses the Foundry Runs API event stream, which produces `AgentResponseUpdate` objects with different content types. The adapter's type checks will never match.

**How to avoid:**
Treat the adapter as a complete rewrite, not a migration. The new `FoundrySSEAdapter` must:
1. Call each agent via `agent.run(..., stream=True)`
2. Iterate `AgentResponseUpdate` objects from the Foundry stream
3. Inspect `update.contents` for `function_call` content to detect tool invocations
4. Emit `StepStartedEvent` / `StepFinishedEvent` for each agent boundary (synthetic, not emitted by Foundry natively)
5. Emit `CLASSIFIED` / `MISUNDERSTOOD` custom events based on tool call detection

Budget significant time (~150 lines from scratch). The core filtering logic (detect classification tool, filter echo, emit custom events) is reusable in concept — but the event type handling is a complete replacement. Test against the mobile client after every structural change; the mobile app will silently show no activity if the SSE stream is malformed.

**Warning signs:**
- Empty SSE streams despite agents running successfully
- `isinstance(event, WorkflowEvent)` is always False
- StepStarted/StepFinished events never appear in the mobile app
- CLASSIFIED custom events never arrive even when Cosmos DB shows a successful write

**Phase to address:**
FoundrySSEAdapter Phase. Rewrite the streaming layer before touching the FastAPI endpoint wiring or specialist agents.

---

### Pitfall 6: Expo Push Token Never Arrives If Notification Permissions Not Requested in Correct State

**What goes wrong:**
You call `getExpoPushTokenAsync()` without first checking and requesting notification permissions. On iOS, the call silently returns without a token or throws. On Android 13+, the runtime permission (`POST_NOTIFICATIONS`) was never requested so background push notifications fail silently. You build the entire proactive notification backend, test it with a token that only works in the Expo Go development environment, and discover production tokens never arrive.

**Why it happens:**
iOS requires explicit permission grant before APNs will issue a token. If the user has not granted notification permissions (or if you call `getExpoPushTokenAsync()` before permissions are resolved), the token request fails. On Android 13+, `android.permission.POST_NOTIFICATIONS` must be requested at runtime — apps targeting Android SDK 33+ must explicitly ask. Additionally, Expo Go uses a shared `experienceId` which produces tokens that only work in the Expo environment — production (standalone) builds produce different tokens.

**How to avoid:**
Always follow the correct sequence:
```javascript
const { status } = await Notifications.requestPermissionsAsync();
if (status !== 'granted') {
  // Handle denied permissions — do NOT call getExpoPushTokenAsync()
  return;
}
const token = await Notifications.getExpoPushTokenAsync({
  projectId: Constants.expoConfig.extra.eas.projectId,
});
```
Store the token on the backend immediately. Use a development build (not Expo Go) for all push notification testing. Register for notifications on every app launch and compare the new token against the stored token — update the backend if it has changed.

**Warning signs:**
- `getExpoPushTokenAsync()` returns undefined or throws without explicit permission check
- Token works in Expo Go but fails when installed as standalone app
- iOS users who denied notifications at first launch can never receive proactive nudges
- Android 13+ users never prompted for notification permission

**Phase to address:**
Push Notification Infrastructure Phase (before building any proactive agent logic). Validate the full token registration → Expo Push API → device delivery cycle in a production build before writing backend notification logic.

---

### Pitfall 7: Expo Push Notification Two-Stage Receipt System Is Easy to Ignore

**What goes wrong:**
You send a push notification via the Expo Push API, receive a `ticket` with `status: "ok"`, and assume the notification was delivered. In practice, `status: "ok"` on the ticket means only that Expo's servers received your request — NOT that APNs/FCM delivered it to the device. Real delivery errors (invalid token, device unregistered, credentials expired) only appear in the **receipt** system, which requires a separate polling call 15 minutes later. You ship the proactive nudge feature believing notifications are working, but real failures go undetected.

**Why it happens:**
Expo uses a two-stage system: tickets confirm Expo received your message, receipts confirm APNs/FCM delivery. Because the receipt call requires polling (not a webhook), it's easy to skip during development. Developers typically test with their own device where delivery works fine, and never see the receipt errors that would surface with invalid tokens.

**How to avoid:**
Implement both stages:
1. **Ticket stage**: Send notification, store receipt ID with the notification record.
2. **Receipt stage**: After 15 minutes, call `getExpoPushReceiptAsync()` with stored receipt IDs. Check for `DeviceNotRegistered` (delete the token), `InvalidCredentials` (fix APNs/FCM configuration), `MessageRateExceeded` (add backoff).

For a single-user system (Will only), the implementation is minimal: one stored push token, one receipt check per notification batch. The critical action is removing or refreshing the token on `DeviceNotRegistered` so the next proactive nudge doesn't fail silently.

**Warning signs:**
- Ticket shows `status: "ok"` but no notification appears on device
- No receipt-checking code in the backend
- Notification delivery success rate never monitored
- App reinstall causes push to stop working (token changed on Android, not updated on backend)

**Phase to address:**
Push Notification Infrastructure Phase. Build the receipt polling mechanism before connecting it to agent-triggered notifications.

---

### Pitfall 8: iOS Background Geofencing Stops When App Is Force-Quit by User

**What goes wrong:**
You implement geofencing to trigger "you've arrived at the office" notifications (e.g., Admin Agent nudges work captures). During testing, geofencing works reliably. In real use, Will force-quits the app (double-tap home, swipe up). Geofencing monitoring silently stops. No error is logged. No notification arrives when location criteria are met. The feature appears to work in QA and silently stops working in production.

**Why it happens:**
On iOS, `Location.stopGeofencingAsync()` is called implicitly when the app is force-terminated. iOS distinguishes between "backgrounded" (location monitoring continues) and "force-quit" (monitoring stops). This is an Apple platform constraint: apps cannot monitor geofences after being force-quit. The system will restart the app on a new geofence event only if the app was backgrounded normally, not force-quit.

On Android, behavior depends on the device vendor. Stock Android (Pixel) restarts the app for geofence events even after force-quit. Many OEM implementations (Samsung, Xiaomi, OnePlus) treat force-quit as a hard kill and do not restart the app.

**How to avoid:**
Do not design proactive geofencing as a reliable trigger for time-sensitive notifications. Design for "best effort": geofencing nudges are helpful when they work, but the system degrades gracefully when they don't. Show a manual "sync location" option in the app for cases where the user knows geofencing has stopped. Document this limitation in comments to avoid re-investigating during future debugging.

Expo Location's managed workflow config plugin (no ejection required) is the right choice for basic geofencing. Limit to 5-10 regions (well within iOS's 20-region hard limit and Android's 100-region limit) to avoid priority-based region eviction.

**Warning signs:**
- Geofence notifications only work when tested from Expo Go (not production)
- Notifications stop appearing after Will kills the app from the app switcher
- Android OEM devices behave differently than iOS (expected, not a bug)
- Battery drain complaints from testing with `Accuracy.Highest` — switch to `Accuracy.Balanced` and increase `timeInterval`

**Phase to address:**
Proactive Geofencing Phase. Document the force-quit limitation explicitly in the phase verification criteria so it's a known accepted behavior, not a bug report.

---

### Pitfall 9: Notification Fatigue Kills the Proactive Agent Feature

**What goes wrong:**
The proactive specialist agents are enthusiastic. The Admin Agent reminds Will of overdue tasks three times a day. The Projects Agent sends nudges whenever a project item has been idle for 48 hours. The People Agent triggers whenever Will hasn't logged a contact in two weeks. After one week, Will disables notifications for the app entirely. The proactive feature — the core differentiation of v2.0 — becomes useless.

**Why it happens:**
Research from CHI 2025 ("Need Help? Designing Proactive AI Assistants") found that increasing suggestion frequency can reduce user preference for the proactive assistant by half, even when the suggestions are accurate. Users accept proactive AI behavior when it aligns with their expectations about frequency and relevance — and reject the entire feature when it overshoots, even slightly.

For a personal tool like the Second Brain, the user (Will) is both the developer and the user. There's a temptation to build enthusiastic agents because "I'll know when to ignore them." In practice, notification fatigue bypasses rational filtering — the instinct is to mute the whole category.

**How to avoid:**
Apply strict defaults before launch:
- **One notification per domain per day maximum** — Admin Agent can fire once per day, not on every trigger event.
- **Quiet hours by default** — No notifications before 8am or after 9pm.
- **Batching** — Collect nudges across a session and send a single digest rather than one notification per item.
- **Relevance threshold** — Only fire if the agent's confidence that the nudge is actionable exceeds a threshold (e.g., 0.8). Skip marginal cases.
- **Easy opt-out per agent** — A setting to silence "Admin Agent nudges" specifically, without disabling all notifications.

Start with minimal nudge frequency and increase only if Will actively wants more. Err toward silence.

**Warning signs:**
- More than 2 push notifications per day during testing
- Nudge logic fires on every idle item without batching
- No configurable quiet hours
- No per-agent mute control in settings

**Phase to address:**
Proactive Nudge UX Phase. Define notification budget before writing any agent scheduling logic. Build throttling and quiet hours into the notification dispatcher, not as an afterthought.

---

### Pitfall 10: Scheduled Agent Execution on Azure Container Apps Uses UTC Only — No Timezone Support

**What goes wrong:**
You configure a Container Apps scheduled job to run the "end of day digest" agent at 5pm. The cron expression `0 17 * * *` schedules it at 5pm UTC — which is midnight in BST (British Summer Time) or 9am in PST. The daily digest arrives at the wrong time and the feature feels broken. Worse: when daylight saving time changes, the effective local time shifts by an hour with no warning.

**Why it happens:**
Azure Container Apps scheduled jobs evaluate cron expressions in UTC with no timezone configuration option. This is a confirmed platform limitation with an open GitHub issue (microsoft/azure-container-apps #1109). Unlike Kubernetes CronJobs (which support `timezone` in the spec) or Azure Functions Timer triggers (which support `WEBSITE_TIME_ZONE`), Container Apps Jobs have no timezone field. The only workarounds are: use UTC offsets and manually update them twice a year for daylight saving time, or add a meta-job that updates other jobs' cron expressions.

**How to avoid:**
For a single-user UK-based system (Will), compute the UTC equivalent of the desired local time and hardcode it:
- UK GMT (winter): Add 0 hours → `0 17 * * *` for 5pm local
- UK BST (summer): Subtract 1 hour → `0 16 * * *` for 5pm local

Document this as a known manual maintenance task (update the cron expression twice a year). Alternatively, use Azure Functions Timer triggers instead of Container Apps Jobs for scheduling — Functions support `WEBSITE_TIME_ZONE` setting and handle DST automatically.

For proactive agent scheduling that is more frequent (e.g., every 2 hours), UTC drift matters less — a 2-hour interval always runs every 2 hours regardless of timezone.

**Warning signs:**
- Daily digest arrives at the wrong local time
- Scheduled job timing "shifts" in March and October without code changes
- Container Apps Job cron expression does not have a `timeZone` field (confirmed expected behavior, not a bug)

**Phase to address:**
Scheduled Agent Execution Phase. Choose the scheduling mechanism (Container Apps Job vs Azure Functions Timer) before writing the scheduler. If precision local time matters, use Azure Functions.

---

### Pitfall 11: Credential Scope Change Breaks Local Development (Async vs Sync)

**What goes wrong:**
The existing codebase uses `DefaultAzureCredential()` (sync, from `azure.identity`) for `AzureOpenAIChatClient`. `AzureAIAgentClient` requires `AsyncTokenCredential` from `azure.identity.aio`. If you pass the sync credential, the client either silently falls back to a broken auth state or raises a `TypeError` at runtime. In Container Apps with managed identity, the sync credential chain includes `ManagedIdentityCredential` — but it is the wrong type for the async client.

**Why it happens:**
`AzureAIAgentClient` is designed as an async client throughout. All Azure AI clients in the Agent Framework RC1 release require `AsyncTokenCredential`. The sync `DefaultAzureCredential` was previously used because `AzureOpenAIChatClient` accepted it. This is a silent breaking change for anyone who copies the existing credential setup without reading the type signature.

**How to avoid:**
Replace all credential imports:
```python
# OLD (sync — will not work with AzureAIAgentClient)
from azure.identity import DefaultAzureCredential

# NEW (async — required for AzureAIAgentClient)
from azure.identity.aio import DefaultAzureCredential

# Do NOT share the same credential object between AzureAIAgentClient and
# other sync Azure clients (Key Vault, Cosmos DB) — separate instances required
```

Use `async with` for credential lifecycle in FastAPI lifespan. Do NOT share the same credential object between `AzureAIAgentClient` and other sync Azure clients.

**Warning signs:**
- `TypeError: argument of type 'DefaultAzureCredential' is not iterable` or similar
- Authentication works in unit tests but fails when the FastAPI lifespan runs
- Key Vault fetch succeeds (sync credential) but Foundry agent creation fails (async credential mismatch)
- Works locally with `az login` but fails in Container Apps

**Phase to address:**
Foundry Infrastructure Phase. Update credential handling before writing any Foundry-specific code.

---

### Pitfall 12: RBAC Assignment Has Two Scopes — Both Are Required

**What goes wrong:**
You create the AI Foundry project, assign yourself "Azure AI User" at the project level, and try to create agents via SDK. You get 403 Forbidden. Or: agent creation works locally but the deployed Container App returns 401. Or: local dev works but managed identity in production fails.

**Why it happens:**
Foundry Agent Service RBAC has two distinct scopes that are both required:
1. **Developer/user principal**: The human developer's Entra ID account needs "Azure AI User" on the Foundry project resource.
2. **Application/managed identity**: The Container App's system-assigned managed identity needs "Azure AI User" on the Foundry project resource.

These are separate role assignments at the same resource scope. Additionally, the Foundry project's managed identity needs access to the underlying Azure OpenAI resource — this is a third assignment many people miss.

**How to avoid:**
Before writing any code, assign all three:
1. Developer's Entra ID → "Azure AI User" on the Foundry project
2. Container App's managed identity → "Azure AI User" on the Foundry project
3. Foundry project's managed identity → "Cognitive Services User" on the Azure OpenAI resource

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
Foundry Infrastructure Phase. Do all role assignments before writing a single line of SDK code. Document the specific resource IDs and role assignments.

---

### Pitfall 13: HITL Flow Is Broken by Server-Managed Threads

**What goes wrong:**
The existing HITL flow works by pausing the workflow, saving the `inbox_item_id` from the SSE stream, and resuming via a separate `/api/ag-ui/follow-up` POST that re-runs the workflow. With Foundry Agent Service, conversation state lives in server-managed threads. When you create a new `agent.run()` call for the follow-up on the same thread, the thread's message history now includes the full first-pass exchange, which confuses the Classifier into trying to continue from where it left off rather than reclassifying from scratch.

**Why it happens:**
With `AzureOpenAIChatClient`, each follow-up request creates a fresh in-memory workflow with no knowledge of the previous run. With `AzureAIAgentClient`, threads persist server-side. A new run on the same thread gives the agent its full conversation history, including the original (wrong) classification attempt.

**How to avoid:**
Always create a fresh Foundry thread for each follow-up classification run. Pass the combined text (original + follow-up) as the user message to the new thread. This is functionally identical to the v1 behavior — no conversation history contamination. The trade-off is no conversational continuity across HITL rounds, but the Second Brain's HITL flow already re-runs classification from scratch.

**Warning signs:**
- Follow-up classification always returns the same (wrong) bucket as the first pass
- The Classifier asks "What did you mean by X?" again on the second round when it already knows
- Agent responses reference "as I mentioned earlier" when the earlier mention was in a different conversation
- Thread message count grows unexpectedly on HITL-heavy captures

**Phase to address:**
HITL Validation Phase. After migrating the single-agent baseline, verify HITL flows with new thread-per-follow-up strategy before declaring migration complete.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Creating agents at every startup instead of using persistent IDs | No env var management needed | New agent created on every deploy; IDs drift; Connected Agents point to stale IDs; portal fills with duplicates | Never. Store agent IDs as env vars from day one. |
| Using sync `DefaultAzureCredential` with `AzureAIAgentClient` | Copy-paste from existing code | Auth fails silently or with cryptic errors; works locally, breaks in Container Apps | Never. Use `azure.identity.aio` from the start. |
| Keeping `HandoffBuilder` during early migration "just in case" | Preserve existing orchestration | `HandoffBuilder` and `AzureAIAgentClient` cannot coexist. Dead code confuses debugging. | Never. Delete `HandoffBuilder` code when the Foundry client is introduced. |
| Skipping push notification receipt polling | Simpler implementation | Real delivery failures go undetected. Push token becomes stale after uninstall. Proactive nudges silently fail. | Never for production. Acceptable in initial development if receipt check is a TODO item. |
| Firing a proactive nudge on every trigger event without throttling | Maximum responsiveness | Notification fatigue causes Will to disable all notifications within days. Core differentiating feature disabled permanently. | Never. Build throttling before connecting agent scheduler to push delivery. |
| Hardcoding cron schedules in UTC with no comment | Works immediately | Requires debugging twice a year when clocks change. Wrong local time delivered to user. | Only if schedule is timezone-agnostic (e.g., "every 6 hours"). Never for "end of business day" type schedules. |
| Skipping thread cleanup for development | Faster iteration | Thousands of orphaned Foundry threads accumulate; portal becomes unusable for debugging; potential future storage costs | Acceptable during initial development; add cleanup before first real use. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `AzureAIAgentClient` + FastAPI lifespan | Creating client inside endpoint handler on every request | Create client once in `lifespan()`, store on `app.state`. Client is reusable across requests. |
| Foundry threads + Cosmos DB Inbox items | Using Foundry thread ID as the document ID for Cosmos DB | They are separate concepts with separate IDs. Cosmos DB has `inbox_item_id` (your UUID). Foundry has `thread_id` (service-managed). Never conflate them. |
| Expo push notifications + backend | Storing the token only in memory at login | Store the push token in Cosmos DB `User` document on every app launch and token refresh event. Proactive agents need the token at any time, not just during active sessions. |
| Expo push notifications + Expo Go testing | Testing push delivery in Expo Go | Expo Go tokens only work within the Expo developer environment. Use development builds (`eas build --profile development`) for all push notification testing. |
| Cosmos DB + concurrent specialist agents | Letting two agents race to write the same Inbox document | Use ETag-based optimistic concurrency (`if_match_etag`) on all Cosmos DB writes from agent tools. On 412 Precondition Failed, reload and retry. For the Second Brain, each capture has a unique `inbox_item_id` — agents should only write to their own capture document, preventing the race. |
| Container Apps scheduled jobs + timezone | Setting cron to local time without UTC conversion | All Container Apps cron expressions are UTC. Compute UTC equivalent, document the conversion, and update twice a year for daylight saving. |
| Geofencing + Expo Go testing | Testing geofence events in Expo Go | Expo Go's TaskManager does not support background execution on iOS. Geofencing requires a development build. |
| Multi-agent + AG-UI thread_id | Generating a new `thread_id` for every endpoint call | The `thread_id` in AG-UI SSE events must be stable for the duration of a capture session (initial run + any follow-up HITL). Generate once per capture, carry it through all follow-up calls. |
| `should_cleanup_agent` | Default `True` deletes agent on `close()` | Set `should_cleanup_agent=False` for agents created externally (by ID). Only use `True` for throwaway test agents. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `DefaultAzureCredential` probing all credential sources | 2-5 second latency on first request after cold start in Container Apps | Use `ManagedIdentityCredential` directly in Container Apps — skip the credential chain probing | Every cold start; worse with scale-to-zero configuration |
| Creating a new `AgentsClient` per request | Rate limit errors; 429s under load; connection overhead | Create one `AgentsClient` in lifespan, share across requests via `app.state` | Under any concurrent load |
| Polling for run completion without streaming | Each capture takes 3-5 seconds of silent waiting while polling; users see no progress | Use `agent.run(..., stream=True)` to get real-time events | From the first user interaction |
| Geofencing with `Accuracy.Highest` | Significant battery drain; iOS may flag app as battery drainer | Use `Accuracy.Balanced` and `timeInterval >= 10 seconds` — battery usage drops 70% | From first user with "battery saver" mode enabled |
| Expo push notifications rate limit | 600 req/sec per project cap; batch failures under load | For single-user app, irrelevant in practice — cap is 600/sec. Only an issue if testing bulk sends. | At 600 notifications/second across the project |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing `AZURE_AI_PROJECT_ENDPOINT` (contains project name) in client-visible logs | Exposes project endpoint URL — low-sensitivity but bad hygiene | Log agent IDs and run IDs, not the full project endpoint. |
| Using `AzureCliCredential` in Container Apps deployment | Container Apps does not have `az login` state; all requests fail | Use `ManagedIdentityCredential` explicitly in production. |
| Storing Expo push token in plaintext in an insecure location | Token allows sending notifications to Will's device without authentication | Store push token in Cosmos DB, protected by the same authentication layer as all other data. Push endpoint protected by existing API key. |
| Sending proactive notifications without rate limiting from the backend | Runaway agent loop could send thousands of notifications | Backend notification dispatcher must enforce a hard cap (e.g., max 10 notifications per 24 hours per agent) regardless of how many trigger events occur. |
| Same managed identity for multiple Azure resources with different access levels | Overly-permissive managed identity | Principle of least privilege: grant the Container App's managed identity only "Azure AI User" on Foundry, only "Key Vault Secrets User" on Key Vault. Nothing more. |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Too many proactive nudges per day | Will disables notifications for the app entirely — core feature becomes permanently unusable | Enforce one notification per specialist agent per day maximum, with quiet hours (8am-9pm local) and explicit opt-out per agent type |
| Notification that requires opening the app to act on | Friction causes ignoring the notification | Include the actionable summary in the notification body. Use notification actions (iOS: inline action buttons) for simple responses like "mark done" or "snooze 4 hours" |
| Geofence trigger that fires before Will is settled at location | Notification arrives during commute, not when actionable | Add a 5-minute stabilization timer: only trigger the notification if Will has been within the geofence for 5+ continuous minutes |
| Proactive nudge about something Will just dealt with | Stale agent state is embarrassing and erodes trust | Specialist agents must read current document state from Cosmos DB at nudge generation time, not from cached state that may be hours old |
| Daily digest that summarizes everything (too long to read) | Will skips reading it; agent adds no value | Digest must be ≤ 3 items, curated by urgency and actionability. An agent that tells you 14 things needs telling you nothing. |

---

## "Looks Done But Isn't" Checklist

- [ ] **Agent persistence**: `agent.run()` returns a result — but verify the agent was NOT recreated (check Foundry portal; agent ID should be stable across restarts if using `agent_id=`)
- [ ] **Tool execution**: The specialist agent runs and returns a response — but verify the `@tool` function actually wrote a document to Cosmos DB (check Cosmos DB Data Explorer, not just the SSE response)
- [ ] **Connected Agents tool execution**: Connected Agent invokes the sub-agent — but verify local Python functions actually executed (they won't; see Pitfall 2). Look for Cosmos DB writes as the ground truth.
- [ ] **Push token stored**: App registers for push notifications — but verify the token is stored in Cosmos DB and readable by the backend agent scheduler (not just logged to console in development)
- [ ] **Push delivery verified**: Backend sends push notification and gets `status: "ok"` on the ticket — but check push receipts after 15 minutes to verify APNs/FCM actually delivered it
- [ ] **Notification throttling active**: One proactive nudge fires during testing — but verify that a second trigger event within 24 hours does NOT send a second notification
- [ ] **Geofencing in production build**: Geofencing works in Expo Go during development — but test geofencing events in a development build (Expo Go's TaskManager does not support background execution on iOS)
- [ ] **HITL thread isolation**: Follow-up classification succeeds — but verify the second run did NOT see conversation history from the first run contaminating its classification decision
- [ ] **Streaming event completeness**: SSE stream shows `RUN_FINISHED` — but verify `CLASSIFIED` or `MISUNDERSTOOD` custom events were also emitted (emitted AFTER the agent run, at the end of the adapter's generator)
- [ ] **Managed identity in Container Apps**: Works locally with `AzureCliCredential` — but test explicitly with the Container App's managed identity by checking Azure Monitor logs for auth errors after deployment
- [ ] **Scheduled job UTC conversion**: Scheduled job runs at the expected local time — but verify behavior after a daylight saving time transition

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| HandoffBuilder incompatibility discovered after major build | HIGH | Stop, delete `HandoffBuilder` / `AGUIWorkflowAdapter` code, choose code-based orchestration, rebuild `FoundrySSEAdapter`. Budget 1-2 days. |
| Tool registration at runtime discovered late | LOW | Move tool assignment from `run()` call to `as_agent()` call. Requires updating agent creation code only. |
| Agent accumulation (hundreds of stale agents in portal) | LOW | Batch delete via SDK loop: `for agent in project_client.agents.list(): project_client.agents.delete_agent(agent.id)`. Add ID management going forward. |
| RBAC misconfiguration in production | MEDIUM | Add correct role assignment via Azure portal or `az role assignment create`. Container App restart picks up new permissions. |
| HITL conversations contaminated by thread history | MEDIUM | Update follow-up endpoint to always create new Foundry thread. Deploy updated endpoint. Existing orphaned threads have no cost impact. |
| `AGUIWorkflowAdapter` does not produce events after Foundry migration | HIGH | Full rewrite of streaming adapter for `AgentResponseUpdate` event types. Budget 1 day. |
| Push token not stored, proactive notifications failing | MEDIUM | Add token persistence to Cosmos DB on app launch. Requires one app update deployment. |
| Notification fatigue has caused Will to disable notifications | HIGH | Impossible to recover immediately — iOS notification permissions, once revoked, require manual re-enabling in Settings. Prevent this by enforcing throttling from day one. |
| Geofencing stopped after app force-quit | LOW (expected) | This is a platform limitation, not a recoverable bug. Document as accepted behavior. |
| Scheduled job at wrong local time | LOW | Update cron expression in Container Apps Job configuration (Azure portal or CLI). Takes effect on next trigger. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| HandoffBuilder incompatibility | Foundry Infrastructure Phase (delete before starting) | No `HandoffBuilder` import anywhere in codebase |
| Connected Agents + local tools | Foundry Multi-Agent Phase (explicit decision) | Explicit decision documented: code-based orchestration for v2.0; Connected Agents + Azure Functions for v3.0 |
| `should_cleanup_agent` defaults | Foundry Infrastructure Phase (agent ID management) | Foundry portal shows exactly N agents (one per specialist) that persist across restarts |
| Runtime tool registration | Single-Agent Baseline Phase | Each specialist agent's tools appear in tool call events; Cosmos DB shows new documents |
| AGUIWorkflowAdapter rewrite | FoundrySSEAdapter Phase | Mobile app receives CLASSIFIED event after Cosmos DB write; MISUNDERSTOOD event triggers follow-up UI |
| HITL thread contamination | HITL Validation Phase | Follow-up classification uses fresh Foundry thread; verified by inspecting thread message history |
| Async credential mismatch | Foundry Infrastructure Phase (credential audit) | All credential imports from `azure.identity.aio`; tested in Container Apps before phase ends |
| RBAC gaps | Foundry Infrastructure Phase | SDK creates agent locally; Container App creates agent in staging before code review |
| Push token permissions | Push Notification Infrastructure Phase | Development build confirms token arrives on device after permissions granted; token stored in Cosmos DB |
| Push receipt polling | Push Notification Infrastructure Phase | Receipt-polling code present; `DeviceNotRegistered` errors remove token from Cosmos DB |
| iOS geofencing + force-quit | Proactive Geofencing Phase | Force-quit limitation documented as accepted behavior in verification criteria; not treated as a bug |
| Notification fatigue | Proactive Nudge UX Phase | Throttling enforced at 1 notification/agent/day max; quiet hours configured; tested by triggering 10 events in 1 hour and confirming only 1 notification fires |
| Scheduled job UTC-only | Scheduled Agent Execution Phase | Cron expression and UTC conversion documented; tested across a simulated DST transition |
| Stale state in proactive agents | Specialist Agent Phase | Each specialist agent reads current Cosmos DB state at trigger time; verified by modifying a document and confirming the next nudge reflects the update |

---

## Sources

- [Python 2026 Significant Changes Guide](https://learn.microsoft.com/en-us/agent-framework/support/upgrade/python-2026-significant-changes) — HIGH confidence, official Microsoft docs updated 2026-02-21; documents async credential requirement and runtime tool warning
- [AzureAIAgentClient Class Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) — HIGH confidence; documents `should_cleanup_agent` default
- [Connected Agents How-To](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — HIGH confidence; documents "cannot call local functions" limitation explicitly
- [Function Calling with Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools-classic/function-calling?view=foundry-classic) — HIGH confidence; documents polling/requires_action pattern
- [RBAC for Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-foundry?view=foundry-classic) — HIGH confidence; documents "Azure AI User" role requirements
- [agent-framework GitHub Issue #3097](https://github.com/microsoft/agent-framework/issues/3097) — HIGH confidence; confirms HandoffBuilder + AzureAIClient 400 error root cause
- [Expo Push Notifications FAQ](https://docs.expo.dev/push-notifications/faq/) — HIGH confidence, official Expo docs; documents DeviceNotRegistered handling, token lifecycle
- [Send Notifications with Expo Push Service](https://docs.expo.dev/push-notifications/sending-notifications/) — HIGH confidence, official Expo docs; documents two-stage ticket/receipt system
- [Expo Location SDK](https://docs.expo.dev/versions/latest/sdk/location/) — HIGH confidence, official Expo docs; documents iOS 20-region limit, force-quit behavior, Android 100-region limit
- [Expo Push Notification Setup Caveats](https://www.sashido.io/en/blog/expo-push-notifications-setup-caveats-troubleshooting) — MEDIUM confidence; covers credential mismatches and Android Doze mode
- [Azure Container Apps Jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs) — HIGH confidence, official Microsoft docs; documents cron expression evaluation in UTC
- [Container Apps UTC-only Scheduled Jobs Issue #1109](https://github.com/microsoft/azure-container-apps/issues/1109) — HIGH confidence (official GitHub issue tracker); confirms no timezone support
- [Cosmos DB Optimistic Concurrency](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/database-transactions-optimistic-concurrency) — HIGH confidence, official Microsoft docs; documents ETag/412 pattern
- [Need Help? Designing Proactive AI Assistants (CHI 2025)](https://dl.acm.org/doi/full/10.1145/3706598.3714002) — HIGH confidence, peer-reviewed; documents 50% preference reduction from increased suggestion frequency
- [Handling Background Tasks in Expo 2025](https://flexapp.ai/blog/expo-background-tasks-guide) — MEDIUM confidence; covers background task limitations and workarounds
- [Making Expo Notifications Actually Work (Medium)](https://medium.com/@gligor99/making-expo-notifications-actually-work-even-on-android-12-and-ios-206ff632a845) — MEDIUM confidence; practical Android 12+ and iOS permission issues

---
*Pitfalls research for: Proactive Second Brain — Foundry migration + specialist agents with push notifications, geofencing, and scheduled execution*
*Researched: 2026-02-25*
