---
status: resolved
trigger: "Capture screen toast shows 0.00 confidence but inbox detail card shows correct value (e.g., 85%)"
created: 2026-02-24T00:00:00Z
updated: 2026-02-24T00:00:00Z
resolved_by: 04.3-09-PLAN.md
---

## Current Focus

hypothesis: CONFIRMED — clean_result in workflow.py is built from function_call.arguments (pre-fallback 0.00) not from the tool return string (post-fallback corrected value)
test: Traced full data flow from LLM function_call -> adapter -> SSE -> client toast
expecting: N/A — root cause confirmed
next_action: Return diagnosis

## Symptoms

expected: Capture screen toast should show the corrected confidence (e.g., 85%) matching what's stored in Cosmos DB
actual: Toast shows "0.00" confidence while inbox detail card correctly shows 85%
errors: No errors — just wrong value displayed
reproduction: Capture a thought where LLM returns all four score params as 0.0, triggering the score fallback logic in classify_and_file
started: After Plan 07 added score validation/fallback to classify_and_file

## Eliminated

## Evidence

- timestamp: 2026-02-24T00:01:00Z
  checked: workflow.py lines 229-231 (_extract_function_call_info)
  found: detected_tool_args is populated from function_call.arguments — the RAW LLM output before tool execution
  implication: confidence=0.0 as the LLM emitted it is captured here

- timestamp: 2026-02-24T00:02:00Z
  checked: classification.py lines 96-104 (confidence fallback) and lines 107-129 (score fallback)
  found: Tool corrects confidence 0.0 -> 0.75 and derives scores, but these corrections only exist in the tool's return string and the Cosmos DB write
  implication: The corrected values are never propagated back to the adapter's detected_tool_args

- timestamp: 2026-02-24T00:03:00Z
  checked: workflow.py lines 379-400 (clean_result construction)
  found: Line 384 reads `confidence = detected_tool_args.get("confidence", 0.0)` — this is the pre-fallback 0.0 value
  implication: The toast text "Filed (needs review) -> {bucket} (0.00)" uses the wrong confidence

- timestamp: 2026-02-24T00:04:00Z
  checked: workflow.py lines 425-435 (CLASSIFIED custom event)
  found: Line 433 also reads `detected_tool_args.get("confidence", 0.0)` — the CLASSIFIED event also carries the wrong confidence
  implication: Both the clean_result text AND the CLASSIFIED custom event have stale pre-fallback values

- timestamp: 2026-02-24T00:05:00Z
  checked: ag-ui-client.ts lines 39-93 (attachCallbacks)
  found: `result` accumulates TEXT_MESSAGE_CONTENT deltas (which come from the clean_result). On RUN_FINISHED, `callbacks.onComplete(result)` is called.
  implication: Toast message = accumulated text deltas = clean_result from workflow.py = the 0.00 value

- timestamp: 2026-02-24T00:06:00Z
  checked: text.tsx line 207 (onComplete handler)
  found: `setToast({ message: result || "Captured", type: "success" })` — directly displays the result string
  implication: The user sees "Filed (needs review) -> People (0.00)" in the toast

## Resolution

root_cause: The adapter (workflow.py) constructs the client-facing clean_result string and CLASSIFIED custom event from `detected_tool_args` — the LLM's raw function_call.arguments captured BEFORE tool execution. The score fallback logic in classify_and_file (classification.py) corrects confidence 0.0 -> 0.75 and derives all_scores, but these corrections only exist inside the tool function scope. They are written to Cosmos DB (so the inbox detail card is correct) but never propagated back to the adapter. The adapter has no access to the tool's return string when constructing the clean_result; it only sees the pre-fallback arguments.
fix:
verification:
files_changed: []
