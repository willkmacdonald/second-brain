# Phase 16: Query Foundation - Research

**Researched:** 2026-04-05
**Domain:** Azure Monitor programmatic queries (LogsQueryClient) + Cosmos DB eval data containers
**Confidence:** HIGH

## Summary

Phase 16 establishes two infrastructure capabilities: (1) programmatic KQL queries against the Log Analytics workspace via `azure-monitor-query` SDK, and (2) three new Cosmos DB containers (Feedback, EvalResults, GoldenDataset) with Pydantic document models. This is pure infrastructure with no user-facing features -- it enables Phases 17-22.

The `azure-monitor-query` SDK v2.0.0 provides an async `LogsQueryClient` that integrates cleanly with the existing FastAPI async patterns and `DefaultAzureCredential` already in use. The key migration task is converting the four existing `.kql` template files from portal schema (`AppTraces`/`AppRequests`) to workspace schema (`traces`/`requests`), with corresponding field name changes (e.g., `SeverityLevel` to `severityLevel`, `TimeGenerated` to `timestamp`).

The Cosmos containers follow the same creation pattern established in Phase 12 (archive scripts). The new containers need Pydantic models that are self-contained documents (no joins), matching the CONTEXT.md decisions.

**Primary recommendation:** Add `azure-monitor-query>=2.0.0` as a dependency, create an `observability/` module with async query functions, migrate KQL templates to workspace schema, and create three new Cosmos containers with Pydantic models.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Templates for known patterns (trace lookup, recent failures, system health, admin audit) + LLM-generated KQL fallback for novel questions with schema grounding
- Agent executes generated KQL directly -- no approval step before running (read-only workspace access)
- Default time range: 24 hours when not specified
- Existing .kql files from Phase 14 need workspace-compatible equivalents
- GoldenDataset: individual documents per test case (not a single dataset document). Easy to add/remove/query.
- Feedback: full capture snapshot in each signal document (capture text, original bucket, correction). Self-contained for analysis, no joins needed.
- EvalResults: each eval run stores both aggregate scores AND individual case results in a single document. One doc per eval run.
- New `observability/` module under `backend/src/second_brain/` -- clean separation from capture/classification code
- Async functions (matching FastAPI pattern). LogsQueryClient async variant.
- Partial query results: flag + return (warning flag, let consumer decide if partial is acceptable)
- Pydantic models for query results (TraceResult, HealthSummary, etc.)
- DefaultAzureCredential for LogsQueryClient (managed identity in production, az login locally)
- Log Analytics Reader RBAC role assignment for Container App managed identity -- set up in this phase via az CLI
- Log Analytics workspace ID configured as environment variable (LOG_ANALYTICS_WORKSPACE_ID) -- not a secret, safe as plain config

### Claude's Discretion
- KQL schema migration strategy (workspace-only vs maintaining both portal and workspace versions)
- Partition key strategy for new Cosmos containers (userId consistency vs domain-specific keys)
- Exact Pydantic model shapes for query results
- LogsQueryClient initialization and lifecycle management

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `azure-monitor-query` | `>=2.0.0` | Programmatic KQL queries against Log Analytics workspace | Official Azure SDK. GA since 2025-07-30. Provides async `LogsQueryClient` under `azure.monitor.query.aio`. Integrates with `DefaultAzureCredential`. |
| `azure-cosmos` | (existing) | Cosmos DB container creation and document CRUD | Already a project dependency. Used for all existing containers. |
| `azure-identity` | (existing) | `DefaultAzureCredential` for both LogsQueryClient and Cosmos | Already a project dependency. Shared credential in lifespan. |
| `pydantic` | (existing via `pydantic-settings`) | Document models for new Cosmos containers and query result shapes | Already used throughout project for all models. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `aiohttp` | (existing) | Async HTTP transport required by async `LogsQueryClient` | Already a project dependency -- required for async Azure SDK clients. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `azure-monitor-query` async | `azure-monitor-query` sync | Sync would block FastAPI event loop. Must use async variant. |
| `query_workspace()` | `query_resource()` | `query_resource()` uses a resource ARM ID instead of workspace ID. Both work, but workspace ID is simpler for this use case and matches the existing RBAC setup. |

**Installation:**
```bash
uv pip install "azure-monitor-query>=2.0.0"
```

**Note:** No new `pandas` dependency needed. The SDK returns `LogsTable` objects with `.rows` (list of `LogsTableRow`) and `.columns` (list of str). Parse into Pydantic models directly.

## Architecture Patterns

### Recommended Project Structure
```
backend/src/second_brain/
├── observability/           # NEW: Phase 16 module
│   ├── __init__.py
│   ├── client.py            # LogsQueryClient lifecycle (init/close)
│   ├── queries.py           # Async query functions (trace_lookup, recent_failures, etc.)
│   ├── kql_templates.py     # KQL template strings with parameter substitution
│   └── models.py            # Pydantic models for query results
├── models/
│   └── documents.py         # ADD: FeedbackDocument, EvalResultsDocument, GoldenDatasetDocument
├── db/
│   └── cosmos.py            # UPDATE: Add new container names to CONTAINER_NAMES list
└── main.py                  # UPDATE: Initialize LogsQueryClient in lifespan
```

### Pattern 1: LogsQueryClient Lifecycle Management
**What:** Initialize LogsQueryClient in FastAPI lifespan, reusing the existing `DefaultAzureCredential`, and close it on shutdown.
**When to use:** For all programmatic KQL queries from the backend.
**Example:**
```python
# Source: https://learn.microsoft.com/python/api/azure-monitor-query/azure.monitor.query.aio.logsqueryclient
from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient

# In lifespan (main.py):
credential = AsyncDefaultAzureCredential()  # already exists
logs_client = LogsQueryClient(credential)
app.state.logs_client = logs_client

# Cleanup:
await logs_client.close()  # before credential.close()
```

**Recommendation (Claude's discretion):** Store `LogsQueryClient` on `app.state` like every other client. Create it during lifespan startup using the already-existing credential. Close it before the credential in the shutdown path. Do NOT create a separate credential -- reuse the one already created in lifespan.

### Pattern 2: Query Execution with Partial Result Detection
**What:** Execute KQL queries and explicitly handle partial results per the success criteria.
**When to use:** Every query function must check `LogsQueryStatus`.
**Example:**
```python
# Source: https://learn.microsoft.com/python/api/overview/azure/monitor-query-readme
from datetime import timedelta
from azure.monitor.query import LogsQueryStatus
from azure.monitor.query.aio import LogsQueryClient

async def execute_kql(
    client: LogsQueryClient,
    workspace_id: str,
    query: str,
    timespan: timedelta = timedelta(hours=24),
) -> QueryResult:
    response = await client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=timespan,
        server_timeout=60,
    )

    if response.status == LogsQueryStatus.SUCCESS:
        return QueryResult(
            tables=_parse_tables(response.tables),
            is_partial=False,
        )
    elif response.status == LogsQueryStatus.PARTIAL:
        return QueryResult(
            tables=_parse_tables(response.partial_data),
            is_partial=True,
            partial_error=str(response.partial_error),
        )
```

### Pattern 3: KQL Template Parameter Substitution
**What:** Store KQL templates as Python string constants with named placeholders, substituted at call time.
**When to use:** For the four known query patterns (trace lookup, recent failures, system health, admin audit).
**Example:**
```python
# kql_templates.py
CAPTURE_TRACE = """
let trace_id = "{trace_id}";
union traces, dependencies, requests, exceptions
| where customDimensions.capture_trace_id == trace_id
    or customDimensions["capture_trace_id"] == trace_id
| project
    timestamp,
    itemType,
    severityLevel,
    message = coalesce(message, name, type),
    component = tostring(customDimensions.component),
    details = customDimensions
| order by timestamp asc
"""
```

**Important:** Use Python f-string or `.format()` substitution for parameters like trace_id. KQL `let` variables work too but the Python-side substitution is cleaner for single-parameter templates. For LLM-generated KQL (future Phase 17), the query string is passed through directly.

### Pattern 4: Cosmos Container Creation Script
**What:** Standalone async script to create new Cosmos containers, following the existing pattern from `backend/scripts/archive/create_tasks_container.py`.
**When to use:** One-time infra setup, run manually via `python3 backend/scripts/create_eval_containers.py`.
**Example:**
```python
# Following established pattern from create_tasks_container.py
CONTAINERS = [
    {"name": "Feedback", "partition_key": "/userId"},
    {"name": "EvalResults", "partition_key": "/userId"},
    {"name": "GoldenDataset", "partition_key": "/userId"},
]

async def create_containers() -> None:
    # ... credential + client setup (same as existing script)
    for spec in CONTAINERS:
        try:
            await database.create_container(
                id=spec["name"],
                partition_key={"paths": [spec["partition_key"]], "kind": "Hash"},
            )
        except CosmosResourceExistsError:
            logger.info("Container '%s' already exists", spec["name"])
```

**Recommendation (Claude's discretion -- partition keys):** Use `/userId` for all three new containers, consistent with most existing containers (Inbox, People, Projects, Ideas, Admin, Tasks, Destinations, AffinityRules). This is a single-user system -- `userId` is always `"will"`. Domain-specific partition keys (e.g., `/evalRunId`) add no benefit because there is no multi-user query isolation needed and queries will never cross partition boundaries meaningfully at this data volume.

### Anti-Patterns to Avoid
- **Creating LogsQueryClient per-request:** The client is lightweight but shares an HTTP session. Create once in lifespan, reuse across requests.
- **Using portal table names in workspace queries:** `AppTraces`/`AppRequests` work in the portal query editor but the workspace-based queries should use `traces`/`requests` for correctness and clarity. The field names also differ.
- **Ignoring partial results:** The SDK returns `LogsQueryPartialResult` when the server couldn't fully complete the query (e.g., timeout, data limits). Silently treating partial as complete violates success criterion #3.
- **Adding pandas dependency:** The SDK examples use pandas for demonstration. We do NOT need pandas -- iterate `LogsTable.rows` directly and map to Pydantic models.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| KQL execution against Log Analytics | Custom REST client to the Log Analytics API | `azure-monitor-query` SDK `LogsQueryClient` | SDK handles auth token refresh, retry policies, response parsing, and version management |
| Partial result detection | Custom HTTP response code inspection | SDK's `LogsQueryStatus.PARTIAL` and `LogsQueryPartialResult` | Partial results have a specific API contract; SDK models it correctly |
| Azure AD token acquisition | Manual token endpoint calls | `DefaultAzureCredential` (existing) | Handles managed identity, az login, env var fallback automatically |
| Cosmos container provisioning | Azure Portal manual creation | Python script with `azure-cosmos` SDK | Reproducible, idempotent (handles `CosmosResourceExistsError`), follows existing project pattern |

**Key insight:** The `azure-monitor-query` SDK is thin but handles critical edge cases -- token refresh during long queries, proper timespan serialization, and the partial result contract. Rolling a custom REST client would require reimplementing all of these.

## Common Pitfalls

### Pitfall 1: Portal vs Workspace Table/Field Names
**What goes wrong:** KQL queries that work in the App Insights portal query editor fail or return unexpected results when executed via `LogsQueryClient.query_workspace()`.
**Why it happens:** Workspace-based App Insights uses different table and field names than the portal experience. The existing `.kql` files use portal names (`AppTraces`, `AppRequests`, `SeverityLevel`, `TimeGenerated`).
**How to avoid:** Migrate all templates to workspace schema. Reference table below.
**Warning signs:** Empty result sets or `BadArgumentError` from queries that worked in the portal.

**Complete table name mapping (Application Insights portal -> Log Analytics workspace):**

| Portal Name | Workspace Name |
|-------------|---------------|
| `AppTraces` | `traces` |
| `AppRequests` | `requests` |
| `AppDependencies` | `dependencies` |
| `AppExceptions` | `exceptions` |
| `AppEvents` | `customEvents` |
| `AppMetrics` | `customMetrics` |
| `AppPageViews` | `pageViews` |
| `AppPerformanceCounters` | `performanceCounters` |
| `AppAvailabilityResults` | `availabilityResults` |
| `AppBrowserTimings` | `browserTimings` |

**Key field name mapping (portal -> workspace):**

| Portal Field | Workspace Field | Tables |
|-------------|----------------|--------|
| `TimeGenerated` | `timestamp` | All |
| `SeverityLevel` (int) | `severityLevel` (int) | traces, exceptions |
| `Message` (capital) | `message` (lowercase) | traces |
| `Name` (capital) | `name` (lowercase) | requests, dependencies |
| `DurationMs` | `duration` | requests, dependencies |
| `ResultCode` | `resultCode` | requests |
| `Success` | `success` | requests |
| `customDimensions` | `customDimensions` | Same in both |
| `itemType` | `itemType` | Same in both |

**Source:** https://learn.microsoft.com/azure/azure-monitor/app/data-model-complete (HIGH confidence -- official Microsoft docs, verified 2026-04-05)

### Pitfall 2: LogsQueryClient Context Manager vs Manual Close
**What goes wrong:** Credential or HTTP connections leak if `LogsQueryClient` is used without proper cleanup.
**Why it happens:** The SDK examples show `async with client:` context manager usage, which calls `close()` automatically. In FastAPI lifespan, we cannot use a context manager because the client must persist across the entire app lifetime.
**How to avoid:** Manually call `await logs_client.close()` in the lifespan shutdown path, BEFORE closing the credential. The existing pattern in `main.py` already does this for `CosmosClient`, `OpenAI client`, etc.
**Warning signs:** "Unclosed client session" warnings in logs.

### Pitfall 3: Timespan Parameter is Required
**What goes wrong:** `query_workspace()` raises `TypeError` if `timespan` is omitted without explicitly passing `None`.
**Why it happens:** The `timespan` parameter is a required keyword-only argument in the SDK signature. Setting it to `None` disables the time constraint; omitting it entirely is an error.
**How to avoid:** Always pass `timespan`. Default to `timedelta(hours=24)` per CONTEXT.md decision. Pass `timespan=None` only if the query itself includes a time filter via `| where timestamp > ago(...)`.
**Warning signs:** `TypeError: query_workspace() missing 1 required keyword-only argument: 'timespan'`

### Pitfall 4: Server Timeout vs Client Timeout
**What goes wrong:** Long-running KQL queries time out with a gateway error.
**Why it happens:** Default server timeout is 180 seconds. For queries scanning large time ranges, this can be insufficient.
**How to avoid:** Set `server_timeout=60` for standard queries (more than enough for 24h scans on a single-user app). The maximum is 600 seconds (10 minutes). If a query consistently times out, the KQL needs optimization (add time filters, reduce `take` limits).
**Warning signs:** `HttpResponseError` with timeout-related messages.

### Pitfall 5: RBAC Permission Delays
**What goes wrong:** RBAC role assignment succeeds but `LogsQueryClient` queries fail with 403 Forbidden.
**Why it happens:** Azure RBAC propagation can take up to 5-10 minutes after assignment. Also, if the Container App's managed identity doesn't have the correct scope (workspace vs subscription).
**How to avoid:** Assign "Log Analytics Reader" role to the Container App's system-assigned managed identity scoped to the specific Log Analytics workspace resource. Wait a few minutes before testing. Verify with `az role assignment list`.
**Warning signs:** 403 errors from `query_workspace()` immediately after role assignment.

## Code Examples

Verified patterns from official sources:

### Async LogsQueryClient Initialization and Query
```python
# Source: https://learn.microsoft.com/python/api/azure-monitor-query/azure.monitor.query.aio.logsqueryclient
from datetime import timedelta

from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient
from azure.monitor.query import LogsQueryStatus

async def query_recent_failures(
    client: LogsQueryClient,
    workspace_id: str,
) -> list[dict]:
    """Query ERROR+ logs and exceptions from the last 24 hours."""
    query = """
    traces
    | where severityLevel >= 3
    | union (exceptions)
    | where timestamp > ago(24h)
    | project
        timestamp,
        itemType,
        severityLevel,
        message = coalesce(message, type),
        component = tostring(customDimensions.component),
        captureTraceId = tostring(customDimensions.capture_trace_id)
    | order by timestamp desc
    | take 50
    """
    response = await client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=timedelta(hours=24),
    )

    results = []
    if response.status == LogsQueryStatus.SUCCESS:
        for table in response.tables:
            for row in table.rows:
                results.append(dict(zip(table.columns, row)))
    elif response.status == LogsQueryStatus.PARTIAL:
        for table in response.partial_data:
            for row in table.rows:
                results.append(dict(zip(table.columns, row)))

    return results
```

### Parsing LogsTable Rows into Pydantic Models
```python
# Pattern for converting SDK table results to typed Pydantic models
from pydantic import BaseModel

class TraceRecord(BaseModel):
    timestamp: str
    item_type: str
    severity_level: int | None = None
    message: str
    component: str | None = None
    capture_trace_id: str | None = None

def parse_trace_table(table) -> list[TraceRecord]:
    """Convert a LogsTable to a list of typed TraceRecord models."""
    records = []
    for row in table.rows:
        row_dict = dict(zip(table.columns, row))
        records.append(TraceRecord(
            timestamp=str(row_dict.get("timestamp", "")),
            item_type=str(row_dict.get("itemType", "")),
            severity_level=row_dict.get("severityLevel"),
            message=str(row_dict.get("message", "")),
            component=row_dict.get("component"),
            capture_trace_id=row_dict.get("captureTraceId"),
        ))
    return records
```

### Cosmos Container Creation (Following Existing Pattern)
```python
# Source: Existing project pattern from backend/scripts/archive/create_tasks_container.py
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError
from azure.identity.aio import DefaultAzureCredential

async def create_eval_containers() -> None:
    credential = DefaultAzureCredential()
    client = CosmosClient(url=endpoint, credential=credential)
    try:
        database = client.get_database_client("second-brain")
        for name, pk_path in [
            ("Feedback", "/userId"),
            ("EvalResults", "/userId"),
            ("GoldenDataset", "/userId"),
        ]:
            try:
                await database.create_container(
                    id=name,
                    partition_key={"paths": [pk_path], "kind": "Hash"},
                )
            except CosmosResourceExistsError:
                pass
    finally:
        await client.close()
        await credential.close()
```

## KQL Migration Reference

### Existing .kql Files Requiring Migration

All four files in `backend/queries/` use portal schema and need workspace-compatible equivalents:

**1. `capture-trace.kql`** -- traces a capture lifecycle by trace ID
- Portal: `union AppTraces, AppDependencies, AppRequests, AppExceptions`
- Workspace: `union traces, dependencies, requests, exceptions`
- Field changes: `TimeGenerated` -> `timestamp`, `SeverityLevel` -> `severityLevel`, `Message`/`message` -> `message`, `name` -> `name` (already lowercase in workspace)

**2. `recent-failures.kql`** -- ERROR+ logs from last 24h
- Portal: `union AppTraces, AppExceptions`
- Workspace: `union traces, exceptions` (note: `union` with `exceptions` may need to alias `type` to `exceptionType`)
- Field changes: same as above

**3. `system-health.kql`** -- multi-section health overview
- Portal: `AppRequests`, `AppTraces`
- Workspace: `requests`, `traces`
- Field changes: `name` stays lowercase, `resultCode` stays, `duration` stays

**4. `admin-agent-audit.kql`** -- Admin Agent processing activity
- Portal: `AppTraces`
- Workspace: `traces`
- Field changes: same pattern

**Recommendation (Claude's discretion -- migration strategy):** Migrate to workspace-only. The portal .kql files were for manual copy-paste into the App Insights query editor. Going forward, queries will be executed programmatically via `LogsQueryClient.query_workspace()` which uses the workspace schema. Keep the original .kql files in `backend/queries/` as reference/archive. Put the new workspace-compatible templates in `backend/src/second_brain/observability/kql_templates.py` as Python string constants.

**Note from STATE.md:** "KQL programmatic queries use workspace schema (traces/requests), NOT portal schema (AppTraces/AppRequests)" -- this is an existing project decision confirming workspace-only.

## Cosmos Document Models (Recommended Shapes)

### FeedbackDocument
```python
class FeedbackDocument(BaseModel):
    """Quality signal document -- self-contained capture snapshot.

    Each document captures a complete signal: what was captured, how it was
    classified, and what correction (if any) the user made.
    Partition key: /userId
    """
    id: str  # uuid
    userId: str = "will"
    signalType: str  # "recategorize", "hitl_bucket", "errand_reroute", "thumbs_up", "thumbs_down"
    captureText: str  # Original raw text of the capture
    originalBucket: str  # What classifier assigned
    correctedBucket: str | None = None  # What user changed it to (None for thumbs_up)
    captureTraceId: str | None = None  # Links back to App Insights telemetry
    createdAt: datetime  # When the feedback signal was generated
```

### GoldenDatasetDocument
```python
class GoldenDatasetDocument(BaseModel):
    """Individual test case for classifier evaluation.

    One document per test case. Easy to add/remove/query.
    Partition key: /userId
    """
    id: str  # uuid
    userId: str = "will"
    inputText: str  # The capture text to classify
    expectedBucket: str  # Known-correct bucket label
    source: str  # "manual", "promoted_feedback", "synthetic"
    tags: list[str] = []  # Optional grouping: "edge_case", "voice", "recipe"
    createdAt: datetime
    updatedAt: datetime
```

### EvalResultsDocument
```python
class EvalResultsDocument(BaseModel):
    """Single eval run with both aggregate scores and individual results.

    One document per eval run. Contains the full picture.
    Partition key: /userId
    """
    id: str  # uuid
    userId: str = "will"
    evalType: str  # "classifier", "admin_agent"
    runTimestamp: datetime  # When the eval started
    datasetSize: int  # How many test cases were evaluated
    aggregateScores: dict  # {"accuracy": 0.92, "precision": {...}, "recall": {...}}
    individualResults: list[dict]  # [{"input": "...", "expected": "...", "actual": "...", "correct": bool}]
    modelDeployment: str  # "gpt-4o" -- which model was used
    notes: str | None = None  # Optional annotation
    createdAt: datetime
```

## RBAC Setup

### Log Analytics Reader Role Assignment

The Container App's system-assigned managed identity needs "Log Analytics Reader" role on the Log Analytics workspace.

```bash
# Get the workspace resource ID
WORKSPACE_RESOURCE_ID=$(az monitor app-insights component show \
    --app second-brain-insights \
    --resource-group shared-services-rg \
    --query "workspaceResourceId" -o tsv)

# Get the Container App's managed identity principal ID
PRINCIPAL_ID=$(az containerapp show \
    --name second-brain-api \
    --resource-group shared-services-rg \
    --query "identity.principalId" -o tsv)

# Assign Log Analytics Reader role
az role assignment create \
    --assignee "$PRINCIPAL_ID" \
    --role "Log Analytics Reader" \
    --scope "$WORKSPACE_RESOURCE_ID"
```

**Note:** This follows the same pattern used in Phase 12.3 for Cosmos RBAC. The `Log Analytics Reader` built-in role (ID: `73c42c96-874c-492b-b04d-ab87d138a893`) grants read-only access to query data. It does NOT allow modifying workspace settings, which is exactly the security posture we want.

### Log Analytics Workspace ID

Retrieve the workspace ID (not the resource ID) for use as `LOG_ANALYTICS_WORKSPACE_ID` env var:

```bash
# Get the workspace ID (GUID) -- this is what LogsQueryClient needs
az monitor log-analytics workspace show \
    --workspace-name <workspace-name> \
    --resource-group shared-services-rg \
    --query "customerId" -o tsv
```

Or from the App Insights resource:
```bash
# Get workspace resource ID, then extract the workspace GUID
WORKSPACE_RES_ID=$(az monitor app-insights component show \
    --app second-brain-insights \
    --resource-group shared-services-rg \
    --query "workspaceResourceId" -o tsv)

# Parse workspace name from resource ID and query it
# The customerId field is the Workspace ID (GUID)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `azure-monitor-query` v1.x with `MetricsQueryClient` | v2.0.0 split metrics to `azure-monitor-querymetrics` | July 2025 | No impact -- we only use logs queries |
| Portal table names (`AppTraces`) in KQL | Workspace table names (`traces`) | Workspace-based App Insights migration | Must use workspace names for `query_workspace()` |
| Classic Application Insights resources | Workspace-based resources | Ongoing Azure migration | `second-brain-insights` is already workspace-based |

**Deprecated/outdated:**
- `MetricsClient`/`MetricsQueryClient` removed from `azure-monitor-query` v2.0.0 (moved to `azure-monitor-querymetrics`). Not relevant -- we do not query metrics.

## Open Questions

1. **Log Analytics workspace name**
   - What we know: The workspace is linked to `second-brain-insights` in `shared-services-rg`. The workspace ID is a GUID obtained from the workspace's `customerId` property.
   - What's unclear: The exact workspace name to use in `az monitor log-analytics workspace show`. It was auto-created with the App Insights resource and may have a generated name.
   - Recommendation: Look up via `az monitor app-insights component show --app second-brain-insights --resource-group shared-services-rg --query "workspaceResourceId"` and extract from the resource ID path.

2. **Container App system-assigned managed identity status**
   - What we know: The app uses managed identity for Cosmos, Key Vault, and ACR access. System-assigned identity should already exist.
   - What's unclear: Whether it's system-assigned or user-assigned identity currently configured.
   - Recommendation: Verify with `az containerapp show --name second-brain-api --resource-group shared-services-rg --query "identity"` before assigning the RBAC role.

## Sources

### Primary (HIGH confidence)
- [azure-monitor-query v2.0.0 README](https://learn.microsoft.com/python/api/overview/azure/monitor-query-readme?view=azure-python) - SDK overview, examples, async client usage
- [LogsQueryClient async API reference](https://learn.microsoft.com/python/api/azure-monitor-query/azure.monitor.query.aio.logsqueryclient?view=azure-python) - Method signatures, return types, parameters
- [Application Insights telemetry data model](https://learn.microsoft.com/azure/azure-monitor/app/data-model-complete) - Complete table and field name mapping between portal and workspace schemas
- [Azure Cosmos DB create container Python](https://learn.microsoft.com/azure/cosmos-db/how-to-python-create-container) - Container creation with Python SDK
- [LogsTable/LogsTableRow API](https://learn.microsoft.com/python/api/azure-monitor-query/azure.monitor.query.logstable) - Table structure (columns, rows, column_types)
- [LogsQueryPartialResult](https://learn.microsoft.com/python/api/azure-monitor-query/azure.monitor.query.logsquerypartialresult) - Partial result handling

### Secondary (MEDIUM confidence)
- [Workspace-based Application Insights migration](https://learn.microsoft.com/azure/azure-monitor/app/apm-tables) - Table schema differences
- [Log Analytics API response format](https://learn.microsoft.com/azure/azure-monitor/logs/api/response-format) - Raw response structure

### Tertiary (LOW confidence)
- None -- all findings verified via official Microsoft docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Azure SDK, GA, verified via official docs and existing project research (STACK.md)
- Architecture: HIGH - Follows established project patterns (CosmosManager, lifespan client init, Pydantic models)
- KQL migration: HIGH - Official table/field mapping documented by Microsoft, confirmed by project STATE.md lessons learned
- Pitfalls: HIGH - Derived from SDK API contracts and official docs, cross-verified with existing project experiences
- Cosmos models: MEDIUM - Shapes are recommendations per Claude's discretion; final shapes may evolve during implementation

**Research date:** 2026-04-05
**Valid until:** 2026-05-05 (stable SDKs, low change velocity)
