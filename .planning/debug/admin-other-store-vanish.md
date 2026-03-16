---
status: awaiting_human_verify
trigger: "Admin-classified items that don't match Jewel, CVS, or Pet Store are silently vanishing -- they get deleted from Inbox after Admin Agent processing but never appear on the Status/Shopping List screen under 'Other' or any store."
created: 2026-03-15T00:00:00Z
updated: 2026-03-15T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED -- admin_handoff.py unconditionally deleted inbox items after any successful agent response, even when the agent did not call add_shopping_list_items
test: Unit tests covering tool-called and no-tool-called paths
expecting: All 16 tests pass, including 3 new no-tool-call tests
next_action: Human verification -- deploy and test with a non-standard shopping item

## Symptoms

expected: Items captured and classified as Admin that don't fit Jewel, CVS, or Pet Store should appear under an "Other" store category on the Status screen
actual: Items silently vanish -- deleted from Inbox after Admin Agent processing, but never appear on the Shopping List/Status screen at all
errors: No error messages -- completely silent failure
reproduction: Capture any text that gets classified as Admin but doesn't relate to Jewel (groceries), CVS (pharmacy), or Pet Store items. Go to Status screen. Items are processed (deleted from Inbox) but don't appear anywhere.
started: Discovered 2026-03-15. Shopping list feature completed ~2026-03-03. All prior test items happened to fit the three known stores.

## Eliminated

- hypothesis: "KNOWN_STORES doesn't include 'other', so per-partition query never finds items with store='other'"
  evidence: KNOWN_STORES in documents.py line 91 is ["jewel", "cvs", "pet_store", "other"] -- "other" IS included. GET endpoint queries all four partitions.
  timestamp: 2026-03-15

- hypothesis: "Store name case mismatch between agent output and KNOWN_STORES causes items to be written to wrong partition"
  evidence: admin.py tool normalizes store via .strip().lower() (line 57), and any non-matching store falls back to "other" (lines 64-71). Even "Other", "OTHER", "Walmart" all become "other".
  timestamp: 2026-03-15

- hypothesis: "Items with missing store field bypass the fallback"
  evidence: admin.py line 57 uses .get("store", "other") -- missing store defaults to "other". No bypass possible.
  timestamp: 2026-03-15

## Evidence

- timestamp: 2026-03-15
  checked: KNOWN_STORES constant in documents.py
  found: ["jewel", "cvs", "pet_store", "other"] -- "other" is present
  implication: The GET endpoint DOES query the "other" partition. If items existed there, they would be found.

- timestamp: 2026-03-15
  checked: add_shopping_list_items tool fallback logic in admin.py lines 55-74
  found: All items with unrecognized store names are normalized to "other". Default for missing store is also "other". Names/stores are lowercased.
  implication: IF the agent calls the tool, items will always land in a valid partition. The write path is correct.

- timestamp: 2026-03-15
  checked: admin_handoff.py process_admin_capture lines 68-106
  found: After get_response returns (line 73-75), the function UNCONDITIONALLY deletes the inbox item (lines 77-82). There is no check for whether the agent actually invoked add_shopping_list_items.
  implication: If the Foundry Agent responds conversationally without calling the tool (e.g., "I've noted your request"), the inbox item is still deleted. No shopping list items are written. The item vanishes.

- timestamp: 2026-03-15
  checked: Admin Agent instructions source
  found: Instructions are managed entirely in Azure AI Foundry portal (agents/admin.py line 59). Tool description says store options are "jewel, cvs, pet_store, or other". Agent may not always invoke tool for non-standard items.
  implication: The Foundry agent's behavior for non-standard items is opaque. If it chooses not to call the tool, the code has no safety net.

- timestamp: 2026-03-15
  checked: main.py lifespan -- admin tool wiring (lines 222-235)
  found: admin_tools are correctly created and passed as [admin_tools.add_shopping_list_items]. The agent has the tool available.
  implication: The agent CAN call the tool -- the question is whether it DOES for all inputs.

- timestamp: 2026-03-15
  checked: FunctionTool.invocation_count in agent_framework (line 326 of _tools.py)
  found: FunctionTool tracks invocations via invocation_count attribute, incremented on each __call__. Cumulative across all calls -- can snapshot before/after to detect tool usage.
  implication: Can use this to detect whether agent called tool during get_response without modifying the agent framework.

- timestamp: 2026-03-15
  checked: All 100 unit tests after fix applied
  found: 100 passed, 3 skipped (integration tests). No regressions. 3 new tests specifically validate no-tool-call behavior.
  implication: Fix is safe and correct.

## Resolution

root_cause: admin_handoff.py unconditionally deletes the inbox item after any successful Admin Agent response, regardless of whether the agent actually invoked the add_shopping_list_items tool. When the Foundry Agent receives items it cannot route to known stores and chooses to respond conversationally instead of calling the tool with store "other", the inbox item is deleted but no shopping list items are written. The items silently vanish.

fix: Added tool invocation detection to process_admin_capture using FunctionTool.invocation_count. Before calling get_response, the code snapshots the tool invocation count. After get_response, it checks if the count increased. If the tool was NOT called, the inbox item is marked as "failed" (not deleted), preventing silent data loss. A warning log is emitted for observability in App Insights. Also extracted _mark_inbox_failed helper and _count_tool_invocations utility.

verification: 16 unit tests pass (13 existing + 3 new). All 100 backend tests pass. Ruff lint + format clean. Key new tests: test_no_tool_call_marks_failed_not_deleted (validates item NOT deleted when tool not called), test_no_tool_call_does_not_raise (fire-and-forget safety), test_tool_call_still_deletes (regression check for happy path).

files_changed:
- backend/src/second_brain/processing/admin_handoff.py
- backend/tests/test_admin_handoff.py
