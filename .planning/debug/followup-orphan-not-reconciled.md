---
status: diagnosed
trigger: "After misunderstood follow-up reclassification, original inbox item not cleaned up — two items appear"
created: 2026-02-27T00:00:00Z
updated: 2026-02-28T00:00:00Z
symptoms_prefilled: true
goal: find_root_cause_only
---

## Current Focus

hypothesis: Primary root cause is that tool_result is never populated from the Foundry streaming SDK, causing inboxItemId to be empty. The fallback query-based reconciliation was added but the exception handling swallows failures silently.
test: Full code trace from adapter through reconciliation
expecting: Identify structural issues preventing reconciliation
next_action: Report diagnosis

## Symptoms

expected: After follow-up reclassification, original misunderstood doc updated, orphan deleted, one item remains
actual: Both original and new doc appear in inbox under same bucket — two items instead of one
errors: App Insights showed "1 failed" item in follow-up trace
reproduction: Trigger misunderstood follow-up (text or voice), observe inbox has two items
started: Current behavior, confirmed in UAT at 2026-02-27T23:08

## Eliminated

- hypothesis: Reconciliation code not called
  evidence: Both text and voice follow-up endpoints wrap with _stream_with_reconciliation. Python generator protocol guarantees post-yield code executes.
  timestamp: 2026-02-28

- hypothesis: StreamingResponse cancels generator before reconciliation
  evidence: Starlette spec >= 2.4 does not cancel generators on client disconnect. Reconciliation runs between last yield and generator return.
  timestamp: 2026-02-28

- hypothesis: CLASSIFIED event not emitted
  evidence: _emit_result_event correctly maps status="classified" to classified_event(). Event parsing in wrapper correctly detects CLASSIFIED type.
  timestamp: 2026-02-28

- hypothesis: Cosmos upsert uses etag-based concurrency and fails
  evidence: Default upsert_item does NOT enforce etag checks (last-write-wins).
  timestamp: 2026-02-28

## Evidence

- timestamp: 2026-02-28
  checked: Commit 0d1e1e3 message
  found: "When the Foundry streaming API doesn't return a function_result content block, tool_result stays None and the CLASSIFIED SSE event has an empty inboxItemId."
  implication: This is a KNOWN issue. tool_result is never populated during streaming.

- timestamp: 2026-02-28
  checked: FunctionInvocationLayer in agent_framework SDK (_tools.py lines 2296-2300)
  found: The SDK DOES yield ChatResponseUpdate with function_result content after executing tools. However, the commit message confirms this content is NOT received by the adapter in practice.
  implication: The SDK yields it but the Foundry Agent Service (Azure AI Foundry) may not stream function_result back through the API in the same way.

- timestamp: 2026-02-28
  checked: _emit_result_event fallback when tool_result is None
  found: result_src = detected_tool_args (function call arguments). detected_tool_args has text, bucket, confidence, status, title — but NOT item_id. So item_id defaults to "".
  implication: CLASSIFIED event always has inboxItemId="" when tool_result is not streamed.

- timestamp: 2026-02-28
  checked: _stream_with_reconciliation fallback query
  found: When new_item_id is "" (falsy), falls to query: SELECT * FROM c WHERE c.userId = 'will' AND c.id != @originalId ORDER BY c.createdAt DESC OFFSET 0 LIMIT 1
  implication: Query finds most recent non-original inbox doc. Should work but is fragile.

- timestamp: 2026-02-28
  checked: UAT results at 2026-02-27T23:08
  found: Tests 3 and 4 both failed with orphan reconciliation issue. This is AFTER the fallback query fix was committed (18:40) and deployed.
  implication: The fallback query fix does NOT resolve the issue. The reconciliation is still failing.

- timestamp: 2026-02-28
  checked: Exception handling in reconciliation
  found: Broad except Exception handler at line 230 catches ALL errors and logs a warning with exc_info=True. The "1 failed" in App Insights is likely this warning.
  implication: Some Cosmos DB operation in the reconciliation is throwing an exception that's being swallowed.

- timestamp: 2026-02-28
  checked: Mobile ag-ui-client.ts MISUNDERSTOOD handling
  found: Line 79: if (parsed.value?.inboxItemId) — empty string is falsy in JS. When inboxItemId is "", onMisunderstood is never called.
  implication: Follow-up flow can only trigger when the INITIAL capture uses the safety-net path (which generates a real UUID for inboxItemId).

## Resolution

root_cause: |
  Two interacting bugs prevent orphan reconciliation:

  1. **Primary: tool_result never populated from Foundry streaming API.** The agent-framework SDK's FunctionInvocationLayer does yield function_result Content objects after tool execution, but the Azure AI Foundry Agent Service streaming does not propagate these back through the adapter's stream iteration in the way the code expects. This means tool_result stays None, and all SSE events (CLASSIFIED, MISUNDERSTOOD, LOW_CONFIDENCE) have inboxItemId="" because item_id comes from tool_result, not the function call arguments.

  2. **Secondary: The fallback query-based reconciliation fails silently.** The exception is caught by the broad except Exception handler and logged as a warning. Without App Insights access, the exact exception is unknown, but likely candidates are:
     - The query returns an unexpected document (not the orphan)
     - A Cosmos DB operation fails during the reconciliation steps

  3. **Structural fragility:** The entire reconciliation approach of running cleanup code AFTER yielding SSE events to the client is architecturally fragile:
     - It depends on post-yield generator code executing reliably
     - The fallback query approach (find most recent non-original doc) is inherently race-condition prone
     - Any exception in the reconciliation is swallowed, leaving orphan docs silently
     - The reconciliation has no retry mechanism

  **The correct fix** should avoid the fragile post-hoc reconciliation entirely. Instead, the follow-up flow should be redesigned so that file_capture during a follow-up does NOT create a new inbox doc at all. The original inbox item ID should be passed to the file_capture tool (or handled in the tool's logic) so it UPDATES the existing misunderstood doc in-place rather than creating an orphan that needs reconciliation.

fix: N/A (diagnosis only)
verification: N/A
files_changed: []
