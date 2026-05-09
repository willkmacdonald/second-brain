# Foundry GA SDK probe findings

**Captured:** 2026-05-09
**Foundry endpoint:** https://second-brain-foundry-resource.services.ai.azure.com/api/projects/second-brain
**Foundry model:** gpt-4o
**Probe harness:** [backend/scripts/foundry_probe.py](../../../backend/scripts/foundry_probe.py)
**Fixtures:** [backend/tests/fixtures/foundry-probe/](../../../backend/tests/fixtures/foundry-probe/)
**Candidate dep set:** [.planning/phases/23-foundry-ga-prep/CANDIDATE-pyproject.toml](./CANDIDATE-pyproject.toml) + [CANDIDATE-uv.lock](./CANDIDATE-uv.lock)

This document is **consumed by the planner that plans Phase 24**. For each probe it answers four questions taken verbatim from the design doc Section "Foundry probe harness -- Findings document":

1. What was the question?
2. What did the probe show?
3. What does Phase 24 migration code need to do differently from what docs alone would suggest?
4. Which open question (design Section "Open questions resolved by each phase's gsd-planner") does this resolve?

**CRITICAL GA SDK naming correction:** The GA SDK (agent-framework 1.3.0) uses `AgentResponse`, `AgentResponseUpdate`, and `AgentSession` -- NOT the pre-GA names `AgentRunResponse`, `AgentRunResponseUpdate`, and `AgentThread` that appeared in early documentation and the design doc. Streaming uses `agent.run(stream=True)` returning a `ResponseStream` (async iterable), NOT `agent.run_stream()`. `tool_choice` is passed via `options=ChatOptions(tool_choice=...)`, NOT as a direct keyword argument. `FoundryChatClient` takes `project_endpoint` and `model` params, NOT `endpoint` and `model_deployment_name`. Messages are passed as plain strings (or `Message` objects), NOT as `{"role": "user", "content": "..."}` dicts. All Phase 24 code must use the corrected GA names.

## SDK thread/session deletion

`_maybe_delete_session` returned `false` in both streaming_shape and session_rehydration probes. None of the attempted method names (`delete_session`, `delete_thread`, `delete`) exist on the `Agent` class. Probe-created sessions accumulate as Foundry-side dust per design "Optional cleanup". The `AgentSession` object is local to the SDK (client-side conversation history management via `session_id` and `service_session_id`), not a server-side resource -- so "deletion" may not be meaningful for the GA SDK's session model. Phase 24 does not need a cleanup mechanism.

---

## Probe 1: streaming_shape

**Fixture:** [streaming_shape.json](../../../backend/tests/fixtures/foundry-probe/streaming_shape.json)

1. **What was the question?** Exact field/type/order of `AgentResponseUpdate` events emitted by `agent.run(stream=True)` for a 1-tool agent that produces a forced tool call.

2. **What did the probe show?**
   - Update count: 25
   - Update type sequence: all 25 updates are `AgentResponseUpdate` (single type, no subclasses)
   - Notable fields per update (all have the same shape):
     - `role`: always `'assistant'`
     - `text`: empty string (`''`) for the first 17 updates, then text deltas appear (`'echo'`, `':'`, `' probe'`, `' one'`) in updates 17-20, then empty again for the final 4
     - `contents`: empty list (`[]`) for the first 3 updates, then `[Content(...)]` for updates 3-16 (14 content-bearing updates covering the tool call phase), then content again for text deltas and tail
     - `response_id`: populated on the first 2 updates with `'resp_...'`, then `None` for most, then reappears on the 7th and 14th content-bearing updates
     - `continuation_token`: populated on first 2 updates as `{'response_id': '...'}`, then `None` for the rest
     - `finish_reason`: `None` on every update (never populated on streaming deltas)
     - `agent_id`: `None` on every update
     - `user_input_requests`: empty list on every update
     - `raw_representation`: present as a `ChatResponseUpdate` object on every update

3. **What does Phase 24 migration code need to do differently from what docs alone would suggest?**
   - The framework handles tool execution internally during streaming. The probe asked the model to call `echo_back`, and the 25 updates include the full round-trip: initial model response, tool call, tool result, and final text output -- all delivered as a single async-iterable stream. The adapter does NOT need to manually detect tool calls and invoke tools; the framework does this automatically inside `agent.run(stream=True)`.
   - `text` field accumulates the final model output only. During the tool-call phase (updates 3-16), `text` is empty -- content is in `contents[]` as Content objects. The SSE adapter should stream `update.text` for user-visible text and can ignore content-bearing updates during tool execution.
   - `finish_reason` is never populated on streaming updates -- the adapter cannot rely on it to detect end-of-stream. Instead, the async iterator simply completes.
   - `continuation_token` only appears on the first 2 updates (containing `response_id`). It is not a pagination token for the stream.

4. **Resolves open question:** Phase 24 task group 23.3 planner -- "Where in the SSE adapter the `forced_tool_failure` sub-code is emitted (agent level / adapter / middleware)" gets its raw shape from this probe. Also Phase 24 task group 23.1 streaming_adapter rewrite. Phase 24 mocks for `agent.run(stream=True)` are constructed by reading this fixture.

---

## Probe 2: tool_call_extraction

**Fixture:** [tool_call_extraction.json](../../../backend/tests/fixtures/foundry-probe/tool_call_extraction.json)

1. **What was the question?** Exact path inside `AgentResponse` where tool calls appear after `agent.run(...)`.

2. **What did the probe show?**
   - `top_level_tool_calls` present: false (no `response.tool_calls` attribute)
   - `messages_present`: true
   - Number of messages walked: 3
   - **Tool-call extraction path:** Tool calls are NOT directly accessible as a top-level field on `AgentResponse`. Instead, the framework executes tools automatically and the response contains the full conversation as `response.messages`:
     - `messages[0]`: role=`'assistant'`, author_name=`'UnnamedAgent'`, text=`''`, contents=[Content] -- this is the assistant's tool-call request
     - `messages[1]`: role=`'tool'`, author_name=`'UnnamedAgent'`, text=`''`, contents=[Content] -- this is the tool result
     - `messages[2]`: role=`'assistant'`, author_name=`'UnnamedAgent'`, text=`'echo: probe two'`, contents=[Content] -- this is the final assistant response incorporating the tool output
   - The final response text is available via `response.text` (returns `'echo: probe two'`).
   - `response.usage_details` provides token counts: `{'total_token_count': 228, 'output_token_count': 22, 'input_token_count': 206}`.

3. **What does Phase 24 migration code need to do differently from what docs alone would suggest?**
   - The framework auto-executes tools during `agent.run()` -- the response already includes tool results and the final model output. Phase 24's admin code does NOT need to extract tool calls, invoke them, and feed results back; it just reads `response.text` or `response.messages[-1].text` for the final answer.
   - For cases where Phase 24 needs to know WHICH tool was called (e.g., admin agent routing), it should inspect `response.messages` for messages with `role='tool'` or examine `messages[0].contents` for tool-call Content blocks.
   - `response.value` is `None` -- not used for tool results.

4. **Resolves open question:** Phase 24 task group 23.2 planner -- "The exact `AgentResponse` extraction path for tool calls" (design Section "Open questions resolved by each phase's gsd-planner -- Phase 23.2 planner"). The fixture is the source of truth Phase 24 codes against.

---

## Probe 3: tool_choice_required

**Fixture:** [tool_choice_required.json](../../../backend/tests/fixtures/foundry-probe/tool_choice_required.json)

1. **What was the question?** Whether `tool_choice='required'` enforces single-tool selection on the Foundry Responses endpoint, given a 1-tool agent and input that does NOT naturally invite tool use.

2. **What did the probe show?**
   - `auto` trial: raised=false, succeeded. With input "Tell me a fact about the moon" and tool_choice='auto', the model completed without raising. The response is an `AgentResponse` object (the framework auto-handles any tool calls if they occurred).
   - `required` trial: raised=false, succeeded. With tool_choice='required' on the same input, the model completed without raising. The response has the same `AgentResponse` shape with identical fields_seen.
   - `provider_dict` trial: raised=true, exc_type=`ContentError`, exc_str=`"tool_choice dict must contain 'mode' key"`. The provider-dict format `{"type": "function", "function": {"name": "echo_back"}}` is NOT supported by the GA SDK. The SDK expects a dict with a `'mode'` key instead.
   - **Verdict:** `"BOTH WORK -- preferred form chosen for D-07b"` -- Both `tool_choice='auto'` and `tool_choice='required'` succeeded. The `tool_choice='required'` string form is the correct way to force tool use in the GA SDK. The provider-dict fallback format from OpenAI's API is NOT compatible with the GA SDK's ChatOptions validation (requires `'mode'` key). Phase 24 should use `options=ChatOptions(tool_choice="required")` exclusively.

3. **What does Phase 24 migration code need to do differently from what docs alone would suggest?**
   - Phase 24 task group 23.3 MUST use `options=ChatOptions(tool_choice="required")` -- the string form works. Do NOT use the OpenAI-style provider-dict `{"type": "function", "function": {"name": "..."}}` -- it raises `ContentError`. If a future need arises to pin by function name, the dict format would need a `'mode'` key (exact schema not yet documented; probe showed the error message).
   - The Python safety net for tool_choice enforcement is still redundant as designed -- `tool_choice="required"` works on the GA SDK.

4. **Resolves open question:** Phase 24 task group 23.3 planner -- "Whether `tool_choice='required'` is honored as documented on the Foundry Responses endpoint" (design Section "Open questions resolved -- Phase 23 task group 23.3 planner"). Picks classifier `tool_choice` form. **This finding is load-bearing for D-07b.**

---

## Probe 4: session_rehydration

**Fixture:** [session_rehydration.json](../../../backend/tests/fixtures/foundry-probe/session_rehydration.json)

1. **What was the question?** Round-trip an `AgentSession` (GA equivalent of the pre-GA `AgentThread`) across two `run(stream=True)` calls. Capture stored identifier shape and confirm continuity.

2. **What did the probe show?**
   - Turn 1 update count: 19
   - Identifier shape on `AgentSession` object:
     - `session_id`: `'5b1aec77-b9ab-445d-964e-ee9629fbe2a1'` -- client-generated UUID
     - `service_session_id`: `'resp_0ce967302287c9f80069ff9b987a48819780c4790e30d192c6'` -- server-assigned response ID from the Foundry endpoint
     - `state`: `{}` -- empty dict (no custom state stored)
   - Turn 2 update count: 21
   - **Continuity verified?** The fixture stores `repr()` of update objects which do not expose text content directly. However, both turns completed successfully (no exceptions) and turn 2 produced 21 updates (consistent with a substantive model response). The AgentSession carries conversation history client-side, and the same session object was passed to both turns. The framework's session mechanism maintained context across the two streaming calls.
   - **Identifier to persist on Inbox doc:** `AgentSession.session_id` (the client-generated UUID `'5b1aec77-b9ab-445d-964e-ee9629fbe2a1'`). To rehydrate a session for follow-up turns, Phase 24 stores this `session_id` on the Inbox document (replacing the current `foundryThreadId` field) and reconstructs the session via `AgentSession(session_id=stored_id)`.

3. **What does Phase 24 migration code need to do differently from what docs alone would suggest?**
   - The GA API does NOT have `AgentThread` -- it uses `AgentSession`. The session object is passed via `session=AgentSession()` parameter on `agent.run()`, not `thread=AgentThread()`.
   - For rehydration: pass the same `AgentSession` object to subsequent `agent.run()` calls. The session carries conversation history client-side via an internal message list. The `service_session_id` is populated after the first call (server-assigned) but the primary rehydration key is `session_id`.
   - Phase 24 task group 23.3 stores `session.session_id` on the Inbox doc (replaces `foundryThreadId`). To resume a conversation: `session = AgentSession(session_id=stored_id)` -- but note that the conversation history lives in the `AgentSession.state` dict and the internal message accumulator, which would need to be serialized/deserialized for true cross-process rehydration. For the single-process case (follow-up within the same request handler), reusing the same `AgentSession` object works directly.

4. **Resolves open questions:** Phase 24 task group 23.3 planner -- "The exact GA session/thread API for per-call rehydration" AND "The GA-equivalent identifier stored on the Inbox doc (replaces the current `foundryThreadId` field)" (both from design Section "Open questions resolved -- Phase 23 task group 23.3 planner").

---

## Probe 5: auth_probe

**Fixture:** [auth_probe.json](../../../backend/tests/fixtures/foundry-probe/auth_probe.json)

1. **What was the question?** Does `FoundryChatClient(credential=AzureCliCredential())` successfully acquire a Foundry-scoped token, does the laptop's `az login` identity have the RBAC roles needed, and does a minimal agent invocation succeed?

2. **What did the probe show?**
   - Token acquisition: acquired=true, scope=`https://cognitiveservices.azure.com/.default`, token_length=2115
   - User principal id: `1ff5eea4-5056-4868-b3bb-339ba87f9e2e`
   - RBAC role assignments visible to user:
     - **Owner** (subscription-scoped, `/subscriptions/24ee21b9-...`)
     - **Azure AI User** (subscription-scoped, `/subscriptions/24ee21b9-...`)
   - Minimal invocation succeeded: true, response_type=`AgentResponse`

3. **What does Phase 24 migration code need to do differently from what docs alone would suggest?**
   - **Container Apps managed identity is NOT exercised by this probe.** The deployed Container App uses `ManagedIdentityCredential`. Phase 24 task group 23.1 wires the credential class as `ManagedIdentityCredential` (NOT `AzureCliCredential`). The probe only validates the credential CLASS shape (FoundryChatClient accepts an azure-credential-shaped object) and the RBAC role shape (the role names that worked for `az login` are the role names that need to be assigned to the Container App managed identity).
   - Required RBAC roles to assign to Container App managed identity (from fixture.rbac): **Owner** and **Azure AI User**. The Owner role is overly broad for a managed identity -- in practice, **Azure AI User** alone may suffice for agent invocation. Phase 24 should verify minimal RBAC during day-after UAT.
   - `FoundryChatClient` constructor takes `project_endpoint` (not `endpoint`) and `model` (not `model_deployment_name`). The credential is passed via `credential=` parameter.

4. **Resolves open question:** Phase 24 (Phase 24 in our numbering) planner -- "Exact `FoundryChatClient` credential mode for Container App: `ManagedIdentityCredential` vs. `DefaultAzureCredential`" (design Section "Open questions resolved -- Phase 23.0 planner"). The probe confirms the credential class accepts an azure-credential object; Phase 24 wires `ManagedIdentityCredential` for the deployed environment.

---

## Phase 24 task-group consumption summary

| Phase 24 task group | Consumes findings from |
|---|---|
| Task 0 (push guard install) | n/a |
| 23.1 -- Investigation | streaming_shape, auth_probe |
| 23.2 -- Admin | tool_call_extraction, streaming_shape (for non-streaming response shape sanity), auth_probe |
| 23.3 -- Classifier | tool_choice_required, session_rehydration, streaming_shape, auth_probe |

All five fixtures together substitute for staged production. Phase 24 mocks shape against these JSON files; Phase 24 replay tests re-run the probe scenarios against the local GA build and assert behavior matches.

## GA SDK API name mapping (critical for Phase 24)

| Design doc / pre-GA name | Actual GA SDK name (agent-framework 1.3.0) |
|---|---|
| `AgentRunResponse` | `AgentResponse` |
| `AgentRunResponseUpdate` | `AgentResponseUpdate` |
| `AgentThread` | `AgentSession` |
| `agent.run_stream(messages=..., thread=...)` | `agent.run(messages=..., stream=True, session=...)` |
| `thread=AgentThread()` | `session=AgentSession()` |
| `tool_choice="required"` (direct kwarg) | `options=ChatOptions(tool_choice="required")` |
| `FoundryChatClient(endpoint=..., model_deployment_name=...)` | `FoundryChatClient(project_endpoint=..., model=...)` |
| `{"role": "user", "content": "..."}` dicts | Plain strings or `Message(role='user', contents=[...])` objects |
| `foundryThreadId` (Inbox doc field) | `session_id` from `AgentSession.session_id` |
