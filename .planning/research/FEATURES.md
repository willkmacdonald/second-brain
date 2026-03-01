# Feature Landscape: v3.0 Admin Agent & Shopping Lists

**Domain:** Store-based shopping lists, YouTube recipe ingredient extraction, multi-agent handoff
**Researched:** 2026-03-01
**Overall confidence:** MEDIUM-HIGH (domain well-understood, some implementation details need phase-specific research)

---

## Context: What Exists Today

The Second Brain app captures fleeting thoughts via voice or text, classifies them into People/Projects/Ideas/Admin via a persistent Classifier agent on Foundry Agent Service, files to Cosmos DB, and streams real-time feedback via AG-UI SSE. The mobile Expo app has two tabs: Capture and Inbox.

v3.0 adds the first specialist agent (Admin Agent) with store-based shopping lists as the initial capability. This is NOT a general-purpose shopping list app -- it is a capture-first system where items enter through the existing capture pipeline and get enriched by the Admin Agent.

---

## Table Stakes

Features users expect from a personal shopping list with agent-driven routing. Missing any of these means the milestone feels incomplete.

### TS-1: Classifier to Admin Agent Inline Handoff

| Attribute | Detail |
|-----------|--------|
| **Why expected** | Core premise of v3.0 -- the Classifier already routes to "Admin" bucket; now Admin captures need further processing |
| **Complexity** | Medium |
| **Dependencies** | Existing Classifier agent, Foundry Agent Service, capture flow |
| **Notes** | Two approaches exist: (A) Foundry Connected Agents -- CANNOT use local `@tool` functions, requires Azure Functions or OpenAPI tools; (B) Code-based routing in FastAPI -- detect Classifier outcome = "Admin", then invoke Admin Agent with the captured text. Approach B matches the existing architecture and avoids Connected Agents limitation. The Classifier already calls `file_capture` with `bucket="Admin"` -- the handoff point is AFTER classification in the adapter layer. |

**Expected user behavior:** User captures "need cat litter" via voice or text. They see "Classifying..." then "Processing..." (two-step feedback). The capture gets classified as Admin, then the Admin Agent extracts the item and routes it to the pet store list. The user sees a success toast like "Added to Pet Store list."

**Implementation approach:** Code-based routing (not Connected Agents). The adapter detects `bucket == "Admin"` in the `file_capture` tool result, then makes a second agent call to the Admin Agent with the captured text and any context. This is a sequential two-agent pipeline within a single capture request.

### TS-2: Store-Based Shopping Lists in Cosmos DB

| Attribute | Detail |
|-----------|--------|
| **Why expected** | Core data structure -- items grouped by store (Jewel, CVS, Pet Store, etc.) |
| **Complexity** | Low-Medium |
| **Dependencies** | CosmosManager (existing), new container or partition strategy |
| **Notes** | Two data model options: (A) One `ShoppingLists` container with one doc per store list containing an items array; (B) One doc per item with a `store` field. Option A is better for this use case -- lists are small (10-30 items), always fetched per-store, and atomic updates on the list document avoid race conditions. Store names are agent-determined, not hardcoded. |

**Data model (recommended):**
```json
{
  "id": "jewel-osco",
  "userId": "will",
  "storeName": "Jewel-Osco",
  "storeCategory": "grocery",
  "items": [
    {
      "id": "uuid",
      "name": "Milk (2%)",
      "quantity": "1 gallon",
      "checked": false,
      "addedAt": "2026-03-01T...",
      "source": "ad-hoc",
      "sourceRecipeUrl": null
    }
  ],
  "updatedAt": "2026-03-01T...",
  "createdAt": "2026-03-01T..."
}
```

**Expected user behavior:** User opens the Status & Priorities tab and sees shopping lists grouped by store. Each store is a collapsible section showing its items. Items can be checked off (strikethrough) or swiped to delete.

### TS-3: Agent-Driven Store Routing

| Attribute | Detail |
|-----------|--------|
| **Why expected** | "Need cat litter" should automatically go to the pet store list without the user specifying which store |
| **Complexity** | Low |
| **Dependencies** | Admin Agent instructions, `add_shopping_list_items` tool |
| **Notes** | This is entirely agent instruction quality, not code. The Admin Agent's system prompt includes a store mapping: "Jewel-Osco: groceries, produce, dairy, meat, bakery; CVS: pharmacy, toiletries, first aid; Pet Supplies Plus: cat litter, dog food, pet toys." The agent decides the store based on the item description. New stores can be added by updating agent instructions in the Foundry portal -- no code deployment needed. |

**Expected user behavior:** User says "grab some ibuprofen." Admin Agent routes to CVS list. User says "we need chicken breast and broccoli." Admin Agent routes to Jewel-Osco list. If the agent is unsure about the store, it should create a "General" list as a fallback rather than failing.

### TS-4: Ad Hoc Item Capture to Correct Store

| Attribute | Detail |
|-----------|--------|
| **Why expected** | Most common use case -- quick "need X" captures throughout the day |
| **Complexity** | Low |
| **Dependencies** | TS-1 (handoff), TS-2 (data model), TS-3 (routing) |
| **Notes** | This is the happy path: capture -> Classifier -> Admin -> add_items tool -> Cosmos. The item text needs parsing by the agent to extract item name, optional quantity, and store. Natural language understanding by GPT-4o handles this well: "grab 2 pounds of ground beef" -> name: "Ground beef", quantity: "2 lbs", store: "Jewel-Osco". |

**Expected user behavior:** Quick capture flow. User taps record, says "need cat litter and paper towels." Admin Agent splits into two items: cat litter -> Pet Store, paper towels -> Jewel-Osco (or CVS, depending on agent judgment). User sees confirmation toast.

### TS-5: YouTube Recipe URL to Ingredient Extraction

| Attribute | Detail |
|-----------|--------|
| **Why expected** | Explicitly listed as a target feature in PROJECT.md; primary differentiator |
| **Complexity** | Medium-High |
| **Dependencies** | `youtube-transcript-api` Python package, Admin Agent, add_shopping_list_items tool |
| **Notes** | The pipeline is: (1) User pastes/says a YouTube URL, (2) Classifier routes to Admin, (3) Admin Agent calls `extract_recipe_ingredients` tool, (4) Tool fetches transcript via `youtube-transcript-api`, (5) Agent parses transcript for ingredients, (6) Agent calls `add_shopping_list_items` with extracted items. **Critical detail:** `youtube-transcript-api` (v1.2.4, Jan 2026) uses an undocumented YouTube API -- it may break without warning. Auto-generated subtitles are supported but quality varies. Not all YouTube videos have subtitles. The agent prompt needs to handle "no transcript available" gracefully. |

**YouTube transcript approach (recommended over alternatives):**
- `youtube-transcript-api` is lightweight (no headless browser), Python-native, handles auto-generated captions
- Alternative: `recipe-scrapers` (611 cooking websites supported) -- useful if the URL is a recipe website, not YouTube
- Alternative: YouTube Data API -- requires API key, quota limits, only returns metadata not transcript
- **Decision:** Use `youtube-transcript-api` for YouTube URLs. Consider adding `recipe-scrapers` support for non-YouTube recipe URLs as a future enhancement.

**Expected user behavior:** User pastes "https://www.youtube.com/watch?v=xyz123" in text capture or says "make the shopping list from this recipe" and gives the URL. They see "Classifying... Extracting recipe..." (extended processing stages). The agent extracts ingredients like "2 cups flour, 1 cup sugar, 3 eggs" and adds them to the grocery store list. Items include source attribution (`sourceRecipeUrl`). User sees "Added 8 items to Jewel-Osco from [recipe name]."

**Failure modes to handle:**
- No transcript available -> Agent tells user "This video doesn't have subtitles. Try pasting the recipe text directly."
- Transcript is not a recipe -> Agent tells user "I couldn't find recipe ingredients in this video."
- Non-English transcript -> `youtube-transcript-api` supports translation, but quality may degrade

### TS-6: Status & Priorities Screen (Shopping Lists Tab)

| Attribute | Detail |
|-----------|--------|
| **Why expected** | Users need to see their shopping lists; new screen per PROJECT.md |
| **Complexity** | Medium |
| **Dependencies** | TS-2 (data model), new API endpoint, new Expo tab |
| **Notes** | Third tab in the mobile app. Shows store-grouped lists. Per-store sections are collapsible. Items show name, quantity, checked state. v3.0 shows ONLY shopping lists here -- other "Status & Priorities" content (task summaries, etc.) is deferred. The API endpoint is `GET /api/shopping-lists` returning all lists for userId "will". |

**Expected user behavior:** User taps the new "Lists" tab (third tab, between Inbox and a potential future tab). They see stores as sections (e.g., "Jewel-Osco (5 items)", "CVS (2 items)", "Pet Store (1 item)"). Tapping a store expands to show items. Checked items move to the bottom of the list with strikethrough styling. Empty stores are hidden.

### TS-7: Swipe-to-Remove on Shopping List Items

| Attribute | Detail |
|-----------|--------|
| **Why expected** | Standard mobile UX for list management; already in PROJECT.md requirements |
| **Complexity** | Low |
| **Dependencies** | TS-6 (screen), API endpoint for item removal |
| **Notes** | Matches the existing swipe-to-delete pattern on Inbox items. Use `react-native-gesture-handler` (likely already installed for Expo). The API endpoint is `DELETE /api/shopping-lists/{store_id}/items/{item_id}` or `PATCH` to mark items as checked. Swipe left = delete permanently. Tap = toggle checked. |

**Expected user behavior:** At the store, user taps items as they put them in the cart (toggles checked/strikethrough). When done shopping, they can swipe to delete checked items, or they accumulate and can be cleared with a "Clear checked" action. No confirmation dialog on swipe -- matches iOS conventions and existing inbox behavior.

---

## Differentiators

Features that elevate this beyond a basic shopping list into a capture-intelligence system.

### D-1: Voice Capture to Shopping List Items

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Say "I need cat litter and dog food" while driving and it files to the correct store lists |
| **Complexity** | Low (already exists) |
| **Dependencies** | Existing voice capture pipeline + TS-1 handoff |
| **Notes** | This is a zero-additional-work differentiator. Voice capture already transcribes and classifies. Once the Classifier -> Admin handoff exists, voice captures that classify as Admin automatically flow through. The differentiator is the *user experience* -- no other shopping list app lets you say unstructured natural language and have AI route items to the right store. |

### D-2: Multi-Store Splitting from Single Capture

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | "We need milk from Jewel and cat litter from the pet store" -> two different store lists updated in one capture |
| **Complexity** | Medium |
| **Dependencies** | TS-3 (store routing), Admin Agent tool design |
| **Notes** | The Admin Agent `add_shopping_list_items` tool should accept a list of `(item, store)` tuples, not just one store at a time. The agent's instructions tell it to split multi-store requests. This is primarily agent instruction quality -- the tool just needs to support multiple stores in one call. |

### D-3: Recipe Source Attribution on Items

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | Items extracted from a YouTube recipe show "(from: Pasta Carbonara)" so the user knows why an item is on their list |
| **Complexity** | Low |
| **Dependencies** | TS-5 (YouTube extraction), data model |
| **Notes** | The `sourceRecipeUrl` and optionally `sourceRecipeName` fields on the item model. When the Admin Agent extracts ingredients from a recipe, it includes the source. The mobile UI can show a small subtitle under the item name. |

### D-4: Real-Time Streaming Feedback During Admin Processing

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | User sees "Classifying... -> Routing to Admin... -> Extracting recipe... -> Adding to list..." instead of a blank spinner |
| **Complexity** | Low-Medium |
| **Dependencies** | Existing SSE infrastructure, adapter extension |
| **Notes** | Extend the existing STEP_START/STEP_END events. The two-agent pipeline (Classifier -> Admin) naturally produces two step brackets. The mobile app already handles step events. New event types may be needed: `SHOPPING_LIST_UPDATED` to trigger a list refresh. |

### D-5: Intelligent Quantity Parsing

| Attribute | Detail |
|-----------|--------|
| **Value proposition** | "Grab a couple pounds of chicken" -> quantity: "2 lbs" (not "a couple pounds") |
| **Complexity** | Low |
| **Dependencies** | Agent instructions |
| **Notes** | GPT-4o is good at normalizing quantities from natural language. The agent instructions should specify: "Normalize quantities to standard units (lbs, oz, cups, each). If no quantity specified, omit the quantity field." This is purely instruction tuning, no code needed. |

---

## Anti-Features

Features to explicitly NOT build in v3.0. Each has a clear rationale.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Push notifications for list updates** | Deferred to v3.1+ per PROJECT.md; pull-based UI sufficient for single user | User opens Lists tab to see current state |
| **Location-aware store reminders** | Expo managed workflow limitations; complex geofencing | Deferred to v3.1+; "time-window heuristic" covers 80% of value per PROJECT.md |
| **Price comparison / coupons** | Scope creep; no integration with store APIs | Out of scope entirely |
| **Shared/collaborative lists** | Single-user system (userId: "will") | Hardcode userId |
| **Barcode scanning** | Requires camera integration, scope creep | Text/voice capture only |
| **Meal planning / recipe storage** | Different product category; capture system, not meal planner | Extract ingredients only, do NOT store full recipes |
| **Auto-ordering (Chewy.com, etc.)** | Future feature requiring computer use; extreme complexity | Deferred to v3.1+ per PROJECT.md |
| **Pantry/inventory management** | Different product; shopping lists are capture-based, not inventory tracking | Keep lists as simple item checklists |
| **Connected Agents pattern (Foundry)** | Connected Agents CANNOT call local `@tool` functions; would require migrating tools to Azure Functions or OpenAPI | Code-based routing in FastAPI (existing pattern) |
| **Recipe website scraping** | `recipe-scrapers` supports 611 sites but adds scope; YouTube is the stated requirement | Start with YouTube only; consider recipe-scrapers as v3.1+ enhancement |
| **Item deduplication / merge** | "Milk" added twice should show as "Milk (2)" -- nice but complex; edge cases with quantities | Defer; allow duplicates for now, user can manually delete |
| **Store layout optimization** | Sorting items by aisle within a store | Defer; sort alphabetically or by addition order |
| **Check-off history / analytics** | "You bought milk 3 times this month" | Defer; out of scope for capture system |
| **Offline support** | Already out of scope per PROJECT.md constraints | Requires connectivity |

---

## Feature Dependencies

```
                     Existing System
                          |
              Classifier Agent (exists)
                          |
                    file_capture tool detects bucket == "Admin"
                          |
              +-----------+-----------+
              |                       |
    Admin Agent registration    ShoppingLists container
    (ensure_admin_agent)         (Cosmos DB data model)
              |                       |
    Admin Agent tools                 |
    (add_items, extract_recipe)       |
              |                       |
              +-----------+-----------+
                          |
                   Capture flow integration
                   (adapter detects Admin, invokes Admin Agent)
                          |
              +-----------+-----------+
              |                       |
    GET /api/shopping-lists      PATCH/DELETE item endpoints
              |                       |
    Status & Priorities screen   Swipe-to-remove + check-off
              |
    youtube-transcript-api
    (extract_recipe_ingredients tool)
```

**Critical path:** Admin Agent registration -> add_items tool -> capture flow handoff -> API endpoint -> mobile screen. YouTube extraction is parallelizable after the add_items tool exists.

---

## Expected User Behaviors & Scenarios

### Scenario 1: Quick Ad Hoc Item (most common, ~70% of usage)
1. User opens app (lands on Capture, voice mode default)
2. Taps record: "Need cat litter and milk"
3. Sees "Classifying..." then "Processing..."
4. Gets toast: "Added: Cat litter -> Pet Store, Milk -> Jewel-Osco"
5. Total time: ~5 seconds

### Scenario 2: Recipe Extraction (weekly, ~15% of usage)
1. User finds a YouTube cooking video
2. Switches to text mode, pastes URL
3. Sees "Classifying... Extracting recipe..."
4. Gets toast: "Added 12 items to Jewel-Osco from Pasta Carbonara"
5. Total time: ~10-15 seconds (transcript fetch + agent reasoning)

### Scenario 3: At the Store (consumption, ~10% of usage)
1. User opens Lists tab
2. Taps "Jewel-Osco" to expand
3. Taps items as they shop (checked/strikethrough)
4. Swipes to delete items they decided to skip
5. When done, all checked items remain as history or get cleared

### Scenario 4: Multi-Store Planning (weekly, ~5% of usage)
1. User captures: "For the weekend I need ground beef and buns from Jewel, cat treats from the pet store, and band-aids from CVS"
2. Admin Agent splits into three store lists
3. User sees: "Added 2 items to Jewel-Osco, 1 to Pet Store, 1 to CVS"

---

## MVP Recommendation

Prioritize features in this order, based on dependency chain and user impact:

### Phase 1: Foundation (must ship together)
1. **Admin Agent registration** (`ensure_admin_agent()`) -- mirrors Classifier pattern
2. **ShoppingLists Cosmos container + Pydantic models** -- data foundation
3. **`add_shopping_list_items` @tool** -- Admin Agent can write to Cosmos
4. **Classifier -> Admin handoff in capture adapter** -- end-to-end pipeline

### Phase 2: Visibility (must ship together)
5. **`GET /api/shopping-lists` endpoint** -- mobile can fetch data
6. **Status & Priorities screen** -- third tab in Expo app
7. **Item check-off (tap to toggle)** -- basic list interaction

### Phase 3: Management
8. **Swipe-to-remove on items** -- matches existing inbox UX
9. **`DELETE /api/shopping-lists/{store}/items/{item}` endpoint**

### Phase 4: Enrichment
10. **`extract_recipe_ingredients` @tool** -- YouTube transcript -> ingredients
11. **`youtube-transcript-api` integration** -- transcript fetching
12. **Recipe source attribution on items** -- UI shows where items came from

### Defer (even within v3.0):
- **Multi-store splitting from single capture** -- This is agent instruction quality, not code. Get single-store routing working first, then tune instructions.
- **Intelligent quantity normalization** -- Let agent handle naturally; tune later based on observed behavior.

---

## Competitive Landscape (for context, not competition)

This is NOT competing with AnyList/OurGroceries/Listonic. Those are list-management apps. Second Brain is a capture-intelligence system where shopping lists are one output of the agent pipeline. The key differentiators vs. traditional shopping list apps:

| Capability | AnyList/OurGroceries | Second Brain v3.0 |
|------------|---------------------|-------------------|
| Manual item entry | Yes (primary input) | Yes (but secondary to voice/text capture) |
| Voice input | Limited (Siri shortcut) | Native voice capture with transcription |
| Store routing | Manual (user assigns store) | Agent-driven (automatic based on item) |
| Recipe import | URL scraping (structured recipe pages) | YouTube transcript extraction (unstructured video) |
| Aisle sorting | Yes (AnyList premium) | No (deferred) |
| Sharing | Yes (household sync) | No (single user) |
| NLP understanding | None | GPT-4o powers all routing and extraction |
| Capture friction | Open app -> navigate -> type -> assign | Open app -> speak -> done |

**The moat is capture speed and intelligence, not list features.**

---

## Sources

- AnyList features: [anylist.com/features](https://www.anylist.com/features) -- MEDIUM confidence
- AnyList vs OurGroceries: [daeken.com comparison](https://www.daeken.com/blog/anylist-vs-ourgroceries-app/) -- MEDIUM confidence
- youtube-transcript-api: [PyPI](https://pypi.org/project/youtube-transcript-api/) v1.2.4, Jan 2026 -- HIGH confidence
- recipe-scrapers: [GitHub](https://github.com/hhursev/recipe-scrapers), 611 sites supported -- HIGH confidence
- Foundry Connected Agents: [Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) -- HIGH confidence (confirms local @tool limitation)
- Agent Framework HandoffBuilder: [Microsoft Learn](https://learn.microsoft.com/en-us/agent-framework/user-guide/workflows/orchestrations/handoff) -- HIGH confidence
- Swipe-to-delete UX: [Nielsen Norman Group](https://www.nngroup.com/articles/contextual-swipe/) -- HIGH confidence
- LLM recipe extraction: [Krasimir Bambalov on Medium](https://medium.com/@kbambalov/building-a-nutritional-co-pilot-using-llms-part-1-recipe-extraction-e112645ef9fd) -- MEDIUM confidence
- Shopping list app landscape: [NerdWallet 2025](https://www.nerdwallet.com/finance/learn/best-grocery-list-apps) -- MEDIUM confidence
