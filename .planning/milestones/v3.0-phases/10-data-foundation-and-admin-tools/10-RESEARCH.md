# Phase 10: Data Foundation and Admin Tools - Research

**Researched:** 2026-03-01
**Domain:** Cosmos DB data modeling, Agent Framework @tool patterns, multi-agent client configuration
**Confidence:** HIGH

## Summary

Phase 10 establishes the data foundation for shopping lists and the Admin Agent's tool interface. The work involves three distinct layers: (1) a new ShoppingLists Cosmos container with `/store` partition key (different from the `/userId` used elsewhere), (2) an AdminTools class with an `add_shopping_list_items` @tool that writes batches of items to Cosmos, and (3) a separate AzureAIAgentClient instance for the Admin Agent with its own tool list.

The existing codebase provides clear patterns for all three layers. The Classifier agent setup in `main.py` is a direct template for the Admin Agent client. The ClassifierTools class demonstrates the @tool decorator pattern with bound CosmosManager. The CosmosManager uses `get_container_client()` (not `create_container`) so the new ShoppingLists container must be created externally before deployment.

**Primary recommendation:** Follow existing patterns exactly. The ShoppingLists container must be created in the Azure portal (or CLI) before code is deployed, the AdminTools class should mirror ClassifierTools structure, and the Admin Agent AzureAIAgentClient should be a second instance in the lifespan alongside the Classifier client.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Minimal fields: name + store only
- No status tracking -- items exist or they don't (delete = remove the document)
- No timestamps -- items have no inherent order
- Item names stored as full strings, lowercase, natural language (e.g., "2 lbs ground beef" not split into name/quantity)
- Duplicates allowed -- if user says "need milk" twice, both items are added
- Fixed enum of known stores: Jewel, CVS, Pet store
- Plus an "Other" catch-all for items that don't match known stores
- Store list defined in the Admin Agent's instructions (not hardcoded in backend code)
- Agent instructions use both category-based rules AND examples for store routing
- New container: ShoppingLists, added to the existing `second-brain` database
- Partition key: `/store` (different from other containers which use `/userId`)
- No TTL -- items persist until explicitly deleted
- Container provisioning approach: follow same pattern as existing containers
- `add_shopping_list_items` accepts a batch (list of items) in one call
- Returns confirmation with count: "Added 3 items: 2 to Jewel, 1 to CVS"
- Write-only for Phase 10 -- no read/delete tools yet (Phase 12 adds those)
- Tool validates store names against known list; unknown stores fall back to "Other" silently
- Same creation approach as the Classifier agent
- Same Azure OpenAI resource (`second-brain-foundry-resource`), different agent_id
- Uses gpt-4o model (same as Classifier)
- Configure only in Phase 10 -- no capture flow wiring (Phase 11)
- Agent extracts structured items from raw capture text
- pytest integration tests that call the tool function directly (not through an agent)
- Tests write to real Cosmos DB (integration tests, not mocked)
- Tests clean up after themselves -- delete test items after assertions
- Also verify Admin Agent can be instantiated (agent_id is valid, agent is fetchable from Foundry)

### Claude's Discretion
- Pydantic model field names and exact schema
- Cosmos indexing policy for ShoppingLists container
- AdminTools class structure and decorator patterns
- Admin Agent system prompt wording (given the routing rules above)
- How CosmosManager is extended to include the new container

### Deferred Ideas (OUT OF SCOPE)
- Shared Cosmos DB account across projects -- future infrastructure task
- Swipe-to-delete on shopping list items -- Phase 12
- Read/query tools for shopping lists -- Phase 12
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGNT-02 | Admin Agent has separate AzureAIAgentClient instance with own agent_id and tool list | Existing Classifier client pattern in `main.py` lines 182-191 provides exact template. Second `AzureAIAgentClient` with different `agent_id`, `should_cleanup_agent=False`, and separate `middleware` list. New env var `AZURE_AI_ADMIN_AGENT_ID` in config.py. |
| SHOP-01 | Shopping list items stored in Cosmos DB, grouped by store | ShoppingLists container with `/store` partition key. Individual documents per item. Pydantic `ShoppingListItem` model with `id`, `store`, `name` fields. CosmosManager extended with "ShoppingLists" in `CONTAINER_NAMES`. |
| SHOP-02 | Admin Agent routes items to correct store based on agent instructions | AdminTools.add_shopping_list_items @tool validates store names against known enum, falls back to "Other". Store routing logic lives in agent instructions (Foundry portal), not in code. The @tool just writes what the agent decides. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| azure-cosmos | Already installed | Cosmos DB async CRUD operations | Current project dependency, async `ContainerProxy` for reads/writes |
| agent-framework-azure-ai | Already installed | AzureAIAgentClient + @tool decorator | Current project dependency, provides `@tool` decorator and agent client |
| pydantic | Already installed (via pydantic-settings) | Data models for shopping list items | Current project pattern for all Cosmos document models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + pytest-asyncio | Already in test deps | Integration tests against real Cosmos | Test harness for tool functions and agent validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Individual item documents | Embedded arrays in store documents | Earlier research suggested per-store docs, but CONTEXT.md locks individual items. Individual docs are better for atomicity and avoid race conditions on concurrent writes. |
| `/store` partition key | `/userId` (like other containers) | `/store` enables efficient queries per store without cross-partition. Single-user system so `/userId` adds no value. User locked this decision. |

**Installation:** No new packages needed. All dependencies are already in pyproject.toml.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/second_brain/
├── agents/
│   ├── classifier.py      # ensure_classifier_agent() -- EXISTING
│   ├── admin.py            # ensure_admin_agent() -- NEW (mirrors classifier.py)
│   └── middleware.py        # OTel middleware -- EXISTING
├── db/
│   └── cosmos.py            # CosmosManager -- MODIFY (add "ShoppingLists" to CONTAINER_NAMES)
├── models/
│   └── documents.py         # Pydantic models -- MODIFY (add ShoppingListItem)
├── tools/
│   ├── classification.py    # ClassifierTools -- EXISTING (template for AdminTools)
│   └── admin.py             # AdminTools -- NEW (add_shopping_list_items @tool)
├── config.py                # Settings -- MODIFY (add azure_ai_admin_agent_id)
└── main.py                  # Lifespan -- MODIFY (add Admin Agent client + tools)

backend/tests/
├── test_admin_tools.py       # Unit tests with mocked Cosmos -- NEW
└── test_admin_integration.py # Integration tests against real Cosmos -- NEW
```

### Pattern 1: CosmosManager Extension for Different Partition Key

**What:** The ShoppingLists container uses `/store` partition key, unlike all other containers which use `/userId`. The existing CosmosManager uses `get_container_client()` which returns a `ContainerProxy` -- this works regardless of partition key. The partition key only matters at read/write time.

**When to use:** Always. Container clients are partition-key-agnostic; the partition key is specified per operation.

**Key insight:** `get_container_client("ShoppingLists")` works the same as any other container. The difference is that when calling `create_item()`, `read_item()`, or `query_items()`, the partition_key parameter must be the store name (e.g., `"jewel"`) instead of `"will"`.

**Implementation:**
```python
# In db/cosmos.py -- only change is adding to CONTAINER_NAMES
CONTAINER_NAMES: list[str] = [
    "Inbox", "People", "Projects", "Ideas", "Admin", "ShoppingLists"
]
```

The container itself must already exist in Azure with partition key `/store`. The `CosmosManager.initialize()` method just calls `database.get_container_client(name)` for each name in the list -- it never creates containers.

### Pattern 2: AdminTools @tool Class (Mirrors ClassifierTools)

**What:** A class that binds a CosmosManager reference and exposes @tool-decorated methods for the Admin Agent to call. Follows the identical pattern as ClassifierTools.

**When to use:** For all agent tool functions that need access to shared resources (CosmosManager, OpenAI client, etc.).

**Example:**
```python
# Source: Existing ClassifierTools pattern in tools/classification.py
from agent_framework import tool
from pydantic import Field
from typing import Annotated

class AdminTools:
    """Admin agent tools bound to a CosmosManager instance."""

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        self._manager = cosmos_manager

    @tool(approval_mode="never_require")
    async def add_shopping_list_items(
        self,
        items: Annotated[
            list[dict],
            Field(description="List of items, each with 'name' and 'store' fields"),
        ],
    ) -> str:
        """Add one or more items to shopping lists, grouped by store."""
        # Validate stores, write to Cosmos, return confirmation
        ...
```

**Critical detail on @tool parameter types:** The `items` parameter must be a type the agent can produce as JSON. A `list[dict]` works. Each dict should have `name: str` and `store: str`. The @tool decorator from agent-framework auto-generates the JSON schema from type annotations and Field descriptions.

### Pattern 3: Second AzureAIAgentClient Instance

**What:** A separate AzureAIAgentClient for the Admin Agent, configured independently from the Classifier client.

**When to use:** For each agent that needs its own tool list and agent_id.

**Example:**
```python
# Source: Existing Classifier client pattern in main.py lines 182-191
admin_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=admin_agent_id,
    should_cleanup_agent=False,
    middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()],
)
app.state.admin_client = admin_client
```

**Key parameters:**
- `agent_id`: The Admin Agent's ID (from AZURE_AI_ADMIN_AGENT_ID env var)
- `should_cleanup_agent=False`: Do not delete the agent when the client closes (agent persists across restarts)
- `credential`: Shares the same `DefaultAzureCredential` as the Classifier client
- `middleware`: Can reuse the same middleware classes (or create Admin-specific ones)

### Pattern 4: ensure_admin_agent() (Mirrors ensure_classifier_agent)

**What:** Self-healing agent registration that validates the stored agent_id on startup, creating a new agent if the ID is invalid.

**Example:**
```python
# Source: agents/classifier.py -- exact same pattern
async def ensure_admin_agent(
    foundry_client: AzureAIAgentClient,
    stored_agent_id: str,
) -> str:
    """Ensure the Admin agent exists in Foundry."""
    if stored_agent_id:
        try:
            agent_info = await foundry_client.agents_client.get_agent(stored_agent_id)
            logger.info("Admin agent loaded: id=%s name=%s", agent_info.id, agent_info.name)
            return stored_agent_id
        except Exception:
            logger.warning("Stored Admin agent ID %s not found, creating new", stored_agent_id)

    new_agent = await foundry_client.agents_client.create_agent(
        model="gpt-4o",
        name="AdminAgent",
    )
    logger.info(
        "NEW Admin agent: id=%s -- SET INSTRUCTIONS IN AI FOUNDRY PORTAL",
        new_agent.id,
    )
    return new_agent.id
```

### Pattern 5: Pydantic Model for Shopping List Items

**What:** A minimal Pydantic model for individual shopping list item documents.

**Key design decisions from CONTEXT.md:**
- Minimal fields: `name` + `store` only
- No `userId` field needed (partition is `/store`, not `/userId`)
- No timestamps (user decision)
- No status field (items exist or they don't)

```python
class ShoppingListItem(BaseModel):
    """Individual shopping list item document in ShoppingLists container.

    Partitioned by /store (not /userId like other containers).
    Items exist until deleted -- no status tracking.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    store: str  # Partition key: "jewel", "cvs", "pet_store", "other"
    name: str   # Natural language: "2 lbs ground beef", "cat litter"
```

**Note:** This model intentionally does NOT extend `BaseDocument`. BaseDocument includes `userId`, `createdAt`, `updatedAt`, `rawText`, and `classificationMeta` -- none of which apply to shopping list items. A clean, minimal model is more appropriate.

### Anti-Patterns to Avoid

- **Do NOT add CONTAINER_MODELS entry for ShoppingListItem.** The `CONTAINER_MODELS` dict maps bucket names to document models for the Classifier's `file_capture` tool. Shopping list items are not classified captures -- they're created by a completely different tool. Mixing them would be confusing.
- **Do NOT pass `offer_throughput` when creating the container.** The Cosmos DB account is serverless. Passing any throughput value will cause an error. The container must be created with only `id` and `partition_key`.
- **Do NOT hardcode store names in Python code.** Per CONTEXT.md, the store list lives in the Admin Agent's instructions (Foundry portal). The tool validates against a known list for safety, but the agent's instructions are the source of truth for store routing.
- **Do NOT reuse the Classifier's AzureAIAgentClient.** Each agent needs its own client instance with its own agent_id and tool list. Sharing would cause tool leakage (Classifier seeing Admin tools and vice versa).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container creation | Python code in CosmosManager | Azure Portal or `az cosmosdb sql container create` CLI | Existing pattern: containers are created externally, code only gets references. Serverless Cosmos requires no throughput setting. |
| Agent registration | Custom agent setup logic | `ensure_admin_agent()` mirroring `ensure_classifier_agent()` | Self-healing pattern already proven in production with the Classifier |
| Tool schema generation | Manual JSON schema for tool parameters | `@tool` decorator + type annotations + `Field(description=...)` | agent-framework auto-generates JSON schema from Python type hints |
| Partition key routing | Custom middleware to route by store | Native Cosmos `partition_key` parameter on `create_item`/`query_items` | SDK handles partition key routing natively -- just pass the store name |

**Key insight:** Phase 10 is almost entirely "follow the existing pattern, but for a new agent." There is very little novel architecture. The biggest risk is getting the small differences right (partition key `/store` vs `/userId`, serverless container creation, separate client instances).

## Common Pitfalls

### Pitfall 1: Serverless Cosmos Rejects offer_throughput
**What goes wrong:** Creating the ShoppingLists container with `offer_throughput=400` (as shown in most Azure docs examples) causes an error on a serverless account.
**Why it happens:** Serverless Cosmos DB does not accept throughput settings. You cannot pass any throughput when creating a serverless container, or an error is returned.
**How to avoid:** Create the container via Azure Portal or CLI without specifying throughput:
```bash
az cosmosdb sql container create \
  --account-name <cosmos-account> \
  --database-name second-brain \
  --name ShoppingLists \
  --partition-key-path "/store" \
  --resource-group shared-services-rg
```
Or use the Azure Portal: Database -> second-brain -> New Container -> Name: ShoppingLists, Partition key: /store.
**Warning signs:** `CosmosHttpResponseError` with message about throughput not being supported.
**Confidence:** HIGH -- confirmed from Azure docs: "You can't pass any throughput when you create a serverless container or an error is returned."

### Pitfall 2: Partition Key Value Mismatch
**What goes wrong:** Using `partition_key="will"` (the pattern in all existing code) when querying ShoppingLists container. Items would not be found because the partition key is `/store`, not `/userId`.
**Why it happens:** Muscle memory from existing code. Every other Cosmos operation in the codebase uses `partition_key="will"`.
**How to avoid:** AdminTools must use the store name as the partition key value:
```python
# WRONG (copied from existing pattern):
await container.read_item(item=item_id, partition_key="will")

# CORRECT for ShoppingLists:
await container.read_item(item=item_id, partition_key="jewel")

# Query by store:
async for item in container.query_items(
    query="SELECT * FROM c",
    partition_key="jewel",
):
    ...
```
**Warning signs:** Empty query results or `CosmosResourceNotFoundError` when items definitely exist.
**Confidence:** HIGH -- the existing code uses `partition_key="will"` in every Cosmos operation (see `tools/cosmos_crud.py` line 89, `tools/classification.py` line 256).

### Pitfall 3: Tool Parameter Types Not Agent-Friendly
**What goes wrong:** Defining `items: list[ShoppingListItem]` as the @tool parameter type. The agent needs to produce JSON matching this schema, but complex nested Pydantic models may confuse the agent or produce schema issues.
**Why it happens:** Natural instinct to use Pydantic models for validation. But the @tool decorator generates JSON schema from the type annotation, and the agent must produce JSON matching that schema.
**How to avoid:** Use `list[dict]` for the tool parameter and validate inside the function:
```python
@tool(approval_mode="never_require")
async def add_shopping_list_items(
    self,
    items: Annotated[
        list[dict],
        Field(description=(
            "List of shopping items. Each item is a dict with "
            "'name' (str, lowercase) and 'store' (str: jewel, cvs, pet_store, other)"
        )),
    ],
) -> str:
    ...
```
**Warning signs:** Agent produces malformed tool calls or errors during schema validation.
**Confidence:** MEDIUM -- the existing `file_capture` tool uses simple types (str, float), not complex models. Following that pattern is safer.

### Pitfall 4: Admin Agent Environment Variable Not Set
**What goes wrong:** Backend crashes on startup because `AZURE_AI_ADMIN_AGENT_ID` is empty and `ensure_admin_agent` creates a new agent, but the ID is not persisted to the env.
**Why it happens:** Same pattern as Classifier -- first deployment creates the agent, logs the ID, and you must manually update the env var.
**How to avoid:** Make the Admin Agent registration non-fatal initially. Log the new agent ID clearly. The first deployment will create the agent; subsequent deployments use the stored ID.
**Warning signs:** "NEW Admin agent: id=asst_xxx" log message on every restart (means the ID is not being stored).
**Confidence:** HIGH -- this is exactly what happened with the Classifier agent.

### Pitfall 5: Container Not Created Before Deployment
**What goes wrong:** `CosmosManager.initialize()` calls `get_container_client("ShoppingLists")` which does not create the container -- it just gets a reference. If the container doesn't exist, the first `create_item()` call fails with `CosmosResourceNotFoundError`.
**Why it happens:** `get_container_client()` is a lazy operation that doesn't validate the container exists. The error only surfaces at write time.
**How to avoid:** Create the ShoppingLists container BEFORE deploying the code. This is a manual step (same as the existing 5 containers were created manually).
**Warning signs:** `CosmosResourceNotFoundError` on the first Admin Agent tool call after deployment.
**Confidence:** HIGH -- confirmed from codebase analysis. `CosmosManager.initialize()` uses `get_container_client()`, not `create_container_if_not_exists()`.

### Pitfall 6: Integration Tests Forget Different Partition Key
**What goes wrong:** Integration tests use `partition_key="will"` for cleanup/assertions on ShoppingLists items. Reads return nothing, deletes fail silently, test items accumulate.
**Why it happens:** Copy-pasting from existing test patterns (e.g., `test_cosmos_crud.py`).
**How to avoid:** Integration tests for ShoppingLists must:
1. Use the store name as partition_key for all operations
2. Track created item IDs and store values
3. Delete each item with `delete_item(item=item_id, partition_key=store_name)` in a finally block
**Warning signs:** Test items accumulating in ShoppingLists container across runs.
**Confidence:** HIGH -- existing tests all use `partition_key="will"` which would be wrong for ShoppingLists.

## Code Examples

Verified patterns from the existing codebase:

### Extending CosmosManager
```python
# Source: backend/src/second_brain/db/cosmos.py
# Change: Add "ShoppingLists" to the CONTAINER_NAMES list
CONTAINER_NAMES: list[str] = [
    "Inbox", "People", "Projects", "Ideas", "Admin", "ShoppingLists"
]
# No other changes needed -- initialize() already loops over CONTAINER_NAMES
```

### ShoppingListItem Pydantic Model
```python
# Source: Pattern from backend/src/second_brain/models/documents.py
from uuid import uuid4
from pydantic import BaseModel, Field

KNOWN_STORES: list[str] = ["jewel", "cvs", "pet_store", "other"]

class ShoppingListItem(BaseModel):
    """Individual shopping list item in the ShoppingLists Cosmos container.

    Partition key is /store. Items exist until deleted (no status tracking).
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    store: str  # Partition key value: "jewel", "cvs", "pet_store", "other"
    name: str   # Full natural language: "2 lbs ground beef"
```

### AdminTools add_shopping_list_items
```python
# Source: Pattern from ClassifierTools in tools/classification.py
from agent_framework import tool
from typing import Annotated
from pydantic import Field
from second_brain.db.cosmos import CosmosManager
from second_brain.models.documents import ShoppingListItem, KNOWN_STORES

class AdminTools:
    """Admin agent tools bound to a CosmosManager instance."""

    def __init__(self, cosmos_manager: CosmosManager) -> None:
        self._manager = cosmos_manager

    @tool(approval_mode="never_require")
    async def add_shopping_list_items(
        self,
        items: Annotated[
            list[dict],
            Field(description=(
                "List of shopping items to add. Each dict must have "
                "'name' (str, lowercase, natural language) and "
                "'store' (str: jewel, cvs, pet_store, or other)"
            )),
        ],
    ) -> str:
        """Add items to shopping lists. Items are grouped by store."""
        container = self._manager.get_container("ShoppingLists")
        store_counts: dict[str, int] = {}

        for item_data in items:
            name = item_data.get("name", "").strip().lower()
            store = item_data.get("store", "other").strip().lower()

            # Validate store -- fall back to "other" silently
            if store not in KNOWN_STORES:
                store = "other"

            doc = ShoppingListItem(store=store, name=name)
            await container.create_item(body=doc.model_dump())
            store_counts[store] = store_counts.get(store, 0) + 1

        total = sum(store_counts.values())
        breakdown = ", ".join(
            f"{count} to {store}" for store, count in store_counts.items()
        )
        return f"Added {total} items: {breakdown}"
```

### Admin Agent Client Configuration in Lifespan
```python
# Source: Pattern from main.py lines 130-199
# In the lifespan, after Classifier setup:

# --- Admin Agent Registration ---
admin_agent_id = await ensure_admin_agent(
    foundry_client=foundry_client,
    stored_agent_id=settings.azure_ai_admin_agent_id,
)
app.state.admin_agent_id = admin_agent_id

# --- AdminTools ---
admin_tools = AdminTools(cosmos_manager=cosmos_mgr)
app.state.admin_tools = admin_tools

# --- Admin AzureAIAgentClient (separate from Classifier) ---
admin_client = AzureAIAgentClient(
    credential=credential,
    project_endpoint=settings.azure_ai_project_endpoint,
    agent_id=admin_agent_id,
    should_cleanup_agent=False,
    middleware=[AuditAgentMiddleware(), ToolTimingMiddleware()],
)
app.state.admin_client = admin_client
app.state.admin_agent_tools = [admin_tools.add_shopping_list_items]
```

### Integration Test Pattern
```python
# Source: Pattern from tests/test_classifier_integration.py
import os
import pytest
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from second_brain.models.documents import ShoppingListItem

_SKIP_REASON = "Integration test requires COSMOS_ENDPOINT"
_has_cosmos = bool(os.environ.get("COSMOS_ENDPOINT"))

@pytest.mark.integration
@pytest.mark.skipif(not _has_cosmos, reason=_SKIP_REASON)
async def test_add_shopping_list_items_writes_to_cosmos():
    """AdminTools.add_shopping_list_items writes items to real Cosmos DB."""
    credential = DefaultAzureCredential()
    created_items = []

    try:
        # Setup real Cosmos client
        cosmos_client = CosmosClient(
            url=os.environ["COSMOS_ENDPOINT"],
            credential=credential,
        )
        database = cosmos_client.get_database_client("second-brain")
        container = database.get_container_client("ShoppingLists")

        # Create AdminTools with real CosmosManager
        from second_brain.db.cosmos import CosmosManager
        manager = CosmosManager(
            endpoint=os.environ["COSMOS_ENDPOINT"],
            database_name="second-brain",
        )
        await manager.initialize()

        from second_brain.tools.admin import AdminTools
        admin_tools = AdminTools(cosmos_manager=manager)

        # Call the tool directly
        result = await admin_tools.add_shopping_list_items(
            items=[
                {"name": "test milk", "store": "jewel"},
                {"name": "test bandages", "store": "cvs"},
            ]
        )

        assert "Added 2 items" in result
        assert "jewel" in result
        assert "cvs" in result

        # Verify items exist in Cosmos
        async for item in container.query_items(
            query="SELECT * FROM c WHERE c.name = @name",
            parameters=[{"name": "@name", "value": "test milk"}],
            partition_key="jewel",
        ):
            created_items.append(("jewel", item["id"]))

        assert len(created_items) >= 1

    finally:
        # Cleanup
        for store, item_id in created_items:
            try:
                await container.delete_item(item=item_id, partition_key=store)
            except Exception:
                pass
        await manager.close()
        await credential.close()
```

### Creating ShoppingLists Container (Azure CLI)
```bash
# Create the container BEFORE deploying the code
az cosmosdb sql container create \
  --account-name <your-cosmos-account> \
  --database-name second-brain \
  --name ShoppingLists \
  --partition-key-path "/store" \
  --resource-group shared-services-rg
# NOTE: Do NOT pass --throughput for serverless accounts
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Embedded arrays per store doc | Individual item documents | Decided in CONTEXT.md | Atomic creates/deletes, no race conditions, aligns with serverless pricing model |
| `/userId` partition key | `/store` partition key for ShoppingLists | Decided in CONTEXT.md | Efficient per-store queries without cross-partition reads |
| Create containers in code | Create containers externally, code gets references | Phase 1 research finding | Cleaner separation, no runtime Cosmos admin operations |

**Deprecated/outdated:**
- Earlier architecture research (ARCHITECTURE.md) suggested one-document-per-store with embedded item arrays. CONTEXT.md overrides this with individual item documents. The research rationale was valid for embedded arrays, but the user chose individual docs for atomicity.

## Open Questions

1. **Cosmos Account Name for CLI Container Creation**
   - What we know: The Cosmos endpoint is in `.env`, account is in `shared-services-rg`
   - What's unclear: Exact Cosmos account name for the `az cosmosdb sql container create` command
   - Recommendation: Derive from COSMOS_ENDPOINT env var or check Azure Portal. The planner should include a task to create the container as a prerequisite.

2. **Store Name Casing Convention**
   - What we know: CONTEXT.md says "Jewel, CVS, Pet store" with mixed casing. Code needs consistent keys.
   - What's unclear: Whether store values should be lowercase slugs ("jewel", "cvs", "pet_store") or display names ("Jewel", "CVS", "Pet Store")
   - Recommendation: Use lowercase slugs as partition key values and Cosmos document field values. Store display names in agent instructions only. This avoids casing inconsistencies and makes partition keys simple. The KNOWN_STORES constant should use lowercase: `["jewel", "cvs", "pet_store", "other"]`.

3. **Admin Agent Instructions Content**
   - What we know: Instructions include both category rules and specific examples for store routing. Managed in Foundry portal.
   - What's unclear: Exact wording -- but this is Claude's discretion per CONTEXT.md
   - Recommendation: Write instructions that cover: (1) role description, (2) store routing rules with categories and examples, (3) item formatting rules (lowercase, natural language), (4) how to use the add_shopping_list_items tool. Deliver as a documented block that the user can paste into the Foundry portal.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `backend/src/second_brain/db/cosmos.py` -- CosmosManager pattern, CONTAINER_NAMES, get_container_client usage
- Existing codebase: `backend/src/second_brain/tools/classification.py` -- ClassifierTools @tool pattern, class structure
- Existing codebase: `backend/src/second_brain/agents/classifier.py` -- ensure_classifier_agent() pattern
- Existing codebase: `backend/src/second_brain/main.py` -- Lifespan pattern for agent client initialization, tool list configuration
- Existing codebase: `backend/src/second_brain/config.py` -- Settings pattern for new env vars
- Existing codebase: `backend/tests/test_classifier_integration.py` -- Integration test pattern with real Azure services
- [Azure Cosmos DB Serverless docs](https://learn.microsoft.com/en-us/azure/cosmos-db/serverless) -- "You can't pass any throughput when you create a serverless container"
- [AzureAIAgentClient API Reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.azure.azureaiagentclient?view=agent-framework-python-latest) -- Constructor parameters: agent_id, should_cleanup_agent, credential, project_endpoint

### Secondary (MEDIUM confidence)
- [Azure Cosmos DB Python SDK - Create Container](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/how-to-python-create-container) -- create_container_if_not_exists pattern, async variant
- [Azure Cosmos DB Python SDK - Container Management Samples](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/cosmos/azure-cosmos/samples/container_management.py) -- partition_key parameter patterns
- Phase 1 research (`.planning/phases/01-backend-foundation/01-RESEARCH.md`) -- serverless Cosmos DB confirmation, container provisioning approach
- Project research (`.planning/research/PITFALLS.md`) -- individual item documents recommendation, partition key analysis

### Tertiary (LOW confidence)
- None. All findings are verified against existing codebase or official Azure documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and proven in the project
- Architecture: HIGH -- all patterns directly mirror existing codebase (ClassifierTools, ensure_classifier_agent, CosmosManager)
- Pitfalls: HIGH -- derived from codebase analysis and confirmed serverless Cosmos behavior from official docs

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable -- no fast-moving dependencies)
