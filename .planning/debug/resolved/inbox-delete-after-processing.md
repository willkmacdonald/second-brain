---
status: resolved
trigger: "Investigate why inbox items are NOT being deleted after successful Admin Agent processing"
created: 2026-03-03T00:00:00Z
updated: 2026-03-03T21:00:00Z
---

## Current Focus

hypothesis: Two failure modes can prevent inbox deletion - both stem from the exception handling structure in admin_handoff.py
test: code analysis + UAT evidence correlation
expecting: root cause identified
next_action: return diagnosis

## Symptoms

expected: After process_admin_capture succeeds and shopping list items are created, the inbox item should be deleted via inbox_container.delete_item
actual: Shopping list items (milk, eggs) appear correctly, but original inbox item remains in Inbox
errors: None visible -- processing succeeds but delete silently fails or is never reached
reproduction: Send text capture classified as Admin, open Status screen to trigger processing, check Inbox -- item still there
started: First observed in Phase 12.1 UAT (may have never worked in production)

## Eliminated

- hypothesis: delete_item uses wrong partition key
  evidence: partition_key="will" matches userId field; read_item uses same value and succeeds
  timestamp: 2026-03-03

- hypothesis: inbox_item_id is wrong or empty
  evidence: shopping_lists.py passes unprocessed[0]["id"] from Cosmos query; admin_handoff reads doc successfully with same ID (line 53)
  timestamp: 2026-03-03

- hypothesis: processing never triggers from Status screen
  evidence: UAT Test 2 passed (banner appeared), Test 4 passed (shopping items appeared)
  timestamp: 2026-03-03

- hypothesis: mobile app caching stale inbox list
  evidence: inbox.tsx uses useFocusEffect to re-fetch on tab focus (line 71-74); fresh data every navigation
  timestamp: 2026-03-03

- hypothesis: background task garbage collected before completion
  evidence: app.state.background_tasks set prevents GC; add_done_callback removes on completion; pattern is correct
  timestamp: 2026-03-03

- hypothesis: adapter.py also triggers processing creating interference
  evidence: commit 0675b16 removed all adapter triggers; only shopping_lists.py triggers remain
  timestamp: 2026-03-03

## Evidence

- timestamp: 2026-03-03
  checked: admin_handoff.py success path structure
  found: delete_item IS on the success path (line 79), wrapped in its own try/except (lines 78-99). Generic Exception handler on line 93 silently swallows delete failures with only a warning log.
  implication: if delete fails for any reason other than 404, item persists with adminProcessingStatus="pending"

- timestamp: 2026-03-03
  checked: admin_handoff.py failure path structure
  found: outer except on line 108 catches ALL exceptions from get_response (including TimeoutError). Sets adminProcessingStatus="failed" on lines 120-124. Delete is never reached on this path.
  implication: if get_response fails after tool execution, shopping items exist but delete never happens

- timestamp: 2026-03-03
  checked: shopping_lists.py retry query (lines 119-125)
  found: query filters for adminProcessingStatus undefined OR "failed". Items with "pending" are EXCLUDED.
  implication: if delete fails and status stays "pending", item is stuck forever -- never retried, never deleted

- timestamp: 2026-03-03
  checked: asyncio.timeout(60) scope (line 72)
  found: timeout wraps ONLY get_response, NOT delete_item. The agent framework's tool invocation loop runs INSIDE get_response -- tool executes mid-call.
  implication: timeout can fire after tool writes shopping items but before get_response returns

- timestamp: 2026-03-03
  checked: agent_framework tool execution flow
  found: AzureAIAgentClient uses Assistants API pattern. Tool is executed locally between requires_action and submit_tool_outputs. If timeout/error occurs after tool execution but before run completion, get_response raises but tool side effects (Cosmos writes) persist.
  implication: confirms that shopping items can exist while get_response throws

- timestamp: 2026-03-03
  checked: mobile InboxItem.tsx (line 135)
  found: only shows "Processing failed" indicator when adminProcessingStatus === "failed". No indicator for "pending".
  implication: user would not see any visual indicator if status is "pending" -- item looks normal

- timestamp: 2026-03-03
  checked: UAT Test 3 user report
  found: "milk and eggs was not automatically deleted -- when I went back to the inbox milk and eggs was still there (not processed as part of Status processing)" -- no mention of "Processing failed" red text
  implication: status is likely "pending" (not "failed"), pointing to either silent delete failure OR get_response failure + failed-update-failure double fault

## Resolution

root_cause: |
  TWO code-level issues create failure modes where inbox items survive processing:

  **PRIMARY (most likely): get_response exception after tool execution (admin_handoff.py lines 68-116)**
  The asyncio.timeout(60) wraps the entire get_response call. The agent framework
  executes the add_shopping_list_items tool locally DURING get_response (Assistants API
  requires_action pattern). If get_response subsequently fails (timeout, network error,
  ChatClientException from THREAD_RUN_FAILED), execution jumps to the except on line 108.
  Shopping list items persist (tool already wrote them), but delete on line 79 is never reached.
  Status is set to "failed" on line 123. On next Status screen open, item is retried, but
  tool re-executes creating DUPLICATE shopping list items.

  **SECONDARY (creates permanent stuck state): silent delete failure (admin_handoff.py lines 93-99)**
  If get_response succeeds but delete_item fails with any non-404 exception, the generic
  except on line 93 swallows the error with a warning log. The item remains in Cosmos with
  adminProcessingStatus="pending". The retry query in shopping_lists.py (lines 119-125)
  excludes "pending" items. Result: item is STUCK FOREVER -- never deleted, never retried.
  This is the WORSE failure mode because it's unrecoverable without manual intervention.

  **STRUCTURAL ROOT CAUSE:** The success path has no fallback. When get_response succeeds
  (tool writes shopping items) but delete fails, adminProcessingStatus stays "pending"
  permanently. There is no code path that transitions "pending" to either "failed" or
  triggers deletion again.

fix:
verification:
files_changed: []
