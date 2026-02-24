---
status: diagnosed
trigger: "Investigate why the MISUNDERSTOOD event is not triggering conversation mode on the capture screen"
created: 2026-02-23T00:00:00Z
updated: 2026-02-23T00:00:00Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: CONFIRMED - Backend emits HITL_REQUIRED instead of MISUNDERSTOOD because the misunderstood regex never matches streamed text
test: Full end-to-end trace of event flow from tool call to UI rendering
expecting: N/A - root cause found
next_action: Return diagnosis

## Symptoms

expected: When typing "Aardvark", classifier asks clarifying question AND UI enters conversation mode (agent question bubble, cleared input, Reply button, follow-up hint)
actual: Classifier asks correct question but UI shows old HITL bucket buttons (People, Projects, Ideas, Admin) instead of conversation mode
errors: None reported - silent UI misbehavior
reproduction: Type "Aardvark" on capture screen, observe UI after classification
started: Phase 04.3 UAT Test 3

## Eliminated

- hypothesis: Client-side ag-ui-client.ts doesn't route MISUNDERSTOOD events to onMisunderstood callback
  evidence: Code at lines 76-83 correctly checks parsed.name === "MISUNDERSTOOD" && parsed.value?.inboxItemId and calls callbacks.onMisunderstood. The logic is correct.
  timestamp: 2026-02-23

- hypothesis: onMisunderstood callback not wired up in sendCapture
  evidence: text.tsx lines 174-182 correctly define onMisunderstood in sendCapture callbacks, setting agentQuestion, misunderstoodInboxItemId, followUpRound=1, clearing thought, etc.
  timestamp: 2026-02-23

- hypothesis: Conversation mode UI not rendering based on agentQuestion/followUpRound state
  evidence: text.tsx lines 304-311 correctly render agentQuestionBubble when agentQuestion is not null, and line 297 correctly shows "Reply" when followUpRound > 0. The UI code is correct.
  timestamp: 2026-02-23

- hypothesis: CustomEvent serialization is wrong (field names, format)
  evidence: Tested EventEncoder output directly. CustomEvent(name="MISUNDERSTOOD", value={...}) serializes to {"type":"CUSTOM","name":"MISUNDERSTOOD","value":{"threadId":"...","inboxItemId":"...","questionText":"..."}}. The by_alias=True + to_camel alias_generator produces correct camelCase field names. Matches what ag-ui-client.ts expects.
  timestamp: 2026-02-23

- hypothesis: The _MISUNDERSTOOD_RE regex pattern is wrong
  evidence: Regex r"Misunderstood\s*→\s*([a-f0-9\-]+)\s*\|\s*(.+)" correctly matches the tool output format "Misunderstood → {uuid} | {question}" when tested with real UUIDs.
  timestamp: 2026-02-23

## Evidence

- timestamp: 2026-02-23
  checked: Backend workflow.py _stream_updates method (lines 324-362) - how custom events are emitted after stream completes
  found: Three branches in priority order: (1) if detected_misunderstood is not None -> emit MISUNDERSTOOD, (2) elif detected_clarification is not None -> emit HITL_REQUIRED, (3) elif saw_request_info -> emit generic HITL_REQUIRED with only threadId
  implication: If detected_misunderstood stays None and saw_request_info is True, the third branch fires, emitting HITL_REQUIRED instead of MISUNDERSTOOD

- timestamp: 2026-02-23
  checked: How detected_misunderstood is populated (workflow.py lines 248-252, 299-303)
  found: The regex _MISUNDERSTOOD_RE is checked against update.text for each AgentResponseUpdate in the stream. update.text only returns text from Content objects with type=="text" (not function_call or function_result)
  implication: The regex can only match if the LLM's text response contains the full "Misunderstood → {uuid} | {question}" format

- timestamp: 2026-02-23
  checked: request_misunderstood tool return format (classification.py line 187)
  found: Tool returns f"Misunderstood → {inbox_doc_id} | {question_text}" -- this is the string that goes back to the LLM as a tool result
  implication: The tool output has the correct format, but it's sent back to the LLM as a tool message, NOT directly yielded as a stream output

- timestamp: 2026-02-23
  checked: AgentExecutor._run_agent_streaming (agent_framework internals)
  found: ctx.yield_output(update) is called for each AgentResponseUpdate the agent generates. Tool call content (function_call) and the LLM's final text response are yielded. Tool RESULTS (function_result messages) are internal to the agent run loop and NOT yielded as outputs.
  implication: The "Misunderstood → {uuid} | {question}" text from the tool result never appears in update.text. Only the LLM's final text response appears.

- timestamp: 2026-02-23
  checked: Classifier instructions (classifier.py) - what the LLM is told to do after calling request_misunderstood
  found: Rule 5 says "respond with ONLY the confirmation string returned by the tool" but this is in the context of "After filing" (classify_and_file). No explicit instruction tells the LLM to echo the exact request_misunderstood output. The LLM naturally outputs just the question text (e.g., "I'm not quite sure what you meant by 'Aardvark'. Could you tell me more?") without the "Misunderstood → {uuid} | " prefix.
  implication: The LLM's text response does not match the regex pattern, so detected_misunderstood stays None

- timestamp: 2026-02-23
  checked: HandoffAgentExecutor behavior for non-autonomous agents (lines 240-243)
  found: When the Classifier (non-autonomous) finishes its turn without triggering a handoff, the executor calls ctx.request_info(HandoffAgentUserRequest(response)), which emits a request_info WorkflowEvent. This sets saw_request_info = True in _stream_updates.
  implication: saw_request_info is always True when the Classifier completes, regardless of which tool it called

- timestamp: 2026-02-23
  checked: Client-side fallback behavior when HITL_REQUIRED has no questionText (ag-ui-client.ts line 68)
  found: const questionText = parsed.value.questionText || result -- falls back to accumulated TEXT_MESSAGE_CONTENT deltas. So the question text IS shown, but via HITL UI (bucket buttons) not conversation mode UI.
  implication: This explains why the user sees the correct question text but with bucket buttons instead of conversation mode

## Resolution

root_cause: The backend's _stream_updates method in workflow.py relies on regex-matching the text "Misunderstood → {uuid} | {question}" in streamed AgentResponseUpdate.text to detect misunderstood items and emit the MISUNDERSTOOD custom event. However, the tool result text (which has this format) is never directly streamed -- it goes back to the LLM as an internal tool message. The LLM then generates its own text response, typically just the question text without the "Misunderstood → {uuid} | " prefix. Since the regex doesn't match, detected_misunderstood stays None. Meanwhile, the non-autonomous Classifier always triggers a request_info event when it finishes its turn, so saw_request_info becomes True. This causes the third branch to fire, emitting HITL_REQUIRED (with only threadId) instead of MISUNDERSTOOD. The client then renders HITL bucket buttons instead of entering conversation mode.

fix:
verification:
files_changed: []
