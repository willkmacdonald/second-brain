# Stack Research: v3.0 Admin Agent & Shopping Lists

**Domain:** Multi-agent personal capture system -- adding first specialist agent
**Project:** Active Second Brain -- v3.0 Admin Agent & Shopping Lists
**Researched:** 2026-03-01
**Confidence:** HIGH for all recommendations (official docs, PyPI, existing codebase patterns verified)

---

## Context: What This Covers

This document covers **only new or changed** stack elements for the v3.0 milestone. Four new capability areas are addressed:

1. **Admin Agent (second persistent Foundry agent)** -- same pattern as Classifier, no new packages
2. **YouTube transcript extraction** -- `youtube-transcript-api` for fetching captions
3. **Shopping list data model** -- new Cosmos DB container, Pydantic models
4. **"Status & Priorities" mobile screen** -- new tab in expo-router, no new mobile packages

The existing validated stack is **unchanged**:
- `agent-framework-azure-ai` 1.0.0rc2 (AzureAIAgentClient)
- `agent-framework-core` 1.0.0rc2 (@tool, middleware, ChatOptions)
- FastAPI + uvicorn (backend)
- `azure-cosmos` (Cosmos DB)
- Expo 54 + expo-router 6 + react-native-sse (mobile)
- Azure Container Apps + GitHub Actions CI/CD
- Application Insights + OTel

---

## New Package: Backend

### youtube-transcript-api

| Attribute | Value |
|-----------|-------|
| **Package** | `youtube-transcript-api` |
| **Version** | `1.2.4` |
| **Released** | 2026-01-29 |
| **Python** | >=3.8, <3.15 |
| **License** | MIT |
| **Confidence** | HIGH (verified on PyPI, GitHub) |

**Why this library:** Extracts YouTube video transcripts without requiring a YouTube Data API key, OAuth, or headless browser. Uses an undocumented YouTube API endpoint to fetch captions (manual or auto-generated). This is the de facto standard for this task -- 3.8K+ GitHub stars, actively maintained, used by Microsoft's markitdown project.

**Why not alternatives:**
- **YouTube Data API v3**: Requires OAuth/API key setup, rate limits, caption download requires separate flow. Overkill for extracting text.
- **yt-dlp subtitle extraction**: Heavy dependency (full video downloader), slower, more complex API.
- **Paid transcript APIs (Supadata, AssemblyAI)**: Unnecessary cost and auth complexity when free library works.

**v1.x API (current -- breaking changes from 0.x):**

```python
from youtube_transcript_api import YouTubeTranscriptApi

ytt_api = YouTubeTranscriptApi()
transcript = ytt_api.fetch("dQw4w9WgXcQ", languages=["en"])

# FetchedTranscript is iterable -- each snippet has .text, .start, .duration
full_text = " ".join(snippet.text for snippet in transcript)
```

**Key v1.x changes from 0.x (do NOT use old API):**
- `YouTubeTranscriptApi.get_transcript()` (static) is **removed** -- use `ytt_api.fetch()`
- `YouTubeTranscriptApi.list_transcripts()` (static) is **removed** -- use `ytt_api.list()`
- Must instantiate `YouTubeTranscriptApi()` first (constructor accepts proxy config)

**Integration with Admin Agent:** The Admin Agent will have a `@tool` function `extract_recipe_from_youtube` that:
1. Parses YouTube URL to extract video ID
2. Calls `ytt_api.fetch(video_id)` to get transcript
3. Joins snippet text into a single string
4. Passes transcript to GPT-4o (via the agent's own reasoning) to extract structured ingredients
5. Calls `add_shopping_list_items` tool to file items to correct stores

**Risk:** Uses undocumented YouTube API. YouTube can change/block at any time. Mitigation: the library is actively maintained and adapts quickly to YouTube changes (multiple patches in 2025-2026). Acceptable risk for a personal project.

---

## No New Packages Required

### Second Persistent Foundry Agent (Admin Agent)

**No new backend packages needed.** The Admin Agent uses the exact same pattern as the Classifier agent already in production:

```python
# Existing pattern in main.py (line 104-128, 182-198):
# 1. Create AzureAIAgentClient with credential + project_endpoint
# 2. ensure_classifier_agent() validates/creates persistent agent
# 3. Create second AzureAIAgentClient with agent_id + middleware

# For Admin Agent -- exact same pattern:
admin_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=admin_agent_id,
    should_cleanup_agent=False,
    middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()],
)
```

**What changes in existing code:**

| File | Change | Impact |
|------|--------|--------|
| `config.py` | Add `azure_ai_admin_agent_id: str = ""` setting | Env var for Admin Agent ID |
| `agents/admin.py` | New file: `ensure_admin_agent()` (copy pattern from `classifier.py`) | Agent registration |
| `tools/admin.py` | New file: `AdminTools` class with shopping list @tool functions | Admin Agent tools |
| `main.py` lifespan | Add Admin Agent registration + client creation block | Startup init |
| `streaming/adapter.py` | Add `stream_admin_capture()` or adapt `_emit_result_event` for Admin outcomes | SSE streaming |
| `api/capture.py` | Add handoff logic: when Classifier classifies as Admin, invoke Admin Agent | Capture flow |
| Container Apps env | Add `AZURE_AI_ADMIN_AGENT_ID` env var | Deployment |

**AzureAIAgentClient constructor supports multiple instances** (verified from official docs):
- Each instance takes an `agent_id` pointing to a different persistent agent
- They share the same `credential` and `project_endpoint`
- `should_cleanup_agent=False` prevents deletion of persistent agents
- `middleware` list is per-client -- reuse the same `AuditAgentMiddleware` and `ToolTimingMiddleware` instances

### Classifier-to-Admin Handoff (Code-Based Routing)

**No Connected Agents, no HandoffBuilder, no new packages.** The handoff is pure FastAPI code-based routing -- the pattern already validated and documented as a key decision in PROJECT.md.

The flow:
1. Classifier classifies capture as "Admin" with `file_capture` tool
2. Capture endpoint detects `bucket == "Admin"` in the streamed `file_capture` result
3. FastAPI code invokes Admin Agent with the captured text + admin doc ID
4. Admin Agent calls its tools (`add_shopping_list_items`, `extract_recipe_from_youtube`)
5. SSE events from Admin Agent are streamed to the mobile app

**Why NOT Connected Agents:** Per PROJECT.md key decisions, Connected Agents require moving @tool functions to Azure Functions -- out of scope. Code-based routing is simpler, already proven, and gives full control over the handoff.

### Shopping List Data Model (Cosmos DB)

**No new Cosmos DB packages.** Uses existing `azure-cosmos` async client via `CosmosManager`.

**What changes:**

| Change | Detail |
|--------|--------|
| New container: `ShoppingLists` | Single container for all shopping list data, partitioned by `/userId` (consistent with all other containers) |
| `CONTAINER_NAMES` list in `cosmos.py` | Add `"ShoppingLists"` to the list |
| New Pydantic models in `models/documents.py` | `ShoppingListItem`, `ShoppingListDocument` |
| Create container in Cosmos DB | One-time Azure Portal or CLI operation |

**Data Model Design:**

```python
class ShoppingListItem(BaseModel):
    """Single item on a shopping list."""
    name: str                          # "cat litter", "chicken breast"
    quantity: str | None = None        # "2 lbs", "1 bag", "3"
    category: str | None = None       # "meat", "produce" (for within-store grouping)
    checked: bool = False              # Swipe-to-check on mobile
    sourceRecipeUrl: str | None = None # YouTube URL if from recipe extraction
    addedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))

class ShoppingListDocument(BaseDocument):
    """Shopping list for a specific store.

    One document per store (e.g., "Jewel", "CVS", "pet store").
    Items are embedded in the document -- no separate container for items.
    """
    storeName: str                     # "Jewel", "CVS", "Costco"
    items: list[ShoppingListItem] = Field(default_factory=list)
    # Inherits: id, userId, createdAt, updatedAt, rawText, classificationMeta
```

**Why embedded items (not separate documents):**
- Single-user system -- no concurrency concerns
- Shopping lists are small (10-50 items per store)
- Reads are always "give me the list for store X" -- single document read, no cross-partition query
- Removes or checks are patch operations on the same document
- Keeps Cosmos RU consumption minimal (1 RU per point read)

**Why `/userId` partition key (not `/storeName`):**
- Consistent with all 5 existing containers
- Single-user system -- all data under partition key `"will"`
- No hot partition risk (single user)
- Cross-store queries (show all lists) work within same partition

**Why single `ShoppingLists` container (not reusing `Admin`):**
- Shopping lists have different lifecycle than Admin captures (persistent lists vs one-time captures)
- `AdminDocument` has `rawText`/`classificationMeta` -- shopping lists don't need these fields
- Separating concerns makes the query model cleaner

### Mobile: Status & Priorities Screen

**No new mobile packages needed.** Uses existing expo-router tab layout pattern.

**What changes:**

| File | Change |
|------|--------|
| `mobile/app/(tabs)/status.tsx` | New file: Status & Priorities screen |
| `mobile/app/(tabs)/_layout.tsx` | Add third `Tabs.Screen` entry for "Status" |
| API calls | `GET /api/shopping-lists` -- new REST endpoint, standard `fetch()` |
| Swipe-to-remove | Reuse `react-native-gesture-handler` (already installed, v2.28.0) |

The existing tab layout in `_layout.tsx` uses the standard `Tabs` component from expo-router with `Tabs.Screen` entries. Adding a third tab is trivial -- no new dependencies, no layout changes.

---

## Recommended Stack (Complete for v3.0)

### Backend -- New Dependencies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `youtube-transcript-api` | `1.2.4` | YouTube transcript extraction | De facto standard, no API key needed, MIT license, actively maintained |

### Backend -- Existing (No Changes)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| `agent-framework-azure-ai` | `1.0.0rc2` | AzureAIAgentClient for Foundry | Already installed, unchanged |
| `agent-framework-core` | `1.0.0rc2` | @tool, middleware, ChatOptions | Already installed, unchanged |
| `azure-cosmos` | (current) | Cosmos DB async client | Already installed, add 1 container |
| `fastapi` | (current) | Web framework | Already installed, add new routes |
| `openai` | (current) | gpt-4o-transcribe | Already installed, unchanged |
| `pydantic-settings` | (current) | Config management | Already installed, add 1 setting |
| `azure-monitor-opentelemetry` | >=1.8.6 | Application Insights | Already installed, unchanged |

### Mobile -- No New Dependencies

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| `expo-router` | ~6.0.23 | Tab navigation | Already installed, add 1 tab |
| `react-native-gesture-handler` | ~2.28.0 | Swipe gestures | Already installed, reuse for swipe-to-remove |
| `react-native-sse` | ^1.2.1 | SSE streaming | Already installed, unchanged |

### Infrastructure -- Changes

| Resource | Change | Notes |
|----------|--------|-------|
| Cosmos DB | Add `ShoppingLists` container | Partition key `/userId`, create via Azure Portal/CLI |
| AI Foundry | Create Admin Agent | In AI Foundry portal, save agent ID to env var |
| Container Apps | Add `AZURE_AI_ADMIN_AGENT_ID` env var | Same deployment, just new config |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| YouTube transcripts | `youtube-transcript-api` | YouTube Data API v3 | OAuth/API key overhead, rate limits, more complex for simple transcript extraction |
| YouTube transcripts | `youtube-transcript-api` | `yt-dlp` | Massive dependency (video downloader), slower, overkill for captions |
| Agent handoff | Code-based FastAPI routing | Connected Agents (Foundry) | Requires Azure Functions for @tool execution -- out of scope per PROJECT.md |
| Agent handoff | Code-based FastAPI routing | HandoffBuilder | Was replaced in v2.0 -- incompatible with AzureAIAgentClient |
| Shopping list storage | Embedded items in store document | Separate items container | Over-engineering for single-user; embedded items = 1 RU reads, simpler queries |
| Shopping list storage | New `ShoppingLists` container | Reuse `Admin` container | Different lifecycle, different schema, cleaner separation |
| Recipe extraction | Agent reasoning + transcript text | Dedicated recipe extraction library | No good Python library for this; GPT-4o reasoning on transcript text is more flexible and accurate |

---

## Installation

```bash
# Single new dependency
cd backend
uv pip install youtube-transcript-api --prerelease=allow
```

**Note:** `--prerelease=allow` is still needed because `agent-framework-azure-ai` 1.0.0rc2 is a pre-release. Adding `youtube-transcript-api` (which is GA) does not change this requirement.

After adding to `pyproject.toml`:
```toml
dependencies = [
    # ... existing deps ...
    # YouTube transcript extraction for recipe URLs
    "youtube-transcript-api",
]
```

Then: `uv pip compile pyproject.toml -o requirements.txt` or `uv lock` to update the lock file.

---

## What NOT to Add

These were considered and explicitly rejected:

| Library/Package | Why Not |
|-----------------|---------|
| `beautifulsoup4` / `requests` | Not needed -- `youtube-transcript-api` handles transcript fetching internally |
| `langchain` | Massive dependency chain for simple transcript-to-LLM pipeline. The Agent Framework already provides the tool/agent pattern |
| `instructor` | Structured output extraction from GPT. Unnecessary -- the Admin Agent can call a `add_shopping_list_items` @tool with structured params directly |
| `expo-notifications` | Push notifications deferred to v3.1+ per PROJECT.md |
| `expo-location` | Location-aware reminders deferred to v3.1+ per PROJECT.md |
| `@expo/vector-icons` | Unicode icons in tabs work fine for MVP (existing pattern) |
| `react-native-reanimated` | Swipe-to-remove works with existing `react-native-gesture-handler` |
| `azure-ai-projects` v2.0.0b4 | Pre-release, unstable API, not needed -- `agent-framework-azure-ai` handles all agent lifecycle via `agents_client` |
| Any state management library (Zustand, Redux) | Single-screen shopping list state. React `useState` + `useEffect` with `fetch()` is sufficient for v3.0 |

---

## Integration Points

### How New Code Connects to Existing Stack

```
Mobile App (Expo)
  |
  |-- POST /api/capture (text/voice)
  |     |
  |     v
  |   Classifier Agent (existing)
  |     |-- file_capture tool --> Cosmos DB (Inbox + bucket container)
  |     |-- When bucket == "Admin":
  |     |     |
  |     |     v
  |     |   Admin Agent (NEW) -- code-based routing in FastAPI
  |     |     |-- extract_recipe_from_youtube tool (NEW)
  |     |     |     |-- youtube-transcript-api --> transcript text
  |     |     |     |-- Agent reasoning --> structured ingredients
  |     |     |     v
  |     |     |-- add_shopping_list_items tool (NEW)
  |     |     |     |-- CosmosManager --> ShoppingLists container
  |     |     |     v
  |     |     |-- SSE events back to mobile app
  |     |
  |-- GET /api/shopping-lists (NEW)
  |     |
  |     v
  |   CosmosManager --> ShoppingLists container
  |     |
  |     v
  |   JSON response --> Status & Priorities screen (NEW tab)
  |
  |-- PATCH /api/shopping-lists/{store}/items/{item} (NEW)
        |
        v
      CosmosManager --> update item.checked / remove item
```

### Shared Resources (Lifespan Singletons)

| Resource | Used By Classifier | Used By Admin Agent |
|----------|-------------------|---------------------|
| `credential` (AsyncDefaultAzureCredential) | Yes | Yes (same instance) |
| `cosmos_manager` (CosmosManager) | Yes (Inbox, Admin containers) | Yes (ShoppingLists container) |
| `AuditAgentMiddleware` | Yes | Yes (same instance) |
| `ToolTimingMiddleware` | Yes | Yes (same instance) |
| `foundry_client` (probe client) | Yes | Yes (same instance, list_agents validation) |

---

## Sources

- [youtube-transcript-api on PyPI](https://pypi.org/project/youtube-transcript-api/) -- version 1.2.4, release date, API
- [youtube-transcript-api GitHub](https://github.com/jdepoix/youtube-transcript-api) -- v1.x API, migration from 0.x
- [agent-framework-azure-ai on PyPI](https://pypi.org/project/agent-framework-azure-ai/) -- version 1.0.0rc2
- [AzureAIAgentClient API reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) -- constructor params, middleware, agent_id
- [Microsoft Agent Framework GitHub](https://github.com/microsoft/agent-framework) -- multi-agent patterns
- [Cosmos DB partitioning overview](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning-overview) -- partition key design
- [Expo Router tabs documentation](https://docs.expo.dev/router/advanced/tabs/) -- adding new tab screens
- [Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview?view=foundry-classic) -- multi-agent orchestration
