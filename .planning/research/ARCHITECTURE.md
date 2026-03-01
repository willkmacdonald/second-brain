# Architecture: Admin Agent & Shopping Lists Integration

**Domain:** Specialist agent integration into existing capture-and-classify pipeline
**Researched:** 2026-03-01
**Confidence:** HIGH for handoff pattern and data model, MEDIUM for YouTube transcript integration, HIGH for mobile screen architecture

---

## Existing Architecture Summary

Before designing the Admin Agent integration, here is the current system as shipped in v2.0:

```
Mobile (Expo)                    Backend (FastAPI on Azure Container Apps)
─────────────                    ────────────────────────────────────────
Capture Screen ──POST /api/capture──►  capture.py → stream_text_capture()
  (Voice/Text)                         │
                                       ├─ AzureAIAgentClient.get_response(stream=True)
                                       │    └─ Classifier Agent (Foundry, persistent)
                                       │         ├─ transcribe_audio @tool (voice only)
                                       │         └─ file_capture @tool
                                       │              └─ ClassifierTools._write_to_cosmos()
                                       │                   ├─ Inbox container (always)
                                       │                   └─ Bucket container (People/Projects/Ideas/Admin)
                                       │
                                       └─ FoundrySSEAdapter yields AG-UI events
                                            └─ STEP_START → STEP_END → CLASSIFIED/MISUNDERSTOOD/LOW_CONFIDENCE → COMPLETE

Inbox Screen ──GET /api/inbox──►  inbox.py → Cosmos query
             ──DELETE /api/inbox/{id}──►  cascade delete (inbox + bucket)
             ──PATCH /api/inbox/{id}/recategorize──►  cross-container move
```

**Key constraints inherited from v2.0:**
- Connected Agents cannot call local @tool functions (confirmed in prior research)
- Each agent runs as an independent persistent Foundry agent invoked by FastAPI code
- `AzureAIAgentClient` with `agent_id` and `should_cleanup_agent=False`
- Agent instructions managed in AI Foundry portal (not in code)
- SSE streaming via async generator → StreamingResponse
- All Cosmos operations use `partition_key="will"` (single user)

---

## Question 1: How Does Classifier → Admin Agent Handoff Work?

### Recommended Pattern: Code-Based Sequential Routing

**NOT HandoffBuilder. NOT Connected Agents.** Use FastAPI code-based routing -- the same pattern v2.0 already uses for the Classifier, extended with a conditional second agent call.

The handoff pattern from the Azure Architecture Center docs describes this as the "routing" or "dispatch" pattern where routing decisions are made deterministically by code, not by an agent deciding to transfer. This fits because:

1. The Classifier already determines `bucket="Admin"` with confidence scoring
2. The decision to invoke the Admin Agent is deterministic: `if bucket == "Admin"` → route to Admin Agent
3. No need for the Classifier to "decide" to hand off -- FastAPI code observes the classification result and routes

### Architecture: Two-Phase Capture Flow

```
User captures: "Need cat litter and I should pick up that prescription"
                                │
                                ▼
              ┌─────────────────────────────────┐
              │     Phase 1: Classification      │
              │  (existing Classifier pipeline)  │
              │                                  │
              │  Classifier Agent sees text       │
              │  → calls file_capture(            │
              │      bucket="Admin",              │
              │      confidence=0.92,             │
              │      status="classified"          │
              │    )                              │
              │  → Inbox doc created              │
              │  → Admin doc created              │
              └─────────────┬───────────────────┘
                            │
                   SSE: CLASSIFIED event
                   observed by adapter
                            │
                            ▼
                   bucket == "Admin"?
                   ┌─────┐     ┌──────┐
                   │ YES │     │  NO  │
                   └──┬──┘     └──┬───┘
                      │           │
                      ▼           ▼
              ┌───────────────┐  Standard flow
              │ Phase 2:      │  (CLASSIFIED event,
              │ Admin Agent   │   auto-reset)
              │ enrichment    │
              │               │
              │ Admin Agent   │
              │ receives text │
              │ + context     │
              │ → calls       │
              │   add_shopping│
              │   _list_items │
              │ → items filed │
              │   to Cosmos   │
              └───────┬───────┘
                      │
                      ▼
              SSE: ADMIN_ENRICHED event
              (new event type for mobile)
```

### Implementation: Adapter-Level Routing

The routing happens inside a new `stream_admin_enrichment()` function that the capture adapter calls after observing a `CLASSIFIED` event with `bucket="Admin"`. This is **not** a new endpoint -- it extends the existing SSE stream.

```python
# In streaming/adapter.py (extended)

async def stream_text_capture(...) -> AsyncGenerator[str, None]:
    """Extended to include Admin Agent enrichment after classification."""
    # ... existing Phase 1 code (unchanged) ...

    # After Phase 1 completes and we have file_capture result:
    if detected_tool == "file_capture":
        # Emit the CLASSIFIED event immediately (user sees instant feedback)
        yield encode_sse(classified_event(item_id, bucket, confidence))

        # Phase 2: If Admin bucket, invoke Admin Agent for enrichment
        if bucket == "Admin" and admin_client is not None:
            yield encode_sse(step_start_event("Processing Admin"))
            async for event in stream_admin_enrichment(
                admin_client=admin_client,
                raw_text=user_text,
                inbox_item_id=item_id,
                admin_tools=admin_tools,
            ):
                yield event
            yield encode_sse(step_end_event("Processing Admin"))

    yield encode_sse(complete_event(thread_id, run_id))
```

### Why This Pattern Over Alternatives

| Pattern | Pros | Cons | Verdict |
|---------|------|------|---------|
| **Code-based routing (recommended)** | Uses existing patterns, deterministic, observable, each agent has own tools | Two serial agent calls per Admin capture | Best fit -- proven pattern, zero new infrastructure |
| Connected Agents (Foundry-native) | Server-managed handoff | Cannot call local @tools, deprecated in new portal | Ruled out by constraints |
| HandoffBuilder | Agent decides routing | Known bugs with Foundry v2 API (issue #3097), adds complexity | Ruled out |
| Single agent with all tools | One agent call | Overloaded prompt, tool confusion, harder to maintain | Anti-pattern for specialist agents |

### Latency Impact

Admin captures will take approximately 2x the wall time of non-Admin captures (two sequential agent calls). For a capture-and-forget UX, this is acceptable because:
- The user sees "Classified" immediately after Phase 1
- Phase 2 runs while the user sees the classification feedback
- The "Processing Admin" step provides progress indication
- Total time: ~3-5 seconds (vs ~1.5-2.5 seconds for non-Admin)

---

## Question 2: Shopping List Data Model in Cosmos DB

### Recommended: New `ShoppingLists` Container (Not Extend Admin)

**Create a dedicated `ShoppingLists` container** rather than extending the Admin container. The Admin container holds generic admin captures (documents with rawText, title, classificationMeta). Shopping lists are a fundamentally different data shape -- they are persistent, mutable collections with line items, not point-in-time captures.

### Data Model

```
ShoppingLists Container
  Partition Key: /userId

  Document structure:
  ┌──────────────────────────────────────────────────┐
  │ ShoppingListDocument                              │
  │                                                    │
  │   id: "list-jewel"           (store-scoped ID)    │
  │   userId: "will"             (partition key)      │
  │   storeName: "Jewel"         (display name)       │
  │   storeSlug: "jewel"         (normalized key)     │
  │   items: [                                        │
  │     {                                             │
  │       id: "item-uuid-1"                           │
  │       name: "Cat litter"                          │
  │       quantity: "1"          (free-text)           │
  │       source: "capture"      (capture|recipe|manual)│
  │       sourceInboxId: "inbox-uuid-abc"             │
  │       addedAt: "2026-03-01T..."                   │
  │       checked: false                              │
  │     },                                            │
  │     {                                             │
  │       id: "item-uuid-2"                           │
  │       name: "Chicken breast (2 lbs)"              │
  │       quantity: "2 lbs"                            │
  │       source: "recipe"                            │
  │       sourceRecipeUrl: "https://youtube.com/..."   │
  │       addedAt: "2026-03-01T..."                   │
  │       checked: false                              │
  │     }                                             │
  │   ]                                               │
  │   createdAt: "2026-03-01T..."                     │
  │   updatedAt: "2026-03-01T..."                     │
  └──────────────────────────────────────────────────┘
```

### Pydantic Models

```python
class ShoppingItem(BaseModel):
    """Individual item on a shopping list."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    quantity: str | None = None
    source: str = "capture"  # capture | recipe | manual
    sourceInboxId: str | None = None
    sourceRecipeUrl: str | None = None
    addedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    checked: bool = False


class ShoppingListDocument(BaseModel):
    """One shopping list per store. Document in ShoppingLists container."""
    id: str  # "list-{storeSlug}"
    userId: str = "will"
    storeName: str  # "Jewel", "CVS", "Pet Store"
    storeSlug: str  # "jewel", "cvs", "pet-store"
    items: list[ShoppingItem] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### Why One Document Per Store (Not One Per Item)

Shopping lists are small (10-30 items per store). One document per store means:
- **Single read** to display all items for a store
- **Single write** (upsert) when adding items -- no multi-document transactions
- **Simple delete** -- remove item from array, upsert document
- **Cosmos free tier friendly** -- fewer RUs consumed, fewer documents
- Items array will never exceed Cosmos's 2MB document limit for a personal shopping list

If this were multi-user with hundreds of items per store, items-as-documents with a composite partition key would be better. For single-user with <50 items per store, the embedded array pattern is correct.

### Why Not Extend the Admin Container

| Approach | Pros | Cons |
|----------|------|------|
| **New ShoppingLists container** | Clean data shape, independent queries, no schema pollution, easy to add new list types later | One more container to initialize |
| Extend Admin container | No new container | Mixes captures (immutable docs) with lists (mutable collections), complex queries, Admin container schema becomes overloaded |

The Admin container holds classified capture documents (`AdminDocument` with rawText, classificationMeta). Mixing in shopping list documents with completely different fields and query patterns would violate single-responsibility and make both harder to query.

### Cosmos Manager Changes

```python
# In db/cosmos.py
CONTAINER_NAMES: list[str] = [
    "Inbox", "People", "Projects", "Ideas", "Admin", "ShoppingLists"
]
```

One line change. The `CosmosManager.initialize()` method already loops over `CONTAINER_NAMES` and creates container clients.

### Shopping List API Endpoints

```
GET  /api/shopping-lists              → All lists (one per store)
GET  /api/shopping-lists/{storeSlug}  → Single store list with items
PATCH /api/shopping-lists/{storeSlug}/items/{itemId}/check   → Toggle checked
DELETE /api/shopping-lists/{storeSlug}/items/{itemId}         → Remove item
POST /api/shopping-lists/{storeSlug}/items                   → Manual add (future)
```

These are standard REST endpoints, NOT SSE streaming. The "Status & Priorities" screen fetches lists via GET, and item interactions (check/delete) are immediate PATCH/DELETE.

---

## Question 3: Mobile "Status & Priorities" Screen

### Recommended: New Tab with REST Data Fetching

The "Status & Priorities" screen is a **read-heavy** view that displays agent-processed output. It does NOT need SSE streaming -- it fetches shopping lists via REST API calls, the same way the Inbox screen fetches inbox items.

### Tab Navigation Update

```
Current tabs:  [Capture]  [Inbox]
New tabs:      [Capture]  [Inbox]  [Status]
```

Add a third tab to the existing `(tabs)/_layout.tsx`.

### Screen Architecture

```
StatusScreen
  └─ useFocusEffect → fetchShoppingLists()
  └─ FlatList (stores)
       └─ StoreCard (collapsible)
            └─ ShoppingItem (swipe-to-remove)
                 ├─ Item name + quantity
                 ├─ Source indicator (capture/recipe)
                 └─ Swipe right → DELETE /api/shopping-lists/{store}/items/{id}
```

### Data Flow

```
StatusScreen
    │
    ├─ On focus: GET /api/shopping-lists
    │   Response: [
    │     { storeName: "Jewel", storeSlug: "jewel", items: [...] },
    │     { storeName: "CVS", storeSlug: "cvs", items: [...] },
    │   ]
    │
    ├─ On swipe-to-remove:
    │   DELETE /api/shopping-lists/{storeSlug}/items/{itemId}
    │   Optimistic UI: remove from local state immediately
    │   Rollback on failure
    │
    └─ On pull-to-refresh: re-fetch all lists
```

### Why REST Not SSE

The Status screen displays **already-processed** data. Unlike the Capture screen where agent processing happens in real-time and must stream events, shopping lists are written to Cosmos by the Admin Agent during capture and then read back as static data. There is no real-time processing to stream.

### No Push Notifications (v3.0)

Per PROJECT.md: "No push notifications this milestone -- pull-based UI." The Status screen uses pull-to-refresh. Push notifications are deferred to v3.1+.

---

## Question 4: YouTube Transcript Fetching -- Where Does It Happen?

### Recommended: Agent @tool Function (Not Backend Service)

YouTube transcript extraction should be an `@tool` function on the Admin Agent, not a separate backend service. The reasoning:

1. **The Admin Agent decides when to extract** -- when it receives a YouTube URL as captured text, it calls `extract_recipe_ingredients` to get the transcript and parse ingredients
2. **The agent interprets the transcript** -- GPT-4o is excellent at extracting structured ingredient lists from unstructured transcript text
3. **The tool is simple** -- `youtube-transcript-api` is a lightweight library (~5 lines of code to get a transcript), wrapped in `asyncio.to_thread()` for async safety
4. **Follows the existing pattern** -- `transcribe_audio` is already a @tool on the Classifier; `extract_recipe_ingredients` follows the same class-based tool pattern

### Implementation: Two-Step Tool Chain

The Admin Agent's instructions (in Foundry portal) tell it to:
1. If the text contains a YouTube URL, call `fetch_youtube_transcript` first
2. Read the transcript, extract ingredients and quantities
3. Call `add_shopping_list_items` to file them to the correct stores

This mirrors how the Classifier uses `transcribe_audio` then `file_capture` -- two @tool calls in sequence, orchestrated by the agent's reasoning.

### Tool Definitions

```python
class AdminTools:
    """Tools for the Admin Agent, bound to CosmosManager."""

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        self._manager = cosmos_manager

    @tool(approval_mode="never_require")
    async def fetch_youtube_transcript(
        self,
        url: Annotated[str, Field(description="YouTube video URL")],
    ) -> str:
        """Fetch the transcript of a YouTube video.

        Returns the full transcript text. The agent should parse this
        to extract recipe ingredients and quantities, then call
        add_shopping_list_items to file them.
        """
        video_id = _extract_video_id(url)
        if not video_id:
            return "Error: Could not extract video ID from URL"

        transcript_entries = await asyncio.to_thread(
            YouTubeTranscriptApi.get_transcript, video_id
        )
        full_text = " ".join(entry["text"] for entry in transcript_entries)
        return full_text

    @tool(approval_mode="never_require")
    async def add_shopping_list_items(
        self,
        items: Annotated[
            list[dict],
            Field(description=(
                "List of items to add. Each item: "
                '{"name": "...", "quantity": "...", "store": "..."}'
            )),
        ],
        source_inbox_id: Annotated[
            str | None,
            Field(description="Inbox item ID this came from"),
        ] = None,
        source_recipe_url: Annotated[
            str | None,
            Field(description="YouTube URL if items are from a recipe"),
        ] = None,
    ) -> dict:
        """Add items to store-based shopping lists.

        Items are grouped by store and added to the appropriate
        ShoppingList document in Cosmos DB. Creates the list document
        if it doesn't exist for that store yet.
        """
        # Group items by store, upsert to Cosmos
        ...
```

### Why @tool Not Backend Service

| Approach | Pros | Cons |
|----------|------|------|
| **Agent @tool (recommended)** | Agent orchestrates the full flow, interprets transcript with GPT-4o reasoning, follows existing pattern | youtube-transcript-api is blocking (needs asyncio.to_thread) |
| Backend service endpoint | Clean separation | Requires new endpoint, loses agent reasoning context, agent can't interpret transcript in-context |
| Pre-process before agent | Simplest backend code | Agent can't decide when to fetch, breaks agent autonomy |

The `asyncio.to_thread()` wrapper for the blocking `youtube-transcript-api` library is the standard pattern for using sync libraries in FastAPI/async contexts. It runs the blocking call in a thread pool, preventing event loop starvation.

### YouTube Transcript Library

**Use `youtube-transcript-api`** (PyPI, latest v1.2.4, Jan 2026):
- No API key required
- No headless browser
- Fetches auto-generated or manual captions
- Lightweight dependency
- Well-maintained (active in 2025-2026)

**Confidence: HIGH** -- this is the de facto standard for YouTube transcript extraction in Python. Verified on PyPI and GitHub.

---

## Complete System Architecture: After v3.0

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Mobile App (Expo)                                  │
│                                                                            │
│   Capture Screen ──────────────── AG-UI SSE Client                        │
│   Inbox Screen ────────────────── REST API (GET/DELETE/PATCH)             │
│   Status Screen (NEW) ─────────── REST API (GET/DELETE)                   │
│         │                    │  ▲                                          │
└─────────┼────────────────────┼──┼──────────────────────────────────────────┘
          │                    ▼  │
     ┌────────────────────────────────────────────────────────────────────┐
     │               FastAPI (Azure Container Apps)                       │
     │                                                                    │
     │   POST /api/capture ──────────► stream_text_capture()              │
     │   POST /api/capture/voice ────► stream_voice_capture()             │
     │   POST /api/capture/follow-up ► stream_follow_up_capture()         │
     │                                                                    │
     │   GET  /api/inbox ────────────► Cosmos query                       │
     │   DELETE /api/inbox/{id} ─────► cascade delete                     │
     │   PATCH /api/inbox/{id}/recat ► cross-container move               │
     │                                                                    │
     │   GET  /api/shopping-lists ──────────► Cosmos query (NEW)          │
     │   DELETE /api/shopping-lists/.../{id} ► array item remove (NEW)    │
     │                                                                    │
     │   ┌── Lifespan ──────────────────────────────────────────────┐     │
     │   │                                                          │     │
     │   │  AzureAIAgentClient (probe, connectivity check)          │     │
     │   │                                                          │     │
     │   │  Classifier Client (AzureAIAgentClient)                  │     │
     │   │    agent_id: AZURE_AI_CLASSIFIER_AGENT_ID                │     │
     │   │    tools: [file_capture, transcribe_audio]               │     │
     │   │    middleware: [AuditAgentMiddleware, ToolTimingMiddleware]│     │
     │   │                                                          │     │
     │   │  Admin Client (AzureAIAgentClient) ◄── NEW              │     │
     │   │    agent_id: AZURE_AI_ADMIN_AGENT_ID                    │     │
     │   │    tools: [add_shopping_list_items,                      │     │
     │   │            fetch_youtube_transcript]                     │     │
     │   │    middleware: [AuditAgentMiddleware, ToolTimingMiddleware]│     │
     │   │                                                          │     │
     │   │  ClassifierTools (→ Cosmos: Inbox, Buckets)              │     │
     │   │  AdminTools (→ Cosmos: ShoppingLists) ◄── NEW           │     │
     │   │  TranscriptionTools (→ Blob Storage + OpenAI)            │     │
     │   │                                                          │     │
     │   │  CosmosManager (6 containers)                            │     │
     │   │    Inbox | People | Projects | Ideas | Admin             │     │
     │   │    ShoppingLists ◄── NEW                                 │     │
     │   │                                                          │     │
     │   └──────────────────────────────────────────────────────────┘     │
     └────────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

### New Components (v3.0)

| Component | File | Responsibility | Communicates With |
|-----------|------|----------------|-------------------|
| `AdminTools` | `tools/admin.py` | @tool functions for shopping list CRUD + YouTube transcript | CosmosManager (ShoppingLists container) |
| `ensure_admin_agent()` | `agents/admin.py` | Self-healing Admin Agent registration | Foundry Agent Service |
| `ShoppingListDocument` / `ShoppingItem` | `models/documents.py` | Pydantic schemas for shopping list data | AdminTools, shopping_lists API |
| `shopping_lists` router | `api/shopping_lists.py` | REST endpoints for Status screen | CosmosManager (ShoppingLists container) |
| `stream_admin_enrichment()` | `streaming/adapter.py` | SSE streaming for Admin Agent phase | Admin AzureAIAgentClient |
| `StatusScreen` | `mobile/app/(tabs)/status.tsx` | Shopping list display with swipe-to-remove | REST API (/api/shopping-lists) |

### Modified Components (v3.0)

| Component | File | Change |
|-----------|------|--------|
| `CosmosManager` | `db/cosmos.py` | Add `"ShoppingLists"` to `CONTAINER_NAMES` |
| `config.py` | `config.py` | Add `azure_ai_admin_agent_id: str = ""` |
| `main.py` lifespan | `main.py` | Initialize Admin Agent client, AdminTools, register in app.state |
| `stream_text_capture()` | `streaming/adapter.py` | After CLASSIFIED with bucket="Admin", call `stream_admin_enrichment()` |
| `stream_voice_capture()` | `streaming/adapter.py` | Same conditional Admin Agent routing |
| Tab layout | `mobile/app/(tabs)/_layout.tsx` | Add Status tab |
| SSE events | `streaming/sse.py` | Add `admin_enriched_event()` |
| AG-UI types | `mobile/lib/types.ts` | Add `ADMIN_ENRICHED` event type |

### Unchanged Components

| Component | Why Unchanged |
|-----------|---------------|
| `ClassifierTools` | Classifier still files to Admin bucket as before |
| `ensure_classifier_agent()` | Classifier agent unchanged |
| Classifier instructions | No change needed -- still classifies into Admin bucket |
| `api/inbox.py` | Inbox CRUD unaffected by shopping lists |
| `api/capture.py` | Endpoint handlers unchanged -- routing happens in adapter |
| `tools/transcription.py` | Voice transcription unchanged |
| `tools/cosmos_crud.py` | Generic CRUD tools unchanged |

---

## Data Flow: Ad Hoc Item Capture

```
User says: "Need cat litter"
    │
    ▼
POST /api/capture { text: "Need cat litter" }
    │
    ▼
stream_text_capture()
    │
    ├─ Phase 1: Classifier Agent
    │   Agent reasons: "This is a household supply need → Admin"
    │   Agent calls: file_capture(
    │       text="Need cat litter",
    │       bucket="Admin",
    │       confidence=0.88,
    │       status="classified",
    │       title="Cat litter"
    │   )
    │   Result: Inbox doc created, Admin doc created
    │
    ├─ SSE: CLASSIFIED { inboxItemId, bucket: "Admin", confidence: 0.88 }
    │   (mobile shows "Filed -> Admin (0.88)" toast immediately)
    │
    ├─ Phase 2: Admin Agent enrichment
    │   SSE: STEP_START { stepName: "Processing Admin" }
    │   Admin Agent receives: "Need cat litter"
    │   Admin Agent reasons: "Cat litter → pet store"
    │   Admin Agent calls: add_shopping_list_items([
    │       { name: "Cat litter", quantity: "1", store: "Pet Store" }
    │   ], source_inbox_id="inbox-uuid")
    │   Result: ShoppingLists/list-pet-store updated
    │   SSE: ADMIN_ENRICHED { stores: ["Pet Store"], itemCount: 1 }
    │   SSE: STEP_END { stepName: "Processing Admin" }
    │
    └─ SSE: COMPLETE

Total SSE sequence:
  STEP_START("Classifying")
  STEP_END("Classifying")
  CLASSIFIED(...)
  STEP_START("Processing Admin")
  STEP_END("Processing Admin")
  ADMIN_ENRICHED(...)
  COMPLETE
```

## Data Flow: YouTube Recipe Capture

```
User says: "Make this recipe https://youtube.com/watch?v=abc123"
    │
    ▼
POST /api/capture { text: "Make this recipe https://youtube.com/watch?v=abc123" }
    │
    ▼
stream_text_capture()
    │
    ├─ Phase 1: Classifier Agent
    │   Agent reasons: "Recipe link, household task → Admin"
    │   Agent calls: file_capture(bucket="Admin", ...)
    │
    ├─ SSE: CLASSIFIED
    │
    ├─ Phase 2: Admin Agent enrichment
    │   Admin Agent receives text with YouTube URL
    │   Admin Agent calls: fetch_youtube_transcript(url="https://youtube.com/...")
    │   Tool returns: "...today we're making chicken parmesan. You'll need
    │                  2 pounds of chicken breast, a cup of breadcrumbs,
    │                  marinara sauce, mozzarella cheese..."
    │   Admin Agent reasons over transcript, extracts ingredients:
    │     - Chicken breast 2 lbs → Jewel
    │     - Breadcrumbs 1 cup → Jewel
    │     - Marinara sauce → Jewel
    │     - Mozzarella cheese → Jewel
    │   Admin Agent calls: add_shopping_list_items([
    │       { name: "Chicken breast", quantity: "2 lbs", store: "Jewel" },
    │       { name: "Breadcrumbs", quantity: "1 cup", store: "Jewel" },
    │       { name: "Marinara sauce", quantity: "1 jar", store: "Jewel" },
    │       { name: "Mozzarella cheese", quantity: "1 package", store: "Jewel" },
    │   ], source_recipe_url="https://youtube.com/...")
    │
    └─ SSE: ADMIN_ENRICHED { stores: ["Jewel"], itemCount: 4 }
```

---

## Admin Agent Instructions (Foundry Portal)

The Admin Agent's instructions in the Foundry portal should include:

1. **Store routing rules** -- a mapping of item categories to stores:
   - Groceries/food → Jewel
   - Pharmacy/health → CVS
   - Pet supplies → Pet Store
   - General household → Target
   - (Will can customize these in the portal without code changes)

2. **YouTube recipe handling** -- when text contains a YouTube URL:
   - Call `fetch_youtube_transcript` to get the video transcript
   - Parse the transcript for ingredients and quantities
   - Route all food ingredients to the grocery store (Jewel)

3. **Item normalization** -- the agent should:
   - Clean up item names ("cat litter" not "I need some cat litter")
   - Extract quantities when mentioned ("2 lbs chicken" → name: "Chicken", quantity: "2 lbs")
   - Use sensible defaults when quantity is not specified

These instructions live in the Foundry portal and are editable without code deployment, following the same pattern as the Classifier agent.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Agent-as-Database
**What:** Having the Admin Agent query Cosmos to check if items already exist before adding
**Why bad:** Adds complexity, latency, and failure modes. The agent is for reasoning about categorization, not data management.
**Instead:** Accept duplicates at write time. The user can remove items from the Status screen. Dedup logic (if ever needed) belongs in the tool, not the agent.

### Anti-Pattern 2: Returning Shopping List State in SSE
**What:** Streaming the full shopping list contents back through SSE events after enrichment
**Why bad:** The Status screen fetches lists via REST. Duplicating the data through SSE creates two sources of truth and SSE payload bloat.
**Instead:** The `ADMIN_ENRICHED` event is a notification ("items were added to these stores"), not a data payload. The Status screen fetches fresh data on focus.

### Anti-Pattern 3: Shared Foundry Thread Between Classifier and Admin Agent
**What:** Running both agents on the same Foundry thread/conversation
**Why bad:** The agents have different instructions, tools, and purposes. A shared thread pollutes context and causes confusion.
**Instead:** Each agent gets its own thread. The Admin Agent's thread is ephemeral (one-shot enrichment), not persisted for follow-up.

### Anti-Pattern 4: Making the Admin Agent a Connected Agent of the Classifier
**What:** Registering Admin as a connected agent callable by the Classifier
**Why bad:** Connected Agents cannot call local @tool functions. The Admin Agent needs `add_shopping_list_items` which writes to Cosmos locally.
**Instead:** Code-based routing in FastAPI. Classifier runs, code inspects result, code invokes Admin Agent separately.

---

## Patterns to Follow

### Pattern 1: Class-Based Tool Binding
**What:** `AdminTools(cosmos_manager)` binds Cosmos references to @tool functions via `self`
**When:** Any tool that needs stateful references (DB clients, API clients)
**Source:** Existing `ClassifierTools` and `TranscriptionTools` patterns

### Pattern 2: Self-Healing Agent Registration
**What:** `ensure_admin_agent()` checks stored agent ID, creates new agent if missing
**When:** Startup (lifespan)
**Source:** Existing `ensure_classifier_agent()` pattern

### Pattern 3: Separate AzureAIAgentClient Per Agent
**What:** Create a distinct `AzureAIAgentClient` instance for each agent with its own `agent_id` and middleware
**When:** Each persistent agent needs its own client
**Source:** Existing `classifier_client` in main.py lifespan

### Pattern 4: Optimistic UI with Rollback
**What:** Remove item from local state immediately on swipe, rollback if DELETE fails
**When:** Shopping list item removal
**Source:** Existing Inbox delete pattern

---

## Scalability Considerations

| Concern | Current (single user) | If Multi-User (future) |
|---------|----------------------|------------------------|
| Shopping list size | Embedded array in single doc (~50 items max) | Split to items-as-documents with composite partition key |
| YouTube transcript length | Full text sent to agent (~10K tokens for 30min video) | Summarize before sending to agent to reduce token cost |
| Agent latency | 2x for Admin captures (acceptable for capture-and-forget) | Consider async processing with webhook callback |
| Cosmos RUs | Free tier sufficient | Autoscale provisioned throughput |

---

## Build Order (Dependency-Driven)

The following build order respects component dependencies:

### Phase 1: Data Foundation
1. `ShoppingListDocument` / `ShoppingItem` Pydantic models
2. Add `"ShoppingLists"` to CosmosManager
3. Create ShoppingLists container in Cosmos DB (Azure portal or script)
4. `AdminTools` class with `add_shopping_list_items` (Cosmos writes)

**Why first:** Everything depends on the data layer. Without models and tools, neither the agent nor the API can function.

### Phase 2: Admin Agent Registration
5. `ensure_admin_agent()` function (mirrors ensure_classifier_agent)
6. `config.py`: add `azure_ai_admin_agent_id`
7. `main.py` lifespan: initialize Admin Agent client + AdminTools
8. Write Admin Agent instructions in Foundry portal

**Why second:** The agent must exist before it can be invoked. Instructions determine behavior.

### Phase 3: Capture Pipeline Integration
9. `stream_admin_enrichment()` in adapter.py
10. Extend `stream_text_capture()` with Admin routing
11. Extend `stream_voice_capture()` with Admin routing
12. New SSE events: `admin_enriched_event()`
13. Mobile: handle `ADMIN_ENRICHED` event type

**Why third:** Depends on Phase 2 (agent exists) and Phase 1 (tools write to Cosmos).

### Phase 4: Shopping List API + Status Screen
14. `api/shopping_lists.py` REST endpoints
15. Mobile: `StatusScreen` component
16. Mobile: Tab layout update
17. Mobile: Swipe-to-remove interaction

**Why fourth:** The Status screen reads data written by Phase 3. It can be built in parallel with Phase 3 since the API reads from Cosmos directly.

### Phase 5: YouTube Recipe Integration
18. `fetch_youtube_transcript` @tool
19. Add `youtube-transcript-api` to backend dependencies
20. Update Admin Agent instructions for recipe handling
21. End-to-end testing with real YouTube recipe URLs

**Why last:** This is an enhancement to the Admin Agent flow. The core shopping list pipeline (ad hoc items) should work first. YouTube recipes add complexity (transcript fetching, ingredient parsing) that should be layered on after the base is solid.

---

## Sources

- [Azure AI Agent Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) -- Microsoft Architecture Center, updated 2026-02-12 (HIGH confidence)
- [Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview) -- Microsoft Learn (HIGH confidence)
- [HandoffBuilder + Foundry v2 payload errors](https://github.com/microsoft/agent-framework/issues/3097) -- GitHub issue, confirms HandoffBuilder bugs with AzureAIClient (HIGH confidence)
- [youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/) -- PyPI, v1.2.4, Jan 2026 (HIGH confidence)
- [youtube-transcript-api GitHub](https://github.com/jdepoix/youtube-transcript-api) -- source code, async usage patterns (HIGH confidence)
- Existing codebase: `backend/src/second_brain/` -- all current patterns verified by reading source (HIGH confidence)
