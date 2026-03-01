# Domain Pitfalls: v3.0 Admin Agent & Shopping Lists

**Domain:** Adding a second specialist agent (Admin Agent), store-based shopping lists, YouTube recipe ingredient extraction, and Classifier-to-Admin Agent inline handoff to an existing single-agent Foundry Agent Service system
**Researched:** 2026-03-01
**Confidence:** MEDIUM-HIGH -- Multi-agent Foundry patterns verified via official docs and SDK reference. YouTube transcript extraction pitfalls verified via GitHub issues and multiple independent sources. Cosmos DB array operations verified via official Microsoft Learn docs. SSE adapter pitfalls based on direct codebase analysis.

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or features that silently fail in production.

---

### Pitfall 1: Thread Cross-Contamination Between Classifier and Admin Agent

**What goes wrong:**
You create a single `AzureAIAgentClient` instance with `agent_id=classifier_id` and try to reuse it for the Admin Agent by swapping `agent_id` at runtime, or you pass the Classifier's Foundry thread to the Admin Agent. The Admin Agent sees the Classifier's conversation history (classification reasoning, bucket decisions) in its thread context and produces confused output -- it tries to re-classify instead of managing shopping lists, or it hallucinates items based on the Classifier's reasoning text.

**Why it happens:**
The existing codebase creates a single `classifier_client` (`AzureAIAgentClient`) at startup with `agent_id=classifier_agent_id`. The current code in `main.py` (line 184-191) binds the client to a specific agent ID. Foundry threads (server-managed conversations) are agent-scoped -- the thread contains the full message history including system prompts and tool call results for that agent. When a Classifier thread is passed to the Admin Agent via `conversation_id` in `ChatOptions`, the Admin Agent receives the Classifier's entire reasoning chain as context.

Per the official Microsoft docs: "It is unsafe to use an AgentThread instance that was created by one agent with a different agent instance."

**Consequences:**
- Admin Agent inherits Classifier's conversation context and produces nonsensical output
- Shopping list items get filed as inbox captures instead of list operations
- Token waste from feeding irrelevant classification history to the Admin Agent
- Non-deterministic behavior -- sometimes works if the Classifier context is short enough

**Prevention:**
Create a **separate** `AzureAIAgentClient` instance for the Admin Agent with its own `agent_id`. Each agent gets its own client, its own tools, and its own threads. The capture flow should be:

```
Classifier client (existing thread) -> file_capture result
   |
   v  (code-based routing in FastAPI, NOT Connected Agents)
Admin Agent client (NEW thread) -> admin tools
```

The handoff is code-based: after the Classifier's `file_capture` returns `bucket="Admin"`, the FastAPI capture endpoint creates a NEW thread on the Admin Agent client and passes only the classified text (not the Classifier's thread history). This is the same pattern used today for code-based routing (per PROJECT.md: "Connected Agents can't call local @tools").

**Detection:**
Admin Agent responses mention "classification", "confidence", or "bucket" when it should be talking about stores and items. Shopping list items appear in the Inbox container instead of the Admin/ShoppingLists container.

**Confidence:** HIGH -- verified via official AzureAIAgentClient docs and Microsoft thread isolation warnings.

---

### Pitfall 2: YouTube Transcript Extraction Blocked on Azure Cloud IPs

**What goes wrong:**
You deploy `youtube-transcript-api` to Azure Container Apps and it works in local development but returns `RequestBlocked` or `IpBlocked` errors in production. Every YouTube recipe URL submitted by the user fails silently or with an unhelpful error message. The feature appears completely broken after deployment.

**Why it happens:**
YouTube actively blocks IP ranges belonging to cloud providers (Azure, AWS, GCP). The `youtube-transcript-api` Python library makes direct HTTP requests to YouTube's servers to scrape transcript data -- it does not use an official API. When requests originate from Azure Container Apps (which uses Azure datacenter IPs), YouTube recognizes the IP block and returns HTTP 429 or custom blocking responses. This is confirmed across multiple GitHub issues (#303, #317, #511) and is the single most reported problem with this library.

**Consequences:**
- Feature works perfectly during local development and testing but fails 100% in production
- Users submit YouTube URLs and get error messages instead of ingredients
- No fallback behavior, so the capture is lost or filed as a generic Admin item without extraction

**Prevention:**
Do NOT rely on `youtube-transcript-api` for cloud-deployed extraction. Instead, use one of these approaches (ordered by recommendation):

1. **Feed the YouTube URL directly to GPT-4o as part of the Admin Agent prompt.** GPT-4o cannot access URLs, but you can use the YouTube Data API v3 (official, authenticated, not blocked) to fetch video metadata and captions. The YouTube Data API provides `captions.list` and `captions.download` endpoints that work from any IP when authenticated with an API key or OAuth token.

2. **Use the YouTube Data API v3** (official Google API) with an API key to download captions. This is the legitimate, supported way to access YouTube captions and is not subject to IP blocking. Requires a Google Cloud project and API key, but is free for the volume you need (single-user system, a few recipes per week).

3. **Client-side extraction.** The mobile app extracts the transcript before sending it to the backend. The user's phone IP is residential and will not be blocked. However, this adds complexity to the mobile app.

4. **Residential proxy.** Route `youtube-transcript-api` requests through a rotating residential proxy service. This works but adds ongoing cost and operational complexity for a hobby project.

**Recommendation:** Use the YouTube Data API v3 with an API key. It is the only approach that is reliable, legitimate, and requires no ongoing maintenance. The `youtube-transcript-api` library is fundamentally fragile for cloud deployment.

**Detection:**
Monitor for `RequestBlocked` exceptions in Application Insights. If YouTube extraction works locally but not in production, this is the cause.

**Confidence:** HIGH -- verified across multiple GitHub issues, community reports, and independent testing. This is a well-known, long-standing problem.

---

### Pitfall 3: Shopping List Items Stored as Arrays Inside Documents Cause Read-Modify-Write Race Conditions

**What goes wrong:**
You model each store's shopping list as a single Cosmos DB document with an `items` array property (e.g., `{"store": "Jewel", "items": ["milk", "eggs", "bread"]}`). When the Admin Agent adds an item at the same time the user swipes to remove a different item, you get a lost update: the agent reads the document, adds "butter" to the items array, and writes it back -- overwriting the user's concurrent removal of "eggs". The user sees "eggs" reappear on their list.

**Why it happens:**
Cosmos DB's default concurrency model is Last Writer Wins (LWW). Without ETags or the Patch API, the standard pattern is read-modify-write, which is inherently racy. Even though this is a single-user system, there are two concurrent writers: the Admin Agent (running asynchronously in the backend) and the user (swiping to remove items on the mobile app). These operations can overlap because the Agent's `get_response` call takes 2-5 seconds, during which the user might remove items.

**Consequences:**
- Removed items reappear (ghost items)
- Added items disappear
- User loses trust in the system ("I already crossed that off!")
- Debugging is difficult because it only happens under concurrent modification

**Prevention:**
Use the **Cosmos DB Patch API** for all shopping list mutations. The Patch API supports atomic array operations without reading the full document first:

```python
# Add item to array (atomic, no read required)
operations = [
    {"op": "add", "path": "/items/-", "value": {"name": "butter", "addedAt": "..."}}
]
await container.patch_item(item=doc_id, partition_key="will", patch_operations=operations)

# Remove item by index (atomic)
operations = [
    {"op": "remove", "path": "/items/2"}
]
await container.patch_item(item=doc_id, partition_key="will", patch_operations=operations)
```

The Patch API resolves concurrent modifications at the **path level**, not the document level. Two patches to different paths (one adding to `/items/-`, one removing `/items/2`) are automatically conflict-resolved. This is confirmed in the official Cosmos DB partial document update documentation.

**Important caveat:** Removing by array index is fragile if the list changes between when the UI renders and when the delete request arrives. Use a unique item ID within each array element and find-then-remove on the backend, or model items as individual documents (see Alternative Design below).

**Alternative design:** Model each shopping list item as its own Cosmos DB document rather than an array within a store document. This eliminates array index issues entirely. The query `SELECT * FROM c WHERE c.store = "Jewel" AND c.type = "shopping_item"` returns the list. Each item has its own `id` and can be independently created/deleted without touching other items. This is more Cosmos-idiomatic (one document per entity) and avoids all array manipulation pitfalls.

**Detection:**
Items that were removed by the user reappear. Items added by the agent are missing. Check Application Insights for concurrent Cosmos writes to the same document ID within a 5-second window.

**Confidence:** HIGH -- Cosmos DB Patch API and concurrency behavior verified via official Microsoft Learn documentation.

---

### Pitfall 4: Admin Agent Tools Registered on Classifier Client (Tool Leakage)

**What goes wrong:**
You add the Admin Agent's tools (e.g., `add_shopping_item`, `get_shopping_list`, `extract_recipe_ingredients`) to the `classifier_agent_tools` list in `main.py` because "both agents need tools." The Classifier agent now sees shopping list tools in its available tool set and occasionally calls `add_shopping_item` directly during classification, bypassing the Admin Agent entirely. Items appear on shopping lists without going through the Admin Agent's store-routing logic.

**Why it happens:**
The current codebase builds `agent_tools` as a flat list (main.py lines 195-198) and passes it to the streaming adapter. If Admin Agent tools are added to this same list, they become available to any agent that receives the tools list. The Classifier agent's instructions say "classify into People/Projects/Ideas/Admin" but LLMs are opportunistic -- if a tool called `add_shopping_item` is available and the user says "need cat litter", the Classifier might skip classification entirely and call the shopping tool directly.

**Consequences:**
- Classifier bypasses the bucket classification system for Admin captures
- Items land on shopping lists without Admin Agent's store-routing intelligence
- The Admin Agent never sees the capture, so no store assignment happens
- Inconsistent behavior -- sometimes classified correctly, sometimes tool-called directly

**Prevention:**
Maintain **separate tool lists** for each agent. The architecture should be:

```python
# In lifespan:
app.state.classifier_agent_tools = [classifier_tools.file_capture, transcription_tools.transcribe_audio]
app.state.admin_agent_tools = [admin_tools.add_shopping_item, admin_tools.get_shopping_list, admin_tools.extract_recipe]

# In capture flow:
# Step 1: Classifier runs with classifier_agent_tools only
# Step 2: If bucket == "Admin", Admin Agent runs with admin_agent_tools only
```

Each agent client receives only its own tools in the `ChatOptions`. The Classifier never sees shopping list tools. The Admin Agent never sees `file_capture`.

**Detection:**
Shopping list items appear without a corresponding Admin Agent run in Application Insights. The `agentChain` in the inbox document shows only `["Classifier"]` for items that should show `["Classifier", "AdminAgent"]`.

**Confidence:** HIGH -- direct analysis of existing codebase patterns.

---

## Moderate Pitfalls

Mistakes that cause significant debugging time or suboptimal UX but are recoverable without rewrites.

---

### Pitfall 5: SSE Adapter Assumes Single-Agent Tool Detection Pattern

**What goes wrong:**
The existing `FoundrySSEAdapter` (streaming/adapter.py) is hardcoded to detect `file_capture` as the sole tool outcome. When you add the Admin Agent handoff, the adapter does not know how to detect or emit events for Admin Agent tool calls (`add_shopping_item`, `extract_recipe`). The mobile app receives a CLASSIFIED event but has no information about what the Admin Agent did -- no shopping list confirmation, no ingredient extraction feedback.

**Why it happens:**
The adapter's `_emit_result_event` function (adapter.py line 59-87) only knows about four statuses: `misunderstood`, `classified`, `pending`, and fallback to `unresolved`. The stream iteration loop (line 206-218) specifically checks `content.name == "file_capture"`. When a two-agent pipeline runs, the Admin Agent's tool calls produce `function_call` and `function_result` content objects with different tool names that the adapter silently ignores.

**Consequences:**
- Admin Agent processes captures but the mobile app shows no feedback about what happened
- User sees "Filed -> Admin" but does not know the item was added to a shopping list or which store
- No shopping list confirmation event reaches the mobile app
- The safety net (line 246-255) might fire incorrectly, filing the capture as misunderstood

**Prevention:**
Extend the SSE event vocabulary for Admin Agent outcomes. Add new event types:

```python
# New SSE events for Admin Agent outcomes
def shopping_item_added_event(inbox_item_id: str, store: str, item_name: str) -> dict:
    return {
        "type": "SHOPPING_ITEM_ADDED",
        "value": {
            "inboxItemId": inbox_item_id,
            "store": store,
            "itemName": item_name,
        },
    }

def recipe_extracted_event(inbox_item_id: str, store: str, item_count: int) -> dict:
    return {
        "type": "RECIPE_EXTRACTED",
        "value": {
            "inboxItemId": inbox_item_id,
            "store": store,
            "itemCount": item_count,
        },
    }
```

The adapter needs to be extended (or a new `stream_admin_capture` function created) that handles the two-step pipeline: Classifier stream followed by Admin Agent stream. The mobile `ag-ui-client.ts` `attachCallbacks` function needs new cases in its switch statement for these event types.

**Detection:**
Admin captures show "Filed -> Admin" but no shopping list confirmation. The `COMPLETE` event fires without any Admin-specific event preceding it.

**Confidence:** HIGH -- direct analysis of existing adapter code.

---

### Pitfall 6: YouTube Recipe Videos Without Captions Fail Silently

**What goes wrong:**
User pastes a YouTube recipe URL. The backend attempts transcript extraction, gets a `TranscriptsDisabled` or `NoTranscriptFound` error, and either crashes the capture or files it as a generic Admin item with no ingredients extracted. The user has no idea why the extraction failed or what to do about it.

**Why it happens:**
Approximately 15% of YouTube videos have no captions at all (neither manual nor auto-generated). Cooking videos from small creators, non-English videos, and very recent uploads frequently lack captions. Auto-generated captions, when present, have only 60-70% accuracy, meaning ingredient names and quantities are often garbled ("two cups of flour" becomes "two cups of flower").

**Consequences:**
- Silent failure: user submits URL, nothing happens or item filed without ingredients
- Garbled ingredients from auto-captions: "1 tsp cayenne" becomes "1 tsp came in"
- No user feedback about why extraction failed
- User learns the feature is unreliable and stops using it

**Prevention:**
Build a robust fallback chain:

1. **Try official YouTube Data API captions first** (manual captions are highest quality)
2. **Fall back to auto-generated captions** with a quality warning
3. **If no captions exist at all**, inform the user: "This video doesn't have captions. Try pasting the recipe text directly."
4. **Post-extraction validation:** Have the Admin Agent sanity-check extracted ingredients. If the transcript quality is poor, the LLM can often correct obvious transcription errors ("flower" -> "flour" in a recipe context).

Add an SSE event like `EXTRACTION_FAILED` so the mobile app can show a meaningful message instead of a generic error.

**Detection:**
Application Insights tracking of YouTube extraction attempts with a `success/failure/fallback` attribute. High failure rate indicates caption availability issues. Monitor for garbled ingredient names in shopping lists.

**Confidence:** MEDIUM -- YouTube caption availability statistics are approximate but consistently reported. Auto-caption accuracy is well-documented by Google.

---

### Pitfall 7: Admin Agent Store Routing Drifts Without Grounding Data

**What goes wrong:**
The Admin Agent is instructed to route items to stores ("Jewel for groceries, CVS for pharmacy, pet store for pet supplies") via its system prompt. Initially it works. Over time, the agent starts making inconsistent decisions: "cat litter" goes to Jewel one day and the pet store the next. "Bandages" sometimes goes to CVS, sometimes to Jewel. The routing becomes unreliable, and the user spends more time correcting the agent than doing manual routing.

**Why it happens:**
LLM-based routing via instructions alone (without structured data) is inherently non-deterministic. The agent's store assignment depends on its interpretation of the item in context, which varies across runs. There is no persistent "store catalog" or "item-to-store mapping" that the agent can reference. Without grounding data, the agent relies on general world knowledge, which is noisy for edge cases.

**Consequences:**
- Items routed to wrong stores
- Same item routed differently on different days
- User loses confidence in the system
- Correcting misrouted items is tedious

**Prevention:**
Ground the Admin Agent with a structured store registry as a tool:

```python
@tool
async def get_store_registry(self) -> str:
    """Return the list of stores and their categories for item routing."""
    return json.dumps({
        "stores": [
            {"name": "Jewel", "categories": ["groceries", "produce", "dairy", "meat", "baking"]},
            {"name": "CVS", "categories": ["pharmacy", "health", "beauty", "first aid"]},
            {"name": "Pet Store", "categories": ["pet food", "pet supplies", "cat litter"]},
        ]
    })
```

Additionally, track where items were previously routed and use that history as context. If "cat litter" was routed to "Pet Store" last time, it should go there again. This can be a simple Cosmos DB query: "What store was this item type last assigned to?"

**Detection:**
User manually corrects store assignments frequently. Same item appears on different store lists across different captures.

**Confidence:** MEDIUM -- LLM non-determinism is well-established; the specific store-routing scenario is inferred from the project's use case.

---

### Pitfall 8: ContextVar Follow-Up Pattern Does Not Extend to Two-Agent Pipeline

**What goes wrong:**
The existing follow-up flow uses `_follow_up_inbox_item_id` ContextVar to tell `file_capture` to update an existing inbox doc instead of creating a new one. When the Admin Agent runs as a second step after the Classifier, the ContextVar is not set in the Admin Agent's execution context. If the Admin Agent calls any tool that needs to reference the original inbox item (e.g., to link a shopping list item back to its capture), it cannot find the context.

**Why it happens:**
ContextVars are scoped to the async task that sets them. The Classifier runs in one `get_response` call, and the Admin Agent runs in a separate `get_response` call. If the Admin Agent is invoked in a different async context (which it will be, since it is a separate client call), the ContextVar from the Classifier's context is not inherited.

**Consequences:**
- Admin Agent tools cannot reference the original inbox item
- Shopping list items are not linked back to their capture
- Follow-up flows for Admin items behave differently than other buckets
- Debugging is confusing because the ContextVar works fine for the Classifier but is empty for the Admin Agent

**Prevention:**
Pass the inbox item ID explicitly to Admin Agent tools rather than relying on ContextVars. The capture flow should:

1. Classifier runs, `file_capture` returns `item_id`
2. FastAPI code extracts the `item_id` from the Classifier's response
3. Admin Agent tools receive `inbox_item_id` as an explicit parameter (either passed in the user message or as a tool argument)

Do not extend the ContextVar pattern to a multi-agent pipeline. Explicit parameter passing is more robust and debuggable.

**Detection:**
Shopping list items in Cosmos DB have no `inboxRecordId` field. Admin Agent tool results do not include `item_id`. Follow-up flows for Admin captures break.

**Confidence:** HIGH -- direct analysis of existing ContextVar pattern in `classification.py`.

---

## Minor Pitfalls

Mistakes that cause annoyance or minor issues but are straightforward to fix.

---

### Pitfall 9: Cosmos DB Container Not Created for Shopping Lists

**What goes wrong:**
You add shopping list logic that writes to a "ShoppingLists" container, deploy to Azure Container Apps, and get `CosmosResourceNotFoundError` on the first shopping list operation. The container does not exist because `CosmosManager.initialize()` only creates container proxies for the 5 hardcoded containers: `["Inbox", "People", "Projects", "Ideas", "Admin"]`.

**Why it happens:**
`cosmos.py` line 17 defines `CONTAINER_NAMES` as a fixed list. Any new container must be added to this list AND created in the Cosmos DB account (either via Azure Portal, CLI, or Bicep/Terraform). The `CosmosManager.initialize()` method does not create containers -- it only gets references to existing ones.

**Prevention:**
Before writing any shopping list code, decide the data model first:

- **Option A: Separate "ShoppingLists" container.** Add it to `CONTAINER_NAMES`, create the container in Azure with `/userId` partition key, add a Pydantic model for shopping list documents.
- **Option B: Use the existing "Admin" container.** Add a `type` field to distinguish admin documents from shopping list items (e.g., `type: "shopping_item"` vs `type: "admin_capture"`). This avoids creating a new container but requires query filtering.

Option B is simpler for a single-user system and avoids Cosmos DB container count concerns (serverless pricing is per-container).

**Detection:**
`CosmosResourceNotFoundError` on first shopping list operation. Easy to spot, easy to fix.

**Confidence:** HIGH -- direct codebase analysis.

---

### Pitfall 10: Mobile App Treats All CLASSIFIED Events Identically

**What goes wrong:**
The mobile app's `ag-ui-client.ts` receives a CLASSIFIED event for an Admin capture and shows "Filed -> Admin (0.95)" -- the same as any other bucket. The user has no idea that a shopping list item was created or what store it was assigned to. The feedback is technically correct but useless for the shopping list use case.

**Why it happens:**
The `attachCallbacks` function in `ag-ui-client.ts` (line 68-75) handles CLASSIFIED events by extracting `bucket` and `confidence` and building a generic result string. There is no special handling for Admin bucket captures that went through the Admin Agent pipeline. The mobile app has no concept of Admin-specific outcomes.

**Prevention:**
The capture flow for Admin items needs to emit a richer event that the mobile app can handle differently. Options:

1. **New event type (ADMIN_PROCESSED)** that includes Admin-specific data (store name, item count, what was done)
2. **Extended CLASSIFIED event** with an optional `adminResult` field when `bucket == "Admin"`
3. **Second SSE stream** where the Admin Agent's processing is streamed as additional events after CLASSIFIED

Option 1 is cleanest -- it follows the existing pattern of type-specific events (CLASSIFIED, MISUNDERSTOOD, LOW_CONFIDENCE).

On the mobile side, add a new callback:
```typescript
onAdminProcessed?: (inboxItemId: string, action: string, details: object) => void;
```

**Detection:**
Admin captures show the same generic "Filed -> Admin" feedback as non-shopping-list Admin items. Users have no confirmation that their shopping list was updated.

**Confidence:** HIGH -- direct analysis of mobile app codebase.

---

### Pitfall 11: Timeout Pressure in Two-Agent Pipeline

**What goes wrong:**
The existing adapter uses `asyncio.timeout(60)` for the entire capture stream (adapter.py line 181). A two-agent pipeline (Classifier 2-3s + Admin Agent 3-5s + tool execution) approaches this timeout, especially if YouTube transcript extraction is involved (network round-trip to YouTube + LLM processing of transcript). Complex recipes with many ingredients push the total time past 60 seconds, and the capture times out with a generic error.

**Why it happens:**
The 60-second timeout was calibrated for a single-agent pipeline (Classifier only). Adding a second agent effectively doubles the LLM call time. Adding YouTube extraction adds a third network dependency. The timeout is global (covers the entire stream), not per-step.

**Consequences:**
- YouTube recipe captures fail intermittently
- Timeout errors are not actionable for the user
- Partial results are lost (Classifier classified successfully, but Admin Agent timed out before finishing)

**Prevention:**
Either increase the timeout for Admin-routed captures or implement per-step timeouts:

```python
# Separate timeouts per stage
CLASSIFIER_TIMEOUT = 30  # seconds
ADMIN_AGENT_TIMEOUT = 45  # seconds (more for YouTube extraction)

# Or a single increased timeout for multi-agent pipelines
MULTI_AGENT_TIMEOUT = 90  # seconds
```

Also, stream progress events between stages so the user knows the system is working: "Classifying..." -> "Classified as Admin" -> "Extracting recipe ingredients..." -> "Added 12 items to Jewel shopping list."

**Detection:**
TimeoutError in Application Insights for Admin captures. YouTube recipe captures have a higher timeout rate than text captures.

**Confidence:** HIGH -- direct analysis of existing timeout values and estimated pipeline duration.

---

### Pitfall 12: Shopping List Screen Fetches Data Shape Incompatible with Inbox Pattern

**What goes wrong:**
You build the new "Status & Priorities" screen by copying the Inbox screen's data fetching pattern (`GET /api/inbox` returning `InboxListResponse`). But shopping list data has a fundamentally different shape: it is grouped by store, each store has a list of items, and items can be checked off. The inbox pattern (flat list of captures) does not map to this structure. You end up with awkward data transforms on the mobile side, or you build a bespoke API that does not follow the existing patterns.

**Why it happens:**
The inbox is a flat, reverse-chronological list of captures. Shopping lists are hierarchical (store -> items) and stateful (items can be completed/removed). These are different data access patterns that require different API design and different UI components.

**Consequences:**
- Flat list API does not support "group by store" efficiently
- Mobile side needs complex client-side grouping logic
- No support for item completion state in the inbox response model
- API feels bolted-on rather than designed

**Prevention:**
Design the shopping list API endpoint independently from the inbox API:

```python
# New API endpoint for shopping lists
@router.get("/api/shopping-lists")
async def get_shopping_lists(request: Request) -> ShoppingListsResponse:
    """Return shopping lists grouped by store."""
    # Query Cosmos for shopping items grouped by store
    ...

@router.delete("/api/shopping-lists/{store}/{item_id}")
async def remove_shopping_item(request: Request, store: str, item_id: str):
    """Remove a shopping list item."""
    ...
```

Response shape:
```json
{
  "stores": [
    {
      "name": "Jewel",
      "items": [
        {"id": "...", "name": "milk", "addedAt": "...", "source": "recipe:..."}
      ]
    }
  ]
}
```

Do not try to reuse `InboxListResponse` or `InboxItemResponse`. They are different domain concepts.

**Detection:**
Mobile code has excessive `.filter()`, `.reduce()`, and `.group()` calls to reshape inbox-style data into store-grouped lists. Or the API endpoint returns data that does not match what the UI needs.

**Confidence:** HIGH -- direct analysis of existing data models and API patterns.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Admin Agent registration | Pitfall 1 (thread contamination), Pitfall 4 (tool leakage) | Create separate AzureAIAgentClient, separate tool lists |
| Shopping list data model | Pitfall 3 (race conditions), Pitfall 9 (container not created) | Use Patch API or individual documents; create container first |
| YouTube recipe extraction | Pitfall 2 (IP blocking), Pitfall 6 (no captions), Pitfall 11 (timeouts) | Use YouTube Data API v3; build fallback chain; increase timeout |
| Classifier -> Admin handoff | Pitfall 1 (thread contamination), Pitfall 8 (ContextVar scope) | Code-based routing with explicit param passing, new threads |
| SSE streaming for Admin | Pitfall 5 (adapter assumes single agent), Pitfall 10 (generic CLASSIFIED) | New event types, extended adapter |
| Mobile shopping list screen | Pitfall 12 (data shape mismatch), Pitfall 10 (no Admin feedback) | Independent API design, new SSE events |

---

## Key Architectural Decision: Shopping List Item Granularity

The most impactful design decision for v3.0 is how shopping list items are stored in Cosmos DB. This decision affects pitfalls 3, 9, and 12.

**Recommendation: One document per shopping list item** (not arrays within a store document).

| Approach | Pros | Cons |
|---|---|---|
| Array in store doc | Fewer documents, single read for full list | Race conditions, array index fragility, max document size |
| Individual item docs | Atomic create/delete, no race conditions, simple queries | More documents, cross-partition queries if not careful |

For a single-user system with serverless Cosmos DB pricing (pay per RU, not per document), individual documents are strongly preferred. Each item gets its own `id`, can be independently created and deleted, and queries like `SELECT * FROM c WHERE c.store = "Jewel" AND c.type = "shopping_item"` are efficient with a composite index.

---

## Sources

- [AzureAIAgentClient API Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) -- agent_id, should_cleanup_agent, thread isolation
- [Cosmos DB Partial Document Update](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update) -- Patch API operations, array manipulation, conflict resolution
- [Cosmos DB Optimistic Concurrency Control](https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency) -- ETag-based concurrency
- [youtube-transcript-api GitHub Issues #303](https://github.com/jdepoix/youtube-transcript-api/issues/303) -- cloud IP blocking
- [youtube-transcript-api GitHub Issues #317](https://github.com/jdepoix/youtube-transcript-api/issues/317) -- AWS Lambda blocking
- [youtube-transcript-api GitHub Issues #511](https://github.com/jdepoix/youtube-transcript-api/issues/511) -- IP blocking with proxies
- [youtube-transcript-api PyPI](https://pypi.org/project/youtube-transcript-api/) -- library documentation and proxy support
- [Azure AI Foundry Connected Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) -- multi-agent patterns
- [Multi-Turn Conversations](https://learn.microsoft.com/en-us/agent-framework/user-guide/agents/multi-turn-conversation) -- thread safety warnings
- [Building a nutritional co-pilot using LLMs](https://medium.com/@kbambalov/building-a-nutritional-co-pilot-using-llms-part-1-recipe-extraction-e112645ef9fd) -- recipe extraction patterns
