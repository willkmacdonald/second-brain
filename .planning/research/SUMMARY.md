# Project Research Summary

**Project:** Second Brain v3.0 — Admin Agent & Shopping Lists
**Domain:** Multi-agent personal capture system with specialist agent routing
**Researched:** 2026-03-01
**Confidence:** HIGH

## Executive Summary

Second Brain v3.0 adds the first specialist agent (Admin Agent) to an existing single-agent capture pipeline. The system already classifies captures into People/Projects/Ideas/Admin buckets via a persistent Foundry Agent Service agent — v3.0 makes the "Admin" bucket actionable by routing those captures through a second agent that manages store-based shopping lists and extracts ingredients from YouTube recipe URLs. The core approach is code-based sequential routing in FastAPI (not Foundry Connected Agents), which is the only viable pattern given that Connected Agents cannot invoke local @tool functions. The architecture is an incremental extension of v2.0's proven patterns: one new `AzureAIAgentClient`, one new tool class, one new Cosmos container, one new REST API router, and one new mobile tab.

The recommended approach is well-scoped and straightforward to implement because the patterns are already established in the codebase. Admin Agent registration mirrors `ensure_classifier_agent()` exactly. Tool structure mirrors `ClassifierTools`. The SSE streaming adapter is extended (not rewritten) to handle a two-phase pipeline. The single significant new dependency is `youtube-transcript-api` (v1.2.4), but there is a critical deployment risk: cloud provider IPs (Azure Container Apps) are actively blocked by YouTube's servers when using this library. Research confirms this as a well-documented, high-frequency failure mode across GitHub issues #303, #317, and #511. The correct mitigation is the official YouTube Data API v3 with an API key, not a proxy workaround, for all production use.

The three primary risks are: (1) YouTube transcript extraction via `youtube-transcript-api` fails in production on Azure IPs — switch to YouTube Data API v3 from the start, not as a retrofit; (2) concurrent writes to shopping list data require the Cosmos DB Patch API or individual-item documents to avoid lost updates under concurrent Admin Agent writes and user swipe-to-remove actions; (3) the SSE adapter must be extended with new Admin-specific event types or the mobile app will show no confirmation that any Admin capture was processed. None of these risks are blockers — each has a clear prevention strategy that must be built in from the start rather than patched later.

## Key Findings

### Recommended Stack

The existing stack requires only one new package for v3.0. The `youtube-transcript-api` (v1.2.4) handles YouTube caption extraction without an API key in local environments, but research confirms it is unreliable on Azure datacenter IPs. The practical implication: plan for YouTube Data API v3 integration from the start rather than discovering the cloud IP block after deployment. All other components — `agent-framework-azure-ai`, `azure-cosmos`, FastAPI, Expo/expo-router, Azure Container Apps CI/CD — are unchanged and already in production.

**Core technologies:**
- `youtube-transcript-api` v1.2.4: YouTube transcript extraction — use for local dev only; use YouTube Data API v3 for production cloud deployment
- `agent-framework-azure-ai` v1.0.0rc2: AzureAIAgentClient for Admin Agent — same package as Classifier, reuse existing patterns exactly
- `azure-cosmos` (existing): ShoppingLists container — one new container with `/userId` partition key, one line added to `CONTAINER_NAMES`
- `expo-router` v6 (existing): Third tab for Status screen — add one `Tabs.Screen` entry, no new mobile packages required

**Version-critical detail:** The v1.x `youtube-transcript-api` API is a breaking change from v0.x. Do NOT use the old static `YouTubeTranscriptApi.get_transcript()` — instantiate `YouTubeTranscriptApi()` and use `.fetch()`. See STACK.md for the correct v1.x usage.

### Expected Features

**Must have (table stakes):**
- Classifier to Admin Agent inline handoff — core premise of v3.0; code-based routing detects `bucket == "Admin"` and invokes Admin Agent in the same SSE stream
- Store-based shopping lists in Cosmos DB — one document per store (or one per item; see Gaps); items grouped by store (Jewel, CVS, Pet Store)
- Agent-driven store routing — Admin Agent instructions map item categories to stores; routing evolves without code deployment
- Ad hoc item capture to correct store — primary use case (est. 70% of usage); voice/text capture lands in the right store list automatically
- YouTube recipe URL to ingredient extraction — stated project goal; pipeline is transcript fetch → agent reasoning → add items
- Status & Priorities screen (third mobile tab) — displays shopping lists grouped by store with check-off and swipe-to-remove
- Swipe-to-remove on shopping list items — matches existing Inbox UX; requires atomic Cosmos writes to avoid lost updates

**Should have (differentiators):**
- Voice capture to shopping list items — zero additional code once handoff exists; the existing voice pipeline flows through automatically
- Multi-store splitting from single capture — "need milk and cat litter" files to two stores in one capture; primarily agent instruction quality
- Recipe source attribution on items — items from YouTube recipes show which recipe they came from
- Real-time streaming feedback during Admin processing — SSE step events show "Classifying... Routing to Admin... Extracting recipe..." rather than a blank spinner

**Defer to v3.1+:**
- Push notifications for list updates — pull-based UI is sufficient for single user at v3.0
- Location-aware store reminders — geofencing complexity, Expo managed workflow limitations
- Auto-ordering (Chewy.com, etc.) — requires computer use, extreme complexity
- Item deduplication/merge — accept duplicates for now; user can manually delete
- Recipe website scraping for non-YouTube URLs — `recipe-scrapers` supports 611 sites but is out of scope for v3.0

### Architecture Approach

The v3.0 architecture extends the existing pipeline with a sequential two-phase capture flow. Phase 1 is unchanged: the Classifier Agent classifies the capture and calls `file_capture` to bucket it. Phase 2 is new: if `bucket == "Admin"`, FastAPI code routes to the Admin Agent client which runs its tool chain (`add_shopping_list_items`, optionally `fetch_youtube_transcript`). The handoff is deterministic code logic, not agent-to-agent communication. The SSE stream continues across both phases — the mobile app sees one unbroken stream with Classifier events followed by Admin events. The Status screen is a separate REST data-fetching screen (not SSE), identical in pattern to the Inbox screen but with a purpose-built hierarchical API response shape.

**Major components:**
1. `AdminTools` (tools/admin.py) — @tool functions for shopping list CRUD and YouTube transcript fetching; bound to `CosmosManager` via constructor injection, same as `ClassifierTools`
2. `ensure_admin_agent()` (agents/admin.py) — self-healing Admin Agent registration on startup; mirrors `ensure_classifier_agent()` exactly
3. `stream_admin_enrichment()` (streaming/adapter.py) — extends SSE adapter for two-phase pipeline; emits Admin-specific events (`ADMIN_ENRICHED`, `SHOPPING_ITEM_ADDED`, `RECIPE_EXTRACTED`, `EXTRACTION_FAILED`)
4. `api/shopping_lists.py` — REST router for Status screen: `GET /api/shopping-lists`, `PATCH` item checked, `DELETE` item
5. `StatusScreen` (mobile/app/(tabs)/status.tsx) — third tab; fetches on focus, collapsible store sections, swipe-to-remove with optimistic UI
6. `ShoppingListDocument` / `ShoppingItem` (models/documents.py) — Pydantic schemas for the new `ShoppingLists` Cosmos container

### Critical Pitfalls

1. **Thread cross-contamination between Classifier and Admin Agent** — Create a separate `AzureAIAgentClient` instance for the Admin Agent with its own `agent_id`. Never pass the Classifier's Foundry thread to the Admin Agent. Microsoft docs explicitly warn this is unsafe. The Admin Agent gets ephemeral threads (one-shot per capture), the Classifier gets persistent threads. This separation must be the starting design, not a retrofit.

2. **YouTube transcript extraction blocked on Azure cloud IPs** — `youtube-transcript-api` works locally but fails in production on Azure Container Apps. YouTube actively blocks cloud datacenter IP ranges. GitHub issues #303, #317, #511 all confirm this. Use the YouTube Data API v3 (official, authenticated, not blocked) for production. Do not attempt residential proxy workarounds for a hobby project.

3. **Shopping list array writes create race conditions** — The Admin Agent (writing items) and the user (swiping to remove) can write to the same Cosmos document concurrently. Cosmos DB defaults to Last Writer Wins, so one write will silently overwrite the other. Use the Cosmos DB Patch API for atomic array operations, or — strongly preferred per PITFALLS.md — model each item as its own Cosmos document with a `store` field, enabling independent create/delete with no array index fragility.

4. **Admin Agent tools registered on Classifier client (tool leakage)** — If shopping list tools are added to the Classifier's tool list, the Classifier will opportunistically call `add_shopping_item` directly, bypassing the Admin Agent's store-routing logic. Maintain strictly separate tool lists per agent client from day one.

5. **SSE adapter assumes single-agent tool detection** — The existing adapter only recognizes `file_capture` as a terminal tool call. Admin Agent tool calls are silently ignored without adapter extension. New event types are required: `ADMIN_ENRICHED`, `SHOPPING_ITEM_ADDED`, `RECIPE_EXTRACTED`, `EXTRACTION_FAILED`. The mobile `ag-ui-client.ts` switch statement must handle these types for the user to see any confirmation of Admin processing.

## Implications for Roadmap

Based on combined research, the dependency chain is clear and the build order is driven by data-before-behavior: the data model and tools must exist before the agent can be registered, the agent must exist before the capture handoff can work, and the handoff must write data before the mobile screen has anything to display. YouTube extraction is the highest-risk feature and should be layered on last after the core ad hoc item pipeline is validated.

### Phase 1: Data Foundation

**Rationale:** Every downstream component (agent tools, API endpoints, mobile screen) depends on Pydantic models and the Cosmos container. Zero of the remaining phases can function without this layer. Must be first.
**Delivers:** `ShoppingListDocument` + `ShoppingItem` Pydantic models; `"ShoppingLists"` added to `CONTAINER_NAMES`; `AdminTools` class with `add_shopping_list_items` @tool writing to Cosmos; `ShoppingLists` container created in Azure Portal.
**Addresses:** TS-2 (store-based data model), TS-3 (store routing via tool)
**Avoids:** Pitfall 9 (container not created before code writes to it), Pitfall 3 (data model decision locked in early with Patch API or individual docs)

### Phase 2: Admin Agent Registration

**Rationale:** The Admin Agent must exist as a registered Foundry agent before the capture pipeline can invoke it. Agent instructions — written in the Foundry portal — determine all store-routing behavior and must be written alongside the code.
**Delivers:** `ensure_admin_agent()` function in agents/admin.py; `azure_ai_admin_agent_id` config setting; Admin Agent client initialized in main.py lifespan; `AZURE_AI_ADMIN_AGENT_ID` env var on Container Apps; Admin Agent instructions written in Foundry portal with store routing rules.
**Addresses:** TS-1 (second persistent Foundry agent), TS-3 (agent-driven store routing)
**Avoids:** Pitfall 1 (thread contamination — separate AzureAIAgentClient instance from day one), Pitfall 4 (tool leakage — separate tool lists per agent from day one)

### Phase 3: Capture Pipeline Integration

**Rationale:** With the data layer (Phase 1) and agent registered (Phase 2), the end-to-end ad hoc item capture flow can be wired together. The SSE adapter extension and new event types must be done in this phase — retrofitting them later creates mobile/backend misalignment risk.
**Delivers:** `stream_admin_enrichment()` in adapter.py; conditional Admin routing in `stream_text_capture()` and `stream_voice_capture()`; new SSE events (`ADMIN_ENRICHED`, `SHOPPING_ITEM_ADDED`); mobile handles new event types and shows store confirmation toast; per-step timeout values increased for two-agent pipeline (recommended: 90 seconds total).
**Addresses:** TS-1 (handoff), TS-4 (ad hoc item capture), D-1 (voice capture flows through automatically), D-4 (streaming feedback)
**Avoids:** Pitfall 5 (adapter single-agent assumption), Pitfall 8 (ContextVar scope — pass `inbox_item_id` explicitly, not via ContextVar), Pitfall 10 (generic CLASSIFIED feedback is useless for Admin captures), Pitfall 11 (60-second timeout insufficient for two-agent pipeline)

### Phase 4: Shopping List API and Status Screen

**Rationale:** Once Cosmos has shopping list data written by Phase 3, the REST endpoints and mobile screen can be built. The API and mobile screen are relatively independent of Phase 3 implementation details — they read from Cosmos, so they can be built in parallel with Phase 3 once the data model (Phase 1) is finalized.
**Delivers:** `api/shopping_lists.py` router (`GET /api/shopping-lists`, `PATCH` check item, `DELETE` item); `StatusScreen` mobile component (third tab, collapsible store sections, item list); swipe-to-remove with optimistic UI and rollback; tab layout update in `_layout.tsx`.
**Addresses:** TS-6 (Status screen), TS-7 (swipe-to-remove)
**Avoids:** Pitfall 12 (data shape mismatch — design shopping list API independently from InboxListResponse; response is hierarchical store/items, not flat)

### Phase 5: YouTube Recipe Extraction

**Rationale:** Enhancement layer on top of the working ad hoc item pipeline. Deliberately last because YouTube extraction has the most implementation uncertainty (cloud IP blocking, caption availability, timeout pressure from a third network dependency). The full v3.0 value proposition — daily shopping list management via voice/text capture — is delivered without YouTube extraction.
**Delivers:** `fetch_youtube_transcript` @tool; YouTube Data API v3 integration (not `youtube-transcript-api` for production); Admin Agent instructions updated for recipe handling; `RECIPE_EXTRACTED` and `EXTRACTION_FAILED` SSE events; fallback chain for missing captions ("No captions available — paste recipe text directly"); end-to-end test with real YouTube recipe URLs.
**Addresses:** TS-5 (YouTube recipe extraction), D-3 (recipe source attribution on items)
**Avoids:** Pitfall 2 (cloud IP blocking — use YouTube Data API v3, not `youtube-transcript-api` in production), Pitfall 6 (missing captions — build graceful fallback chain before considering this done)

### Phase Ordering Rationale

- **Data before behavior:** Pydantic models and Cosmos container in Phase 1 unblock all downstream phases. The decision between embedded array vs. individual item documents must be made here and cannot be changed cheaply later.
- **Agent before handoff:** The Admin Agent must be registered (Phase 2) before the capture pipeline can route to it (Phase 3). Writing agent instructions alongside registration is critical — routing accuracy depends on instruction quality.
- **Ad hoc items before recipe extraction:** The core shopping list use case (Phases 3-4) should work reliably and be validated before adding the complexity of YouTube extraction (Phase 5). This allows store routing quality to be assessed with simple text captures first.
- **YouTube extraction deliberately last:** It has the highest implementation risk (cloud IP blocking is a confirmed production failure mode, not a hypothetical) and is the most separable enhancement. The daily-use value of the system is fully delivered without it.
- **Status screen parallelizable with Phase 3:** The API endpoints read from Cosmos written by Phase 1 models. They can be built alongside Phase 3 if bandwidth allows, since the only shared dependency is the Phase 1 data model.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5 (YouTube extraction):** YouTube Data API v3 setup, caption download API surface, and handling auto-generated vs manual caption types need implementation-time research. STACK.md covers `youtube-transcript-api` thoroughly but does not fully document the YouTube Data API v3 alternative path. Treat this as pre-work before Phase 5 starts.
- **Phase 3 (SSE adapter extension):** The two-phase streaming pipeline is novel for this codebase. The adapter refactor scope, new event type contracts, and mobile event handling should be designed carefully before coding to avoid mobile/backend misalignment that would require changes to both sides.

Phases with standard patterns (skip research):
- **Phase 1 (Data Foundation):** Pydantic models and Cosmos container are identical to existing containers and tool class patterns. No unknowns.
- **Phase 2 (Admin Agent Registration):** Exact mirror of `ensure_classifier_agent()`. No new patterns.
- **Phase 4 (Shopping List API + Status Screen):** REST endpoints follow existing FastAPI router patterns. Expo tab addition is documented and trivial. Optimistic UI matches existing Inbox swipe-to-delete pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All existing packages verified in production. `youtube-transcript-api` fully researched including cloud IP blocking pitfall. YouTube Data API v3 is the correct production alternative. One new dependency only. |
| Features | HIGH | Feature set is small and well-defined. Scope tightly bounded by PROJECT.md anti-features list. No ambiguous requirements. Usage scenario estimates (70% ad hoc, 15% recipe, 10% at-store, 5% multi-store) are plausible for single-user system. |
| Architecture | HIGH | Code-based routing pattern is identical to existing Classifier pattern. Handoff mechanics, data model, SSE extension, and REST API design are all detailed and verified against codebase. Component boundaries are clear. |
| Pitfalls | HIGH | 12 pitfalls identified. Critical pitfalls verified via official docs, confirmed GitHub issues, and direct codebase analysis. Cloud IP blocking has multiple independent source confirmations across 2024-2026. Cosmos race condition prevention is well-documented. |

**Overall confidence:** HIGH

### Gaps to Address

- **YouTube Data API v3 implementation path:** Research confirmed `youtube-transcript-api` won't work in production but did not fully document the YouTube Data API v3 setup (Google Cloud project, API key, caption download endpoint, handling caption types). Resolve before Phase 5 begins — treat as Phase 5 pre-work research.

- **Individual item documents vs embedded array — firm decision needed before Phase 1:** PITFALLS.md recommends individual item documents (one Cosmos document per shopping list item) for atomicity and no array index fragility. STACK.md and ARCHITECTURE.md both describe embedded arrays in a store document. This must be decided before Phase 1 starts. Recommendation: go with individual item documents — the Pitfall 3 analysis is rigorous on concurrent write risks and serverless Cosmos DB pricing is per-RU not per-document, so document count is not a cost concern.

- **Admin Agent instruction quality:** Store routing accuracy depends entirely on instructions written in the Foundry portal. These can only be validated empirically after the end-to-end pipeline works. Plan for an instruction-tuning sub-step in Phase 3 after first captures flow through. Consider the `get_store_registry` grounding tool (Pitfall 7) to reduce routing non-determinism from the start.

- **Two-agent pipeline timeout UX:** PITFALLS.md recommends 90 seconds for the full multi-agent pipeline including YouTube extraction. Confirm the current mobile progress indicator design handles this gracefully. A 90-second capture with no progress feedback will feel broken. SSE step events ("Classifying...", "Routing to Admin...", "Extracting recipe...") are essential, not optional, for this timeout range.

## Sources

### Primary (HIGH confidence)
- [youtube-transcript-api PyPI](https://pypi.org/project/youtube-transcript-api/) — v1.2.4 release date, v1.x API, install instructions
- [youtube-transcript-api GitHub](https://github.com/jdepoix/youtube-transcript-api) — cloud IP blocking issues #303, #317, #511
- [AzureAIAgentClient API Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) — agent_id, should_cleanup_agent, thread isolation warnings
- [Azure AI Agent Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) — routing/dispatch pattern, multi-agent design
- [Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview?view=foundry-classic) — persistent agents, multi-agent orchestration
- [Azure AI Foundry Connected Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/connected-agents?view=foundry-classic) — confirms local @tool limitation (rules out Connected Agents)
- [HandoffBuilder GitHub issue #3097](https://github.com/microsoft/agent-framework/issues/3097) — confirms HandoffBuilder bugs with AzureAIClient (rules out HandoffBuilder)
- [Cosmos DB Partial Document Update](https://learn.microsoft.com/en-us/azure/cosmos-db/partial-document-update) — Patch API, atomic array operations
- [Cosmos DB Optimistic Concurrency Control](https://learn.microsoft.com/en-us/azure/cosmos-db/database-transactions-optimistic-concurrency) — ETag-based concurrency, Last Writer Wins behavior
- [Expo Router tabs documentation](https://docs.expo.dev/router/advanced/tabs/) — adding new tab screens
- Existing codebase (`backend/src/second_brain/`) — all current patterns verified by reading source

### Secondary (MEDIUM confidence)
- [Building a nutritional co-pilot using LLMs](https://medium.com/@kbambalov/building-a-nutritional-co-pilot-using-llms-part-1-recipe-extraction-e112645ef9fd) — recipe extraction patterns via LLM
- [AnyList features](https://www.anylist.com/features) — competitive context for shopping list UX conventions
- [NerdWallet best grocery list apps 2025](https://www.nerdwallet.com/finance/learn/best-grocery-list-apps) — market context, user expectations
- [Nielsen Norman Group: contextual swipe](https://www.nngroup.com/articles/contextual-swipe/) — swipe-to-remove UX conventions

---

## Files in This Research Set

| File | Purpose |
|------|---------|
| `.planning/research/STACK.md` | Technology recommendations — 1 new package, integration points, what NOT to add |
| `.planning/research/FEATURES.md` | Feature landscape — table stakes, differentiators, anti-features, usage scenarios |
| `.planning/research/ARCHITECTURE.md` | Architecture patterns — handoff design, data model, SSE extension, build order |
| `.planning/research/PITFALLS.md` | Domain pitfalls — 12 pitfalls with prevention strategies, phase-specific warnings |
| `.planning/research/SUMMARY.md` | This file — executive summary and roadmap implications |

---
*Research completed: 2026-03-01*
*Ready for roadmap: yes*
