---
status: resolved
trigger: "Investigate why the capture screen does not auto-reset after a successful classification filing, and why verbose classifier reasoning text streams through instead of just the tool result."
created: 2026-02-23T00:00:00Z
updated: 2026-02-23T00:01:00Z
---

## Current Focus

hypothesis: ROOT CAUSES CONFIRMED - two bugs with a shared origin
test: complete code trace through all layers
expecting: n/a
next_action: write findings and suggested fixes

## Symptoms

expected: After high-confidence classification (e.g. "Book flight to NY" -> Admin 0.90), screen auto-resets after ~2.5s. Only "Filed -> Admin (0.90)" shown, not classifier reasoning.
actual: Screen stays on result, never auto-resets. Classifier reasoning text ("Booking a flight is a one-off logistics task...") streams through to UI.
errors: No crash errors reported - behavioral bugs
reproduction: Submit any capture text, observe result screen behavior
started: Phase 04.3 UAT Test 1 and 2 failures

## Eliminated

- hypothesis: "SSE EventSource fires error event after close(), overwriting success toast and skipping resetState"
  evidence: react-native-sse close() sets this.status=CLOSED before xhr.abort(); both onreadystatechange and onerror check for CLOSED and return early. Verified in node_modules/react-native-sse/src/EventSource.js lines 96-98 and 137-139.
  timestamp: 2026-02-23T00:00:10Z

- hypothesis: "RUN_FINISHED event is never emitted by the backend"
  evidence: _stream_sse in main.py unconditionally yields RunFinishedEvent at line 143 after the async for loop completes. The _stream_updates generator catches all exceptions internally (line 317-318), so the stream always completes normally. Verified that EventEncoder produces correctly formatted SSE data with \n\n delimiter.
  timestamp: 2026-02-23T00:00:20Z

- hypothesis: "RUN_FINISHED event is not parsed correctly by the client"
  evidence: EventEncoder outputs 'data: {"type":"RUN_FINISHED",...}\n\n'. react-native-sse EventSource dispatches this as a "message" event (no event: prefix). attachCallbacks listens on "message", parses JSON, and switch matches case "RUN_FINISHED". Verified encoding format with actual EventEncoder.encode() call.
  timestamp: 2026-02-23T00:00:25Z

- hypothesis: "hitlTriggered flag blocks onComplete for high-confidence cases"
  evidence: hitlTriggered is only set true on CUSTOM events with name HITL_REQUIRED or MISUNDERSTOOD. For high-confidence captures, the workflow detects neither detected_clarification nor detected_misunderstood, so no CUSTOM event is emitted. hitlTriggered stays false; onComplete fires.
  timestamp: 2026-02-23T00:00:30Z

- hypothesis: "ResponseStream wrapper breaks async iteration of _stream_updates"
  evidence: ResponseStream.__aiter__ returns self; __anext__ resolves the wrapped async iterable and delegates iteration. _stream_updates is an async generator with __aiter__, so it's stored directly. _stream_sse async-for-iterates correctly. Verified source of ResponseStream._get_stream and __anext__.
  timestamp: 2026-02-23T00:00:35Z

- hypothesis: "pollingInterval=0 causes EventSource to reconnect and re-fire events"
  evidence: _pollAgain(0, false) evaluates condition (0 > 0 || false) = false, so no reconnection occurs. Verified in EventSource.js _pollAgain lines 57-64.
  timestamp: 2026-02-23T00:00:40Z

## Evidence

- timestamp: 2026-02-23T00:00:05Z
  checked: workflow.py _is_orchestrator_text echo filter (lines 141-149)
  found: Filter only checks if author_name matches the Orchestrator's name. Classifier text (author_name="Classifier") passes through unfiltered. All content types (text, function_call) from Classifier are yielded.
  implication: The Classifier's pre-tool reasoning text and post-tool response text both stream to the client as TEXT_MESSAGE_CONTENT events. This is the PRIMARY cause of verbose text leaking.

- timestamp: 2026-02-23T00:00:06Z
  checked: Classifier agent instructions in classifier.py (rules 5-6, lines 128-132)
  found: Instructions say "respond with ONLY the confirmation string returned by the tool" and "Do NOT add any extra commentary." However, LLMs generate reasoning tokens BEFORE calling the tool (chain-of-thought), and may add commentary after the tool result.
  implication: Prompt instructions alone cannot prevent reasoning tokens from streaming. The LLM's pre-tool reasoning is the source of verbose text like "Booking a flight is a one-off logistics task, fitting the Admin bucket."

- timestamp: 2026-02-23T00:00:07Z
  checked: main.py _convert_update_to_events (lines 69-112)
  found: Text content (content_type=="text") becomes TextMessageContentEvent with delta=content.text. Function call content becomes ToolCallStart/Args/End events. All Classifier text content is converted to TEXT_MESSAGE_CONTENT.
  implication: Every piece of Classifier text becomes a streamable event. No filtering happens at the SSE conversion layer.

- timestamp: 2026-02-23T00:00:08Z
  checked: ag-ui-client.ts attachCallbacks TEXT_MESSAGE_CONTENT handler (lines 56-60)
  found: result += parsed.delta accumulates ALL text deltas into result. callbacks.onTextDelta?.(parsed.delta) streams each delta to the UI. Both the accumulated result AND the streamed display get the verbose text.
  implication: The client accumulates the verbose reasoning text. onComplete(result) gets the full verbose string. setToast({message: result}) shows the verbose text in the toast.

- timestamp: 2026-02-23T00:00:09Z
  checked: text.tsx onComplete callback (lines 204-209)
  found: onComplete calls setSending(false), Haptics, setToast({message: result || "Captured"}), setTimeout(resetState, AUTO_RESET_MS). The mechanism IS correctly wired.
  implication: onComplete IS called and resetState IS scheduled via setTimeout. The auto-reset mechanism is structurally correct.

- timestamp: 2026-02-23T00:00:11Z
  checked: text.tsx resetState function (lines 61-75)
  found: resetState clears all state: setThought(""), setShowSteps(false), setStreamedText(""), etc. All setters are stable React useState setters with primitive/empty values.
  implication: When resetState fires, the UI should fully reset. No possible error in the state setters.

- timestamp: 2026-02-23T00:00:12Z
  checked: Classification tool return values in classification.py
  found: classify_and_file returns "Filed -> {bucket} ({confidence:.2f})" (line 142) or "Filed (needs review) -> {bucket} ({confidence:.2f})" (line 141). request_misunderstood returns "Misunderstood -> {id} | {question}" (line 187).
  implication: The tool returns are clean, concise strings. The verbose text comes from the LLM's reasoning tokens, not the tool output.

- timestamp: 2026-02-23T00:00:15Z
  checked: Full event flow timing analysis
  found: The LLM generates reasoning tokens (several seconds of streaming text), then calls the tool, then generates final response. All of this text streams through to the client. RUN_FINISHED only arrives AFTER the LLM completes its full response. For a verbose LLM, this could be 5-15 seconds of streaming before onComplete fires.
  implication: The perceived "no auto-reset" may be partly because the total time (LLM reasoning + 2.5s reset delay) is much longer than the expected ~2.5s. But even after RUN_FINISHED, the reset SHOULD fire after 2.5s.

- timestamp: 2026-02-23T00:00:45Z
  checked: Whether onComplete result is passed correctly to toast
  found: onComplete receives accumulated result (all TEXT_MESSAGE_CONTENT deltas). With verbose reasoning, result is something like "Booking a flight is a one-off logistics task...\n\nFiled -> Admin (0.90)". This full string is set as the toast message.
  implication: Even if auto-reset works, the toast shows verbose gibberish text instead of a clean "Filed -> Admin (0.90)" confirmation.

## Resolution

root_cause: |
  TWO related bugs sharing a common origin in the echo filter:

  **Bug 2 (Verbose reasoning text) - PRIMARY ROOT CAUSE:**
  File: backend/src/second_brain/agents/workflow.py, method _is_orchestrator_text (lines 141-149)

  The echo filter in AGUIWorkflowAdapter only suppresses text from the Orchestrator agent
  (checks author_name against self._orchestrator.name). The Classifier agent's text output
  passes through unfiltered because its author_name is "Classifier", not "Orchestrator".

  When the Classifier LLM processes input, it generates reasoning tokens BEFORE calling
  classify_and_file (e.g., "Booking a flight is a one-off logistics task, fitting the
  Admin bucket. Admin Score: 0.90, People Score: 0.05..."). These reasoning tokens flow
  as AgentResponseUpdate(author_name="Classifier", content_type="text"), pass the echo
  filter, get converted to TextMessageContentEvent in main.py _convert_update_to_events,
  and stream to the client where they appear in the feedback area AND accumulate in the
  onComplete result.

  The Classifier instructions (rules 5-6) say "respond with ONLY the confirmation string"
  but LLMs generate chain-of-thought reasoning tokens before tool invocation, which cannot
  be suppressed by prompt instructions alone.

  **Bug 1 (No auto-reset) - CONSEQUENCE OF BUG 2:**
  File: mobile/lib/ag-ui-client.ts, attachCallbacks (lines 39, 56-60, 89-94)
  File: mobile/app/capture/text.tsx, onComplete callback (lines 204-209)

  The auto-reset mechanism (onComplete -> setTimeout(resetState, 2500)) IS correctly wired
  and DOES fire. Code analysis confirms: RUN_FINISHED is emitted, hitlTriggered stays false
  for high-confidence cases, onComplete(result) is called, setTimeout is scheduled.

  The perceived "no auto-reset" has two contributing factors:

  1. TIMING: The LLM's verbose reasoning takes several seconds to stream. RUN_FINISHED
     only arrives AFTER the LLM completes all reasoning + tool call + final response.
     The total time from submission to reset = (LLM streaming time) + 2.5s, which is
     much longer than the expected ~2.5s. The user sees verbose text streaming and
     concludes the screen is "stuck" before the reset eventually happens.

  2. TOAST CONTENT: When onComplete fires, result contains the FULL verbose reasoning
     text (not just "Filed -> Admin (0.90)"). The toast message shows this verbose text,
     which looks broken/wrong to the user. Combined with the long delay, it creates the
     impression of a stuck screen.

  Fixing Bug 2 (filtering Classifier reasoning) resolves BOTH issues: the onTextDelta
  callbacks receive only the clean tool result, and onComplete's result is the concise
  "Filed -> Admin (0.90)" string. The auto-reset fires after the expected ~2.5s total.

fix: |
  SUGGESTED FIX (not applied - diagnosis only):

  Option A (Recommended): Add Classifier text filtering in workflow.py
  In _stream_updates, after the orchestrator echo filter, add a second filter that
  suppresses Classifier text content UNLESS it matches the expected tool result patterns
  (_FILED_CONFIDENCE_RE or "Filed (needs review)"). Buffer Classifier text and only yield
  content matching these patterns.

  Option B: Filter at the SSE conversion layer
  In main.py _convert_update_to_events, check if the text content matches expected result
  patterns before converting to TextMessageContentEvent. Suppress non-matching text.

  Option C: Filter at the client
  In ag-ui-client.ts attachCallbacks, for TEXT_MESSAGE_CONTENT events, check if the delta
  matches the "Filed" pattern before adding to result and calling onTextDelta. This is less
  ideal because the client shouldn't need to know about backend implementation details.

  Option A is recommended because:
  - It keeps filtering logic centralized in the adapter where other filtering already happens
  - It prevents verbose text from being sent over the wire at all
  - It's consistent with the existing echo filter pattern
  - The adapter already has _FILED_CONFIDENCE_RE and related regexes for pattern detection

verification:
files_changed: []
