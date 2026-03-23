# Phase 10: Data Foundation and Admin Tools - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Shopping list data model and tool functions exist so downstream phases can write and read shopping list items. Specifically: Pydantic models, a ShoppingLists Cosmos container, and an AdminTools @tool class with `add_shopping_list_items`. The Admin Agent is configured but NOT wired into the capture flow (Phase 11 handles that). No UI work.

</domain>

<decisions>
## Implementation Decisions

### Shopping item data model
- Minimal fields: name + store only
- No status tracking — items exist or they don't (delete = remove the document)
- No timestamps — items have no inherent order
- Item names stored as full strings, lowercase, natural language (e.g., "2 lbs ground beef" not split into name/quantity)
- Duplicates allowed — if user says "need milk" twice, both items are added

### Store taxonomy
- Fixed enum of known stores: Jewel, CVS, Pet store
- Plus an "Other" catch-all for items that don't match known stores
- Store list defined in the Admin Agent's instructions (not hardcoded in backend code)
- Agent instructions use both category-based rules AND examples for store routing (e.g., "Groceries/food -> Jewel" plus specific examples like "milk, bread, eggs")

### Cosmos container configuration
- New container: ShoppingLists, added to the existing `second-brain` database
- Partition key: `/store` (different from other containers which use `/userId`)
- Throughput: match existing database mode (researcher to confirm serverless vs provisioned)
- No TTL — items persist until explicitly deleted
- Container provisioning approach: researcher to check how existing containers are set up and follow same pattern

### Tool interface design
- `add_shopping_list_items` accepts a batch (list of items) in one call
- Returns confirmation with count: "Added 3 items: 2 to Jewel, 1 to CVS"
- Write-only for Phase 10 — no read/delete tools yet (Phase 12 adds those)
- Tool validates store names against known list; unknown stores fall back to "Other" silently

### Admin Agent configuration
- Same creation approach as the Classifier agent (researcher to check how Classifier was set up)
- Same Azure OpenAI resource (`second-brain-foundry-resource`), different agent_id
- Uses gpt-4o model (same as Classifier)
- Configure only in Phase 10 — no capture flow wiring (Phase 11)
- Agent extracts structured items from raw capture text (e.g., "need cat litter and milk" -> two items with store assignments)

### Test harness
- pytest integration tests that call the tool function directly (not through an agent)
- Tests write to real Cosmos DB (integration tests, not mocked)
- Tests clean up after themselves — delete test items after assertions
- Also verify Admin Agent can be instantiated (agent_id is valid, agent is fetchable from Foundry)

### Claude's Discretion
- Pydantic model field names and exact schema
- Cosmos indexing policy for ShoppingLists container
- AdminTools class structure and decorator patterns
- Admin Agent system prompt wording (given the routing rules above)
- How CosmosManager is extended to include the new container

</decisions>

<specifics>
## Specific Ideas

- Shared ACR exists: `wkmsharedservicesacr` — use this for container images (already in use for deployment)
- Agent instructions should include both category rules and specific item examples for store routing
- Item names should be natural language as the user said them — don't over-process

</specifics>

<deferred>
## Deferred Ideas

- Shared Cosmos DB account across projects — future infrastructure task to migrate to a shared Cosmos account (e.g., `wkm-shared-cosmos`) with per-project databases. For now, `second-brain` database stays project-specific.
- Swipe-to-delete on shopping list items — Phase 12 (already in roadmap success criteria)
- Read/query tools for shopping lists — Phase 12 (when API endpoints are built)

</deferred>

---

*Phase: 10-data-foundation-and-admin-tools*
*Context gathered: 2026-03-01*
