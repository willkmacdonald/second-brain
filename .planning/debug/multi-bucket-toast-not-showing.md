---
status: resolved
trigger: "multi-split toast shows 'filed to admin' instead of 'Filed to Admin, People' when a multi-intent capture is split across buckets"
created: 2026-03-02T06:00:00Z
updated: 2026-03-02T06:30:00Z
---

## Current Focus

hypothesis: CONFIRMED -- see Resolution
test: n/a
expecting: n/a
next_action: none -- root cause identified, fix direction documented

## Symptoms

expected: Toast shows "Filed to Admin, People" multi-bucket format when a capture is split across two buckets
actual: Toast shows single-bucket format "Filed -> Admin (0.xx)" even though both Cosmos items (Admin + People) were created correctly
errors: No errors -- silent data loss in the adapter's streaming loop
reproduction: Send "need milk and also remind me to call the vet" via text capture
started: Phase 11.1 (first multi-split deployment)

## Eliminated

- hypothesis: "Backend classified_event function not being called with buckets/item_ids arrays"
  evidence: "Code at adapter.py:279-288 correctly calls classified_event with buckets=all_buckets when len(file_capture_results) > 1. The function signature and implementation in sse.py:33-55 are correct."
  timestamp: 2026-03-02T06:05:00Z

- hypothesis: "Mobile client not parsing buckets field correctly from SSE event"
  evidence: "Mobile ag-ui-client.ts:72-78 correctly checks parsed.value.buckets && buckets.length > 1 and formats as 'Filed to ${buckets.join(\", \")}'. TypeScript interface at line 30 declares buckets?: string[]. Parsing is correct."
  timestamp: 2026-03-02T06:05:00Z

- hypothesis: "classified_event SSE format not including buckets array in the JSON payload"
  evidence: "sse.py:51-54 conditionally includes buckets and itemIds when not None. Tests at test_streaming_adapter.py:86-102 verify multi-bucket format includes both fields. The event constructor is correct."
  timestamp: 2026-03-02T06:06:00Z

## Evidence

- timestamp: 2026-03-02T06:07:00Z
  checked: "UAT results -- test 2 (text multi-split) vs test 5 (voice multi-split)"
  found: "Text multi-split FAILED toast format but items were created. Voice multi-split PASSED. Both use near-identical adapter code."
  implication: "The issue is in the streaming observation loop, not the event emission or mobile parsing"

- timestamp: 2026-03-02T06:10:00Z
  checked: "agent_framework_azure_ai SDK _chat_client.py _process_stream() method"
  found: "THREAD_RUN_REQUIRES_ACTION event at line 904 yields ALL function_call Content objects in a SINGLE ChatResponseUpdate (line 909-920). _parse_function_calls_from_azure_ai returns a list of Content.from_function_call objects, one per tool.function in required_action.submit_tool_outputs.tool_calls."
  implication: "When the Classifier calls file_capture twice, BOTH function_call contents arrive in ONE update.contents list"

- timestamp: 2026-03-02T06:12:00Z
  checked: "agent_framework _tools.py FunctionInvocationLayer _stream() at line 2222"
  found: "After the inner stream yields updates (including the REQUIRES_ACTION update with function_calls), the FunctionInvocationLayer executes tools locally, then yields a SEPARATE update at line 2297-2300 containing all function_result contents."
  implication: "Function_results for ALL tool calls arrive in a SINGLE update, separate from the function_call update"

- timestamp: 2026-03-02T06:15:00Z
  checked: "adapter.py streaming loop content processing (lines 213-228)"
  found: |
    The adapter tracks one function at a time via `current_fc_name`. When processing
    Update 1 (two function_calls in update.contents):
      - content[0]: current_fc_name = "file_capture", current_fc_args = args_for_call_1
      - content[1]: current_fc_name = "file_capture", current_fc_args = args_for_call_2 (OVERWRITES call_1)

    When processing Update 2 (two function_results in update.contents):
      - content[0]: current_fc_name == "file_capture" -> True, merged+appended, current_fc_name = None
      - content[1]: current_fc_name == "file_capture" -> False (it's None!), SKIPPED, result DROPPED
  implication: "The second function_result is silently dropped because current_fc_name was reset to None after the first result. This is the root cause."

- timestamp: 2026-03-02T06:17:00Z
  checked: "Why file_capture_results only has 1 entry"
  found: "With 2 file_capture calls, only the first function_result is appended. file_capture_results has length 1. The check at adapter.py:279 (len > 1) is False. Single-bucket classified_event is emitted without buckets array."
  implication: "The mobile receives a CLASSIFIED event with no buckets field, falls through to single-bucket toast format"

- timestamp: 2026-03-02T06:19:00Z
  checked: "Why Cosmos DB has both items despite adapter only capturing one result"
  found: "The agent_framework SDK executes the tools BEFORE streaming the results back. ClassifierTools.file_capture writes to Cosmos during tool execution (line 2284-2293 of _tools.py). The function_result contents are the RETURN values streamed back for observation. The adapter is a passive observer -- tool execution happens independently."
  implication: "Cosmos writes always succeed because they happen during tool execution. The adapter's observation failure only affects the SSE event, not the data."

- timestamp: 2026-03-02T06:21:00Z
  checked: "Secondary bug: current_fc_args overwrite on multiple function_calls in same update"
  found: "When both function_call contents arrive in one update.contents, the second call's args overwrite the first's. The merged dict for the first result uses call_2's args (text='call the vet') merged with call_1's result (bucket='Admin'). The bucket/confidence/item_id from the result override the args, so those fields are correct. But the 'text' field in the merged dict would be wrong (call_2's text, not call_1's). This affects Admin Agent raw_text for that item."
  implication: "Even if the result-dropping bug is fixed, the args-overwrite bug would cause wrong text to be associated with the first result. Both bugs need fixing."

## Resolution

root_cause: |
  The adapter's `current_fc_name` single-variable tracking cannot handle multiple
  function_call/function_result pairs delivered in the same ChatResponseUpdate.

  The Azure AI Agent Service (via the agent_framework SDK) delivers ALL tool calls
  from a single agent run as a batch:
  - One update containing ALL function_call Content objects (from THREAD_RUN_REQUIRES_ACTION)
  - One update containing ALL function_result Content objects (from FunctionInvocationLayer)

  The adapter processes these sequentially in a `for content in update.contents` loop.
  After processing the first function_result, it resets `current_fc_name = None`.
  The second function_result then fails the `current_fc_name == "file_capture"` check
  and is silently dropped. Only one result is captured, so the single-bucket CLASSIFIED
  event is emitted instead of the multi-bucket format.

  There is also a secondary bug: multiple function_call contents in the same update
  cause `current_fc_args` to be overwritten (last writer wins), corrupting the merged
  dict for earlier results. This would cause wrong `text` to be associated with
  the first captured result (used for Admin Agent raw_text).

fix: |
  Not yet applied. Recommended fix direction:

  Replace the single `current_fc_name` / `current_fc_args` tracking with a dict
  keyed by `call_id`. Each function_call content has a unique `call_id` attribute
  (confirmed in SDK source: Content.from_function_call requires call_id). Each
  function_result also carries the same `call_id`.

  Approach:
  ```python
  # Replace:
  current_fc_name: str | None = None
  current_fc_args: dict = {}

  # With:
  pending_calls: dict[str, dict] = {}  # call_id -> {name, args}
  ```

  Processing function_call:
  ```python
  elif content.type == "function_call":
      call_id = getattr(content, "call_id", None)
      name = getattr(content, "name", None)
      if name == "file_capture" and call_id:
          pending_calls[call_id] = {
              "name": name,
              "args": _parse_args(getattr(content, "arguments", {})),
          }
  ```

  Processing function_result:
  ```python
  elif content.type == "function_result":
      call_id = getattr(content, "call_id", None)
      parsed = _parse_result(getattr(content, "result", None))
      if call_id and call_id in pending_calls and parsed is not None:
          call_info = pending_calls.pop(call_id)
          if call_info["name"] == "file_capture":
              merged = {**call_info["args"], **parsed}
              file_capture_results.append(merged)
  ```

  This fix:
  1. Correctly pairs each function_result with its corresponding function_call via call_id
  2. Handles any number of parallel tool calls in a single update
  3. Fixes the args-overwrite bug (each call's args are stored separately)
  4. Works for both text and voice capture (same pattern in both)
  5. Backward-compatible with single-call scenarios (single pending_calls entry)

verification: "Not yet verified -- fix not applied"
files_changed: []
