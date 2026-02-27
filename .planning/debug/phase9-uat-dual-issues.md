---
status: diagnosed
trigger: "Phase 9 UAT: 'Untitled' displayed instead of capture text + ambiguous text triggers misunderstood instead of low-confidence"
created: 2026-02-27T00:00:00Z
updated: 2026-02-27T00:00:00Z
---

## Current Focus

hypothesis: Two separate root causes identified
test: Code tracing complete
expecting: N/A - diagnosis only
next_action: Report findings

## Symptoms

expected:
  1. Conversation screen shows original capture text as title
  2. Ambiguous text like "thing about the place" triggers low-confidence classification with bucket buttons on capture screen

actual:
  1. Conversation screen shows "Untitled" instead of capture text
  2. "thing about the place" triggers misunderstood follow-up flow instead of low-confidence

errors: None (behavioral issues, not crashes)
reproduction: Text capture with ambiguous input
started: Phase 9 UAT

## Evidence

- timestamp: 2026-02-27
  checked: conversation/[threadId].tsx title source
  found: Conversation screen does NOT display a title header from the item. It uses hardcoded "Resolve" as headerTitle (line 93/129). The "Captured Text" card shows item.rawText (line 134). "Untitled" is NOT coming from the conversation screen itself.
  implication: "Untitled" must be referring to something else -- possibly the InboxItem preview in the inbox list

- timestamp: 2026-02-27
  checked: InboxItem.tsx preview line
  found: Line 103: `const preview = item.title || item.rawText.slice(0, 60)` -- the inbox list shows item.title if present, falls back to rawText
  implication: If item.title is "Untitled" (the default in file_capture tool), it would show "Untitled" instead of rawText

- timestamp: 2026-02-27
  checked: file_capture tool title parameter default
  found: Line 76-77 in classification.py: `title: ... = "Untitled"` -- the title parameter has a default value of "Untitled"
  implication: If the Foundry classifier agent doesn't pass a title argument, the default "Untitled" is stored

- timestamp: 2026-02-27
  checked: InboxDocument model
  found: title field is `str | None = None` in the model, but classification.py always writes whatever the agent provides (or "Untitled" default)
  implication: The title "Untitled" is truthy, so InboxItem.tsx shows it instead of falling back to rawText

- timestamp: 2026-02-27
  checked: misunderstood path in _write_to_cosmos
  found: For misunderstood items (line 127-138), title is written to the InboxDocument. The Foundry agent likely passes title="Untitled" or omits title (getting the default) for misunderstood captures.
  implication: Root cause for Issue 1 confirmed

- timestamp: 2026-02-27
  checked: _emit_result_event for MISUNDERSTOOD
  found: Line 73 in adapter.py: `question_text = detected_tool_args.get("title", "Could you clarify?")` -- the MISUNDERSTOOD event uses the title field as the question text
  implication: The "title" field serves double duty: it's both the display title AND the clarification question for misunderstood items. This is a design issue.

- timestamp: 2026-02-27
  checked: CLASSIFIED vs MISUNDERSTOOD decision boundary
  found: The status field is set by the Foundry classifier agent (GPT-4o) based on its instructions in the AI Foundry portal. The backend code merely passes through what the agent decides. The file_capture tool description says: "'classified' (confidence >= 0.6), 'pending' (confidence < 0.6), or 'misunderstood'"
  implication: The agent instructions in Foundry portal determine when something is misunderstood vs low-confidence. The backend has no hardcoded thresholds for this distinction.

- timestamp: 2026-02-27
  checked: How CLASSIFIED event triggers low-confidence HITL on capture screen
  found: In ag-ui-client.ts line 66-73, CLASSIFIED events always call onComplete with the result. There is NO separate low-confidence path in the SSE protocol. The HITL bucket buttons on the capture screen (hitlQuestion state) are triggered by the legacy CUSTOM/HITL_REQUIRED event (line 121-129), not by a low-confidence CLASSIFIED event.
  implication: The v2 SSE protocol has no low-confidence-with-bucket-buttons path. CLASSIFIED always auto-files. The only HITL path is MISUNDERSTOOD (conversational follow-up) or the legacy HITL_REQUIRED. There is no mechanism for the capture screen to show bucket buttons for a low-confidence classification.

- timestamp: 2026-02-27
  checked: Classification threshold enforcement
  found: The 0.6 threshold in ClassifierTools.__init__ is stored but never actually enforced by the backend code. The tool description tells the agent the threshold, but the agent chooses the status. The backend trusts whatever status the agent passes.
  implication: Whether "thing about the place" gets classified as low-confidence vs misunderstood is entirely up to the Foundry agent's judgment based on its portal instructions

## Eliminated

- hypothesis: Conversation screen renders "Untitled" from its own code
  evidence: The conversation screen uses "Resolve" as header title and shows rawText in the quote card. It never shows a "title" field.
  timestamp: 2026-02-27

## Resolution

root_cause: |
  **Issue 1 (Untitled display):** Two interacting problems:
  (a) The file_capture tool has `title = "Untitled"` as its default parameter value. When the Foundry classifier agent doesn't provide a meaningful title for misunderstood captures, "Untitled" is stored in Cosmos DB.
  (b) InboxItem.tsx line 103 uses `item.title || item.rawText.slice(0, 60)` for the preview. Since "Untitled" is a truthy string, it shows "Untitled" instead of falling back to rawText. The title "Untitled" was intended as a fallback label for bucket documents, but it poisons the inbox list display.
  (c) Additionally, adapter.py line 73 uses `detected_tool_args.get("title", "Could you clarify?")` as the MISUNDERSTOOD question text -- the title field is overloaded to serve as both display title and clarification question.

  **Issue 2 (misunderstood vs low-confidence):** The Foundry classifier agent's instructions (managed in the AI Foundry portal, not in code) determine when a capture is classified as "misunderstood" vs "pending" (low confidence). The backend code has no hardcoded logic to differentiate these -- it passes through whatever the agent decides. Furthermore, the v2 SSE protocol has no path for showing bucket buttons on the capture screen for low-confidence items. CLASSIFIED always auto-files via onComplete. The only interactive path is MISUNDERSTOOD (conversational follow-up). The legacy HITL_REQUIRED event could show bucket buttons, but it's not being emitted by the v2 adapter.

fix: N/A (diagnosis only)
verification: N/A
files_changed: []
