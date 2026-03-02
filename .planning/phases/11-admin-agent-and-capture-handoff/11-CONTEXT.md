# Phase 11: Admin Agent and Capture Handoff - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Admin-classified captures are silently processed by the Admin Agent in the background. The capture flow returns immediately (fire-and-forget), while the Admin Agent parses items, routes them to the correct store shopping lists, and marks the inbox item as processed. No user-facing UI changes in this phase.

</domain>

<decisions>
## Implementation Decisions

### Capture handoff timing
- Fire-and-forget via `asyncio.create_task` — capture endpoint kicks off Admin Agent as a background coroutine after Classifier files to Inbox, then SSE closes immediately
- If Admin Agent fails (Azure AI timeout, tool error): log the error, leave inbox item in "failed" state. No retry mechanism. No user notification.
- No concurrency control needed — single-user app, concurrent captures are rare
- If server restarts mid-processing, the background task is lost (acceptable for v2.1)

### Multi-item parsing
- Single Admin Agent call per capture — agent receives the full capture text and splits items itself via its instructions
- Item names kept natural: whatever the user said stays as-is ("cat litter" stays "cat litter", "2% milk" stays "2% milk")
- Quantities stay inline as part of the item name ("3 cans of tuna" is the item text, no separate quantity field)
- Mixed-content captures (shopping + non-shopping): the Classifier is responsible for splitting these into separate inbox items before Admin Agent processes. Admin Agent only receives shopping-related captures.

### Store routing rules
- Store-to-category mapping lives in the Admin Agent's system instructions in the Azure AI Foundry portal (same pattern as Classifier instructions)
- Initial stores: **Jewel** (groceries, produce, dairy), **CVS** (pharmacy, toiletries), **Pet Store** (pet supplies), **Other** (catch-all for items that don't map to defined stores)
- Fixed store names only — agent must use exactly "Jewel", "CVS", "Pet Store", or "Other". Cannot invent new store names.

### Processed flag behavior
- Three states: `pending` (default when filed), `processed` (Admin Agent completed successfully), `failed` (Admin Agent errored)
- Only Admin-classified inbox items get this field — other categories (Journal, Followup, etc.) don't have it
- Not visible in mobile app this phase — processing is silent, user just sees items appear on shopping lists
- Error details go to App Insights via Python logging, not stored on the inbox item document

### Claude's Discretion
- Exact structure of the Admin Agent's system instructions in Foundry portal
- How to wire the fire-and-forget task into the existing capture endpoint
- Error logging format and App Insights integration details

</decisions>

<specifics>
## Specific Ideas

- Classifier should handle content splitting: if a user says "need milk and also remind me to call the vet", the Classifier creates two separate inbox items (Admin for shopping, appropriate category for the reminder) — this may require Classifier instruction updates
- Store mapping in Foundry portal instructions mirrors how Classifier instructions are managed — easy to update without code deploys

</specifics>

<deferred>
## Deferred Ideas

- Classifier multi-bucket splitting — now Phase 11.1
- App Insights operational audit — now Phase 14
- Retry mechanism for failed Admin Agent processing — could add a scheduled sweep or manual retry in a future phase
- User-configurable store mapping — letting users add/rename stores from the mobile app

</deferred>

---

*Phase: 11-admin-agent-and-capture-handoff*
*Context gathered: 2026-03-01*
