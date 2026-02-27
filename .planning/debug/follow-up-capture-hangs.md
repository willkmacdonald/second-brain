---
status: diagnosed
trigger: "Investigate why POST /api/capture/follow-up hangs during processing"
created: 2026-02-27T00:00:00Z
updated: 2026-02-27T00:00:00Z
---

## Current Focus

hypothesis: Follow-up hangs at the Foundry agent call level (60s asyncio.timeout eventually fires). Root cause is most likely the Foundry agent thread reuse call timing out or failing silently on the Azure Agents API side, combined with a possible race condition where foundryThreadId is never written to Cosmos.
test: Check App Insights logs for the follow-up request to see if the agent call completes, times out, or errors
expecting: Either a 60s timeout error or a 400 "No thread ID" error in the logs
next_action: Report findings

## Symptoms

expected: User submits follow-up text, backend re-classifies on the same Foundry thread, client receives CLASSIFIED or MISUNDERSTOOD SSE events
actual: "Processing" spinner hangs indefinitely, eventually times out. Item remains "Needs Clarification" in inbox.
errors: None visible to user (timeout, no explicit error)
reproduction: 1) Text capture of nonsense ("apple dog cat spaghetti") 2) Get misunderstood question 3) Type follow-up ("I have to build a deck for a customer") and hit send 4) Observe hang
started: After deployment (was 404 before, now endpoint exists but hangs)

## Eliminated

- hypothesis: Mobile client not calling correct endpoint
  evidence: Endpoint exists and is hit (no longer 404)
  timestamp: 2026-02-27

- hypothesis: Mobile client SSE parsing issue
  evidence: ag-ui-client.ts attachCallbacks handles all event types correctly, same code path as initial capture which works
  timestamp: 2026-02-27

- hypothesis: Missing or wrong SSE event types from backend
  evidence: stream_follow_up_capture emits same event sequence as stream_text_capture (STEP_START, result, COMPLETE) -- sse.py events match what client expects
  timestamp: 2026-02-27

## Evidence

- timestamp: 2026-02-27
  checked: Backend follow-up endpoint (capture.py:318-368)
  found: Endpoint reads Cosmos for foundryThreadId, validates it exists, calls stream_follow_up_capture
  implication: If foundryThreadId is missing, returns 400 (not a hang). Hang must be in the streaming phase.

- timestamp: 2026-02-27
  checked: stream_follow_up_capture (adapter.py:331-459) with asyncio.timeout(60)
  found: The entire Foundry agent call is wrapped in asyncio.timeout(60). If the agent call hangs, after 60s it yields ERROR + COMPLETE events.
  implication: Maximum hang is 60 seconds before client gets an error. "Eventually times out" matches this 60s window.

- timestamp: 2026-02-27
  checked: FunctionInvocationLayer.get_response streaming path (_tools.py:2224-2362)
  found: FIL handles tool execution loop for file_capture. Calls _inner_get_response, iterates stream, executes tools, loops back. For conversation-based APIs, it updates conversation_id and clears messages.
  implication: The FIL properly handles the tool execution loop and thread reuse. Not likely the source of the hang.

- timestamp: 2026-02-27
  checked: AzureAIAgentClient._create_agent_stream (_chat_client.py:645-695) and _prepare_thread (_chat_client.py:712-729)
  found: On follow-up, conversation_id in options -> thread_id in run_options -> _create_agent_stream. Checks for active runs, cancels if needed, creates new run on existing thread.
  implication: Thread reuse mechanism is correct. If previous run completed, new run should start cleanly.

- timestamp: 2026-02-27
  checked: _stream_with_thread_id_persistence (capture.py:54-99) - Cosmos write timing
  found: foundryThreadId is written to Cosmos AFTER the entire SSE stream completes (post-loop code). The MISUNDERSTOOD event is yielded to client BEFORE the Cosmos write happens.
  implication: CRITICAL RACE CONDITION -- if ASGI cancels the generator after yielding COMPLETE (client disconnects), the Cosmos write at lines 82-99 may never execute. Follow-up would then fail with 400 "No thread ID" or read a stale/missing foundryThreadId.

- timestamp: 2026-02-27
  checked: react-native-sse EventSource (EventSource.js)
  found: No client-side timeout configured (timeout defaults to 0 = no timeout). pollingInterval=0 correctly prevents reconnection. Error handler dispatches to callbacks.
  implication: Client waits indefinitely for server response. The 60s timeout on the server side is the only protection.

- timestamp: 2026-02-27
  checked: Mobile follow-up callback handling (text.tsx:77-129, index.tsx:291-359)
  found: Both screens properly handle onError, onMisunderstood, onComplete, onUnresolved callbacks from sendFollowUp
  implication: If SSE events arrive, the client handles them. The hang is server-side.

## Resolution

root_cause: |
  Two layered issues causing the follow-up to fail/hang:

  **Primary (LIKELY): Foundry Agent API call on reused thread hangs or takes excessive time**
  The stream_follow_up_capture function calls the Azure AI Foundry Agents API to create a new run
  on an existing thread (reusing conversation_id). This agent call either:
  a) Takes longer than expected on thread reuse (Foundry service latency), OR
  b) Fails silently or returns an error that the framework doesn't surface as stream events

  The 60-second asyncio.timeout in the adapter (line 377) should eventually fire and send an ERROR
  event to the client, matching the "eventually times out" symptom.

  **Secondary (POSSIBLE race condition): foundryThreadId never written to Cosmos**
  The _stream_with_thread_id_persistence wrapper writes foundryThreadId to Cosmos ONLY AFTER
  the entire SSE generator completes (capture.py:81-99). If the ASGI server cancels the
  generator when the client disconnects after receiving COMPLETE, the Cosmos write never
  executes. In this case, the follow-up endpoint reads the inbox item, finds no foundryThreadId,
  and returns HTTP 400 -- which react-native-sse would dispatch as an error event, not a hang.

  However, this 400 error MIGHT appear as a hang in some scenarios if react-native-sse doesn't
  properly dispatch error events for non-200 responses from POST requests.

fix: Not applied (investigation only)
verification: Not performed (investigation only)
files_changed: []
