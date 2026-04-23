# Phase 21: Eval Framework - Research

**Researched:** 2026-04-23
**Domain:** LLM agent evaluation / deterministic quality measurement
**Confidence:** HIGH

## Summary

Phase 21 builds a deterministic evaluation framework for the Classifier agent and Admin Agent. The architecture is straightforward: golden dataset documents in Cosmos are iterated sequentially, each sent through the real Foundry agents via the existing `agent_framework` SDK, and the returned bucket/destination is compared against ground truth. Results are stored in the EvalResults Cosmos container and surfaced through the investigation agent chat (mobile or Claude Code).

The heavy lifting is already done: `GoldenDatasetDocument`, `EvalResultsDocument`, and `FeedbackDocument` models are defined. The Feedback, EvalResults, and GoldenDataset Cosmos containers are provisioned. The `InvestigationTools` class already has `query_feedback_signals` and `promote_to_golden_dataset` tools. This phase adds (1) an eval runner module, (2) an eval API endpoint, (3) new investigation tools to trigger/view evals, (4) a dataset export/curation script, and (5) dry-run tool handlers for the Admin Agent eval.

**Primary recommendation:** Build the eval runner as a standalone module (`second_brain/eval/`) with separate classifier and admin evaluators. The runner accepts a `CosmosManager`, `AzureAIAgentClient`, and eval config, reads golden dataset entries, runs them sequentially through real agents, computes metrics, and writes results. The API endpoint kicks off the runner as a background task and returns a run ID. Two new investigation tools (`run_classifier_eval`, `run_admin_eval`) call the API endpoint internally.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Eval runner lives as a backend API endpoint (`/api/eval/run`) that kicks off the eval as a background task (`asyncio.create_task`), returns immediately with a run ID
- **D-02:** Classifier eval sends each golden dataset entry through the real Foundry Classifier agent (full thread creation + agent run), comparing the returned bucket against `expectedBucket` -- no direct GPT-4o shortcut
- **D-03:** Test cases run sequentially -- one agent call at a time, no concurrency. A 50-case run takes 3-5 minutes, which is acceptable for on-demand eval
- **D-04:** Admin Agent eval uses the same real-agent-run pattern but with dry-run tool handlers that intercept `add_errand_items` to check routing destination without writing to Cosmos
- **D-05:** Mobile trigger is via investigation agent command -- user says "run classifier eval" or "run admin eval" in the investigation chat. Agent calls a new @tool that hits the eval API endpoint. No new mobile UI screens needed
- **D-06:** Claude Code trigger is via the existing `/investigate` skill -- routes through the investigation agent on the deployed API, which calls the same eval @tool. No new MCP tool needed
- **D-07:** Results are displayed as a formatted investigation agent chat response (markdown with accuracy, per-bucket precision/recall table, failures highlighted). No dashboard cards in this phase
- **D-08:** Admin Agent eval focuses on routing accuracy only -- did items end up at the correct destination? No tool call sequence verification
- **D-09:** Admin Agent eval runs captures through the real Admin Agent with dry-run tool handlers -- intercepts tool calls to check what would have been routed without side effects
- **D-10:** Initial golden dataset is seeded by exporting real captures from Cosmos Inbox, manually curating/labeling them, then importing as GoldenDatasetDocuments with `source='manual'`
- **D-11:** The export/curation/import script is a deliverable within Phase 21 -- not pre-work
- **D-12:** Admin Agent golden dataset entries have `inputText` + `expectedDestination` -- routing accuracy only, no expected item extraction verification
- **D-13:** Admin Agent test cases require a known set of affinity rules as test fixtures to ensure deterministic expected destinations

### Claude's Discretion
- Eval status polling mechanism (SSE vs polling endpoint vs webhook)
- Classifier eval result formatting in the investigation agent response
- How the dry-run tool handler works for Admin Agent eval (mock tools, tool interception, or sandbox mode)
- Whether to add an `expectedDestination` field to GoldenDatasetDocument or use a separate AdminGoldenDatasetDocument model
- Export script output format (JSON file for human review before import)
- How to handle multi-bucket split captures in the classifier golden dataset (test the split detection, or treat as individual bucket tests)
- Confidence calibration metric calculation approach

### Deferred Ideas (OUT OF SCOPE)
- Eval scores dashboard card on Status screen (deferred from Phase 18)
- Eval results quick action chip on investigation chat (deferred from Phase 18)
- Tool call sequence verification for Admin Agent eval (deeper EVAL-03 compliance)
- Synthetic edge case generation for golden dataset expansion
- GitHub Actions eval workflow (belongs in Phase 22: Self-Monitoring Loop)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EVAL-01 | Golden dataset of 50+ test captures with known-correct bucket labels evaluates Classifier accuracy | Export/curation script (D-10, D-11), GoldenDatasetDocument model already defined, GoldenDataset Cosmos container provisioned |
| EVAL-02 | Classifier eval reports per-bucket precision/recall, overall accuracy, and confidence calibration | Eval runner module computes confusion matrix from sequential agent runs (D-02, D-03); metrics computed from file_capture tool call args |
| EVAL-03 | Admin Agent eval measures routing accuracy by destination and tool usage correctness | Dry-run tool handlers intercept add_errand_items to capture destination without writes (D-04, D-08, D-09); routing accuracy only per D-08 |
| EVAL-04 | Eval results are stored with timestamps for trend tracking (Cosmos + App Insights) | EvalResultsDocument model defined; write to EvalResults container + logger.info for App Insights |
| EVAL-05 | User can trigger an eval run on-demand from mobile or Claude Code | API endpoint (D-01) + investigation tools (D-05, D-06); polling endpoint for status |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Eval runner (agent invocation + metric computation) | API / Backend | -- | Must run on deployed backend with Foundry client access |
| Golden dataset CRUD | Database / Storage | API / Backend | Cosmos containers (GoldenDataset) read/written by backend |
| Eval results storage | Database / Storage | API / Backend | Cosmos EvalResults container + App Insights logs |
| Eval triggering | API / Backend | -- | `/api/eval/run` endpoint + investigation @tools |
| Result display | API / Backend | -- | Investigation agent formats markdown; no frontend changes |
| Dataset seeding script | API / Backend | -- | Python script using CosmosManager to export/import |
| Dry-run tool handlers | API / Backend | -- | Modified AdminTools that capture routing without Cosmos writes |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| agent-framework-azure-ai | 1.0.0rc2 | Foundry agent client for eval runs | Already in use; eval runner reuses same client pattern [VERIFIED: pip show] |
| azure-cosmos (async) | installed | Golden dataset + eval results storage | Already in use via CosmosManager [VERIFIED: cosmos.py] |
| fastapi | 0.133.1 | Eval API endpoint | Already in use [VERIFIED: pip show] |
| pydantic | installed | Document models (GoldenDatasetDocument, EvalResultsDocument) | Already defined in documents.py [VERIFIED: source code] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Unit tests for eval runner, dry-run tools, metrics | Already configured [VERIFIED: pip show] |
| pytest-asyncio | installed | Async test support | Already configured (asyncio_mode = "auto") [VERIFIED: pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom eval runner | azure-ai-evaluation SDK | Out of scope per REQUIREMENTS.md; no classification evaluator exists natively (confirmed Phase 19.3) |
| Polling endpoint | SSE for eval status | Polling is simpler; eval runs 3-5 min; SSE adds complexity for no benefit on single-user system |
| Separate AdminGoldenDatasetDocument | Extended GoldenDatasetDocument | Single model with optional `expectedDestination` field is simpler; `evalType` field on the document distinguishes classifier vs admin test cases |

**Installation:**
No new dependencies required. All libraries are already installed.

## Architecture Patterns

### System Architecture Diagram

```
User (mobile chat / Claude Code)
    |
    | "run classifier eval"
    v
Investigation Agent (@tool: run_classifier_eval)
    |
    | POST /api/eval/run {evalType: "classifier"}
    v
Eval API Endpoint
    |
    | asyncio.create_task(run_eval(...))
    | return {runId, status: "running"}
    v
Eval Runner (background task)
    |
    | 1. Read golden dataset from Cosmos (GoldenDataset container)
    | 2. For each test case:
    |    a. Create new thread
    |    b. Send inputText to Classifier agent via get_response()
    |    c. Parse file_capture tool call args (bucket, confidence)
    |    d. Compare predicted vs expectedBucket
    | 3. Compute aggregate metrics (accuracy, precision, recall, calibration)
    | 4. Write EvalResultsDocument to Cosmos (EvalResults container)
    | 5. Log results to App Insights
    v
Investigation Agent (@tool: get_eval_results)
    |
    | Read latest EvalResultsDocument from Cosmos
    | Format as markdown table
    v
User sees formatted results in chat
```

### Recommended Project Structure
```
backend/src/second_brain/
├── eval/                     # NEW: eval runner module
│   ├── __init__.py
│   ├── runner.py             # Core eval runner (classifier + admin)
│   ├── metrics.py            # Precision/recall/accuracy/calibration computation
│   └── dry_run_tools.py      # Dry-run AdminTools for eval
├── api/
│   └── eval.py               # NEW: /api/eval/run endpoint
├── tools/
│   └── investigation.py      # MODIFIED: add run_classifier_eval, run_admin_eval, get_eval_results
├── models/
│   └── documents.py          # EXISTING: GoldenDatasetDocument, EvalResultsDocument (no changes needed)
└── db/
    └── cosmos.py              # EXISTING: EvalResults, GoldenDataset containers (no changes needed)

backend/scripts/
└── seed_golden_dataset.py    # NEW: export/curate/import script
```

### Pattern 1: Background Task with Status Polling
**What:** Eval runs as `asyncio.create_task` in the background. The API endpoint returns immediately with a run ID. A separate status endpoint allows polling.
**When to use:** Long-running operations (3-5 min eval run) that shouldn't block the request.
**Example:**
```python
# Source: existing pattern in api/errands.py (admin processing)
from uuid import uuid4
import asyncio

# In-memory eval run tracking (single-user system)
_eval_runs: dict[str, dict] = {}

@router.post("/api/eval/run")
async def start_eval(request: Request, body: EvalRunRequest) -> dict:
    run_id = str(uuid4())
    _eval_runs[run_id] = {"status": "running", "started_at": datetime.now(UTC).isoformat()}
    
    task = asyncio.create_task(
        run_eval(
            run_id=run_id,
            eval_type=body.eval_type,
            cosmos_manager=request.app.state.cosmos_manager,
            classifier_client=request.app.state.classifier_client,
            classifier_tools=request.app.state.classifier_tools,
            runs_dict=_eval_runs,
        )
    )
    # Prevent GC of fire-and-forget task
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)
    
    return {"runId": run_id, "status": "running"}

@router.get("/api/eval/status/{run_id}")
async def eval_status(run_id: str) -> dict:
    run = _eval_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
```

### Pattern 2: Classifier Eval via Non-Streaming Agent Call
**What:** Send golden dataset text through the real Classifier agent, parse the `file_capture` tool call to extract predicted bucket and confidence.
**When to use:** Classifier eval (D-02).
**Example:**
```python
# Source: pattern from processing/admin_handoff.py (non-streaming agent call)
from agent_framework import ChatOptions, Message, FunctionTool

async def eval_single_classifier(
    client: AzureAIAgentClient,
    tools: list,  # [eval_file_capture] -- dry-run version
    input_text: str,
) -> dict:
    """Run a single classifier eval case. Returns predicted bucket + confidence."""
    messages = [Message(role="user", text=input_text)]
    options = ChatOptions(
        tools=tools,
        tool_choice={
            "mode": "required",
            "required_function_name": "file_capture",
        },
    )
    
    async with asyncio.timeout(60):
        response = await client.get_response(
            messages=messages, options=options
        )
    
    # Extract prediction from the dry-run file_capture tool
    # The tool captures args without writing to Cosmos
    return {
        "predicted_bucket": eval_tools.last_bucket,
        "confidence": eval_tools.last_confidence,
    }
```

### Pattern 3: Dry-Run Tool Handlers for Admin Agent Eval
**What:** Create modified versions of AdminTools that capture routing decisions (destination, items) without writing to Cosmos. The agent runs normally but the tool handlers record what would have been written.
**When to use:** Admin Agent eval (D-04, D-09).
**Example:**
```python
# Source: pattern derived from tools/admin.py AdminTools
class DryRunAdminTools:
    """Admin tools that capture routing decisions without side effects."""
    
    def __init__(self, routing_context: str) -> None:
        self._routing_context = routing_context
        self.captured_destinations: list[str] = []
        self.captured_items: list[dict] = []
    
    @tool(approval_mode="never_require")
    async def add_errand_items(self, items: list[dict]) -> str:
        """Intercept errand routing -- record destinations without writing."""
        for item in items:
            dest = item.get("destination", "unrouted")
            self.captured_destinations.append(dest)
            self.captured_items.append(item)
        return f"[DRY RUN] Would add {len(items)} items"
    
    @tool(approval_mode="never_require")
    async def add_task_items(self, tasks: list[dict]) -> str:
        """Intercept task creation -- record without writing."""
        return f"[DRY RUN] Would add {len(tasks)} tasks"
    
    @tool(approval_mode="never_require")
    async def get_routing_context(self) -> str:
        """Return fixed routing context for deterministic eval."""
        return self._routing_context
    
    # manage_destination, manage_affinity_rule, query_rules can be
    # no-ops or return fixed responses for eval scenarios
```

### Pattern 4: Metrics Computation
**What:** Compute per-bucket precision/recall, overall accuracy, and confidence calibration from eval results.
**When to use:** EVAL-02 metric computation.
**Example:**
```python
# Source: standard classification metrics (no external library needed)
from collections import defaultdict

def compute_classifier_metrics(results: list[dict]) -> dict:
    """Compute precision, recall, accuracy from eval results."""
    total = len(results)
    correct = sum(1 for r in results if r["predicted"] == r["expected"])
    accuracy = correct / total if total > 0 else 0.0
    
    # Per-bucket metrics
    buckets = {"People", "Projects", "Ideas", "Admin"}
    precision = {}
    recall = {}
    
    for bucket in buckets:
        tp = sum(1 for r in results if r["predicted"] == bucket and r["expected"] == bucket)
        fp = sum(1 for r in results if r["predicted"] == bucket and r["expected"] != bucket)
        fn = sum(1 for r in results if r["predicted"] != bucket and r["expected"] == bucket)
        
        precision[bucket] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall[bucket] = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    return {
        "accuracy": accuracy,
        "total": total,
        "correct": correct,
        "precision": precision,
        "recall": recall,
    }

def compute_confidence_calibration(results: list[dict], bins: int = 5) -> list[dict]:
    """Compute calibration: does confidence correlate with actual accuracy?
    
    Bins results by confidence range and computes actual accuracy per bin.
    Perfect calibration: 80% confidence bin has ~80% actual accuracy.
    """
    bin_edges = [i / bins for i in range(bins + 1)]
    calibration = []
    
    for i in range(bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        bin_results = [r for r in results if lo <= r["confidence"] < hi]
        if bin_results:
            actual_accuracy = sum(1 for r in bin_results if r["predicted"] == r["expected"]) / len(bin_results)
            avg_confidence = sum(r["confidence"] for r in bin_results) / len(bin_results)
            calibration.append({
                "bin": f"{lo:.1f}-{hi:.1f}",
                "count": len(bin_results),
                "avg_confidence": round(avg_confidence, 3),
                "actual_accuracy": round(actual_accuracy, 3),
            })
    
    return calibration
```

### Pattern 5: Dry-Run Classifier Tools for Eval
**What:** A modified `file_capture` tool that captures the agent's classification decision (bucket, confidence, status) without writing to Cosmos.
**When to use:** Classifier eval -- need to see what the agent decided without side effects.
**Example:**
```python
class EvalClassifierTools:
    """Classifier tools that capture predictions without Cosmos writes."""
    
    def __init__(self) -> None:
        self.last_bucket: str | None = None
        self.last_confidence: float | None = None
        self.last_status: str | None = None
    
    @tool(approval_mode="never_require")
    async def file_capture(
        self,
        text: str,
        bucket: str,
        confidence: float,
        status: str,
        title: str | None = None,
    ) -> dict:
        """Capture classification without writing to Cosmos."""
        self.last_bucket = bucket
        self.last_confidence = max(0.0, min(1.0, confidence))
        self.last_status = status
        return {"bucket": bucket, "confidence": confidence, "item_id": "eval-dry-run"}
```

### Anti-Patterns to Avoid
- **Concurrent agent calls:** D-03 locks sequential execution. Do NOT use `asyncio.gather()` for eval cases -- Foundry has rate limits and concurrent threads create non-deterministic timing.
- **Direct GPT-4o API calls:** D-02 requires the real Foundry Classifier agent with its portal-managed instructions. Bypassing the agent means you're not testing the actual production system.
- **Writing to production containers during eval:** Classifier eval must NOT write InboxDocuments or bucket documents. Use dry-run tool handlers that capture args without Cosmos writes.
- **In-memory-only results:** Eval results must be persisted to Cosmos AND logged to App Insights (EVAL-04). Don't just return them in the API response.
- **Global mutable state for eval run tracking:** Use `app.state` for the eval runs dict, not a module-level global, to maintain test isolation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Confusion matrix | Custom matrix class | dict-based precision/recall computation | Only 4 buckets; simple dict math is sufficient and more readable |
| Agent invocation | Custom HTTP calls to Foundry | `AzureAIAgentClient.get_response()` | Already used everywhere; handles auth, retries, tool execution |
| Background task management | Custom task queue | `asyncio.create_task` + `app.state.background_tasks` set | Established pattern in this codebase (admin processing) |
| Cosmos CRUD | Direct HTTP to Cosmos REST API | `CosmosManager.get_container()` | Already abstracted; handles auth, partitioning |
| Result formatting | Custom markdown renderer | String formatting in investigation tool | Simple tables; no library needed for this scale |

**Key insight:** This phase has zero new dependencies. Everything is built on the existing agent framework, Cosmos infrastructure, and investigation tool pattern. The novel code is the eval runner logic (iterate dataset, invoke agent, compute metrics) and the dry-run tool handlers.

## Common Pitfalls

### Pitfall 1: Tool Argument Extraction from Non-Streaming Response
**What goes wrong:** The non-streaming `get_response()` returns a `ChatResponse` object. The tool call arguments and results are embedded in the response, but their extraction differs from the streaming adapter's `ChatResponseUpdate` content inspection.
**Why it happens:** The streaming adapter (used by capture.py) manually tracks `function_call` and `function_result` content types. The non-streaming admin_handoff.py pattern uses `FunctionTool.invocation_count` to detect tool calls but doesn't extract arguments.
**How to avoid:** Use dry-run tool handlers (EvalClassifierTools) that capture arguments internally when invoked. The agent framework will call the tool automatically during `get_response()`. After the response completes, read captured values from the tool instance. This is cleaner than parsing the response object.
**Warning signs:** If you find yourself inspecting `response.value` for function call data, you're going the wrong way.

### Pitfall 2: Agent State Leakage Between Eval Cases
**What goes wrong:** If the same `AzureAIAgentClient` reuses thread/conversation state between eval cases, later cases may be influenced by earlier results.
**Why it happens:** The agent framework preserves conversation context via `conversation_id`. If not explicitly creating a new thread per eval case, state leaks.
**How to avoid:** Do NOT pass `conversation_id` in ChatOptions for eval runs. Each eval case must be a fresh, stateless interaction. The agent should classify the text in isolation.
**Warning signs:** Eval results are order-dependent (different results when cases are shuffled).

### Pitfall 3: Dry-Run Tool Signature Mismatch
**What goes wrong:** The Foundry agent has instructions expecting specific tool signatures (matching `ClassifierTools.file_capture` or `AdminTools.add_errand_items`). If the dry-run tool signature differs, the agent may refuse to call it or pass wrong arguments.
**Why it happens:** The `@tool` decorator generates a JSON schema from the function signature. Even cosmetic changes (different parameter names, missing annotations) produce a different schema.
**How to avoid:** Copy the exact parameter signatures from the production tools. Only change the function body. The `Annotated[..., Field(...)]` type hints must be identical.
**Warning signs:** Agent returns text without calling tools, or tool calls have missing/wrong arguments.

### Pitfall 4: Admin Agent Eval Requires Deterministic Routing Context
**What goes wrong:** The Admin Agent calls `get_routing_context` to load destinations and affinity rules. If the production Cosmos data changes between eval runs, expected destinations become stale.
**Why it happens:** The golden dataset has `expectedDestination` values computed against a specific set of affinity rules. If rules change in production, the eval becomes invalid.
**How to avoid:** The dry-run `get_routing_context` tool must return a FIXED routing context matching the golden dataset's assumptions (D-13). Store the reference affinity rules alongside the golden dataset or embed them in the eval config.
**Warning signs:** Admin Agent eval accuracy drops suddenly after affinity rule changes -- false negative.

### Pitfall 5: Background Task Error Swallowing
**What goes wrong:** `asyncio.create_task` fires and forgets. If the eval runner raises an unhandled exception, it's silently swallowed unless the task has an error callback.
**Why it happens:** Python asyncio tasks log "Task exception was never retrieved" to stderr, but this doesn't surface in App Insights.
**How to avoid:** The eval runner MUST have a top-level try/except that (1) logs to App Insights, (2) updates the eval run status to "failed" with the error message, (3) sets `_eval_runs[run_id]["status"] = "failed"`.
**Warning signs:** Eval runs show "running" forever, no results appear.

### Pitfall 6: Auto-Format Hook Strips Unused Imports
**What goes wrong:** The ruff auto-format hook runs on every file edit. If you add an import that isn't referenced until the next edit, it gets stripped.
**Why it happens:** PostToolUse auto-format hook in `~/.claude/hooks/auto-format.py` runs ruff between edits.
**How to avoid:** When adding a new import + its first usage, do both in a single `Write` operation. Or add the import AFTER the usage is already in place. [VERIFIED: MEMORY.md Phase 17.1 lesson]
**Warning signs:** `NameError: name 'X' is not defined` at runtime despite having added the import.

## Code Examples

### Eval Runner Core Loop
```python
# Source: derived from processing/admin_handoff.py pattern + D-02/D-03 constraints
import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from agent_framework import ChatOptions, Message
from agent_framework.azure import AzureAIAgentClient

from second_brain.db.cosmos import CosmosManager
from second_brain.eval.metrics import compute_classifier_metrics, compute_confidence_calibration
from second_brain.models.documents import EvalResultsDocument

logger = logging.getLogger(__name__)

async def run_classifier_eval(
    run_id: str,
    cosmos_manager: CosmosManager,
    classifier_client: AzureAIAgentClient,
    runs_dict: dict,
) -> None:
    """Run classifier eval against golden dataset. Background task."""
    try:
        # 1. Read golden dataset
        golden_container = cosmos_manager.get_container("GoldenDataset")
        test_cases: list[dict] = []
        async for item in golden_container.query_items(
            query="SELECT * FROM c WHERE c.userId = @userId",
            parameters=[{"name": "@userId", "value": "will"}],
            partition_key="will",
        ):
            # Only classifier test cases (no expectedDestination)
            if "expectedDestination" not in item or item.get("expectedDestination") is None:
                test_cases.append(item)
        
        if not test_cases:
            runs_dict[run_id] = {
                "status": "failed",
                "error": "No classifier test cases found in golden dataset",
            }
            return
        
        # 2. Run each case sequentially (D-03)
        individual_results: list[dict] = []
        for i, case in enumerate(test_cases):
            eval_tools = EvalClassifierTools()
            try:
                messages = [Message(role="user", text=case["inputText"])]
                options = ChatOptions(
                    tools=[eval_tools.file_capture],
                    tool_choice={
                        "mode": "required",
                        "required_function_name": "file_capture",
                    },
                )
                
                async with asyncio.timeout(60):
                    await classifier_client.get_response(
                        messages=messages, options=options
                    )
                
                result = {
                    "input": case["inputText"][:100],
                    "expected": case["expectedBucket"],
                    "predicted": eval_tools.last_bucket or "NONE",
                    "confidence": eval_tools.last_confidence or 0.0,
                    "correct": eval_tools.last_bucket == case["expectedBucket"],
                    "case_id": case["id"],
                }
            except Exception as exc:
                result = {
                    "input": case["inputText"][:100],
                    "expected": case["expectedBucket"],
                    "predicted": "ERROR",
                    "confidence": 0.0,
                    "correct": False,
                    "case_id": case["id"],
                    "error": str(exc),
                }
            
            individual_results.append(result)
            runs_dict[run_id]["progress"] = f"{i + 1}/{len(test_cases)}"
        
        # 3. Compute metrics
        metrics = compute_classifier_metrics(individual_results)
        calibration = compute_confidence_calibration(individual_results)
        metrics["calibration"] = calibration
        
        # 4. Write to Cosmos
        eval_doc = EvalResultsDocument(
            evalType="classifier",
            runTimestamp=datetime.now(UTC),
            datasetSize=len(test_cases),
            aggregateScores=metrics,
            individualResults=individual_results,
            modelDeployment="gpt-4o",
        )
        
        eval_container = cosmos_manager.get_container("EvalResults")
        await eval_container.create_item(
            body=eval_doc.model_dump(mode="json"),
        )
        
        # 5. Log to App Insights
        logger.info(
            "Classifier eval complete: accuracy=%.2f, total=%d, correct=%d",
            metrics["accuracy"],
            metrics["total"],
            metrics["correct"],
            extra={
                "component": "eval",
                "eval_type": "classifier",
                "eval_run_id": run_id,
                "accuracy": metrics["accuracy"],
            },
        )
        
        runs_dict[run_id] = {
            "status": "completed",
            "result_id": eval_doc.id,
            "accuracy": metrics["accuracy"],
            "total": metrics["total"],
            "correct": metrics["correct"],
        }
        
    except Exception as exc:
        logger.error(
            "Classifier eval failed: %s", exc, exc_info=True,
            extra={"component": "eval", "eval_run_id": run_id},
        )
        runs_dict[run_id] = {"status": "failed", "error": str(exc)}
```

### Investigation Tool for Triggering Eval
```python
# Source: follows existing InvestigationTools pattern in tools/investigation.py
@tool(approval_mode="never_require")
async def run_classifier_eval(self) -> str:
    """Trigger a classifier evaluation run against the golden dataset.
    
    Starts a background eval run that sends each golden dataset
    entry through the Classifier agent and measures accuracy.
    Returns the run ID for status tracking.
    """
    # Internal API call to eval endpoint
    # (or direct invocation of eval runner)
    ...
```

### Golden Dataset Export Script
```python
# Source: new script, pattern from scripts/create_eval_containers.py
"""Export Inbox captures to JSON for golden dataset curation.

Usage:
    python3 backend/scripts/seed_golden_dataset.py export --limit 100
    # Manually edit the exported JSON (add/fix expectedBucket labels)
    python3 backend/scripts/seed_golden_dataset.py import --file golden_dataset.json
"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM-as-judge eval | Deterministic metrics (exact match) | v3.1 decision | No model dependency for evaluation -- results are reproducible |
| azure-ai-evaluation SDK | Custom eval runner | Phase 19.3 finding | No built-in classification evaluator in azure-ai-evaluation; custom scorers via Foundry evaluate() possible but overkill for 4-bucket classification |
| Offline eval scripts | Live eval against deployed agents | D-02 | Tests the actual production system, not a mock; catches instruction drift |

**Deprecated/outdated:**
- azure-ai-evaluation classification evaluators: Do not exist as of Phase 19.3 inventory [VERIFIED: Phase 19.3 decision in STATE.md]
- Eval pipeline as CLI + GitHub Actions: Original STATE.md decision overridden by D-01 (API endpoint + background task). CLI/CI eval deferred to Phase 22

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_response()` without `conversation_id` creates a new isolated thread per call | Common Pitfalls #2 | Agent state leaks between eval cases, producing order-dependent results. Mitigation: verify in first eval run by running the same case twice |
| A2 | FunctionTool dry-run replacement with identical signature will be accepted by the Foundry agent without re-registration | Architecture Patterns #5 | Agent refuses to call the tool. Mitigation: the agent is instruction-driven and uses JSON schema matching; identical schema = same tool |
| A3 | 50 sequential agent calls complete within 5 minutes at ~6s per call average | Summary | Eval takes longer than expected. Impact: low; sequential is locked (D-03), just wait longer. Monitor with progress tracking |
| A4 | Admin Agent calls `get_routing_context` before `add_errand_items` consistently | Pitfall #4 | Dry-run routing context never used; admin agent routes without loading rules. Impact: eval misses routing accuracy. Mitigation: Admin Agent portal instructions require routing context lookup |

## Open Questions

1. **GoldenDatasetDocument schema for admin eval**
   - What we know: GoldenDatasetDocument has `inputText`, `expectedBucket`, `source`, `tags`. Admin eval needs `expectedDestination`.
   - What's unclear: Add `expectedDestination: str | None = None` to existing model, or separate document type?
   - Recommendation: Add optional `expectedDestination` field to GoldenDatasetDocument. Single model, `evalType` distinguished by presence of `expectedDestination`. Simpler than maintaining two models with shared fields.

2. **Eval run ID persistence across container restarts**
   - What we know: In-memory `_eval_runs` dict is lost on restart. Eval results ARE persisted in Cosmos.
   - What's unclear: If user triggers eval, container restarts mid-run, status endpoint returns 404.
   - Recommendation: Acceptable for single-user system. The eval result either appears in Cosmos (success) or doesn't (failure). Investigation tool can query latest EvalResultsDocument directly.

3. **Multi-bucket split captures in golden dataset**
   - What we know: The Classifier can split a capture across multiple buckets (e.g., "Buy milk and call the dentist" -> Admin + Admin).
   - What's unclear: How to score a split capture. The golden dataset has a single `expectedBucket`.
   - Recommendation: For Phase 21, treat split captures as a special `tags: ["multi_bucket"]` category. Score by primary bucket (first file_capture call). More sophisticated split scoring is a future enhancement.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && .venv/bin/python3 -m pytest tests/test_eval.py -x` |
| Full suite command | `cd backend && .venv/bin/python3 -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EVAL-01 | Golden dataset read + count | unit | `.venv/bin/python3 -m pytest tests/test_eval.py::test_golden_dataset_read -x` | Wave 0 |
| EVAL-02 | Metrics computation (precision/recall/accuracy/calibration) | unit | `.venv/bin/python3 -m pytest tests/test_eval.py::test_metrics_computation -x` | Wave 0 |
| EVAL-03 | Admin dry-run tool captures routing decisions | unit | `.venv/bin/python3 -m pytest tests/test_eval.py::test_admin_dry_run_tools -x` | Wave 0 |
| EVAL-04 | Eval results written to Cosmos + logged | unit | `.venv/bin/python3 -m pytest tests/test_eval.py::test_eval_results_persistence -x` | Wave 0 |
| EVAL-05 | Eval trigger via API endpoint | unit | `.venv/bin/python3 -m pytest tests/test_eval.py::test_eval_api_endpoint -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && .venv/bin/python3 -m pytest tests/test_eval.py -x`
- **Per wave merge:** `cd backend && .venv/bin/python3 -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_eval.py` -- covers EVAL-01 through EVAL-05 (unit tests with mocked Cosmos + mocked agent client)
- [ ] `tests/test_eval_metrics.py` -- covers metric computation edge cases (empty dataset, single bucket, perfect score, zero score)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | API key middleware (already applied to all routes) |
| V3 Session Management | no | -- |
| V4 Access Control | yes | Eval endpoint behind same API key auth; no new auth surface |
| V5 Input Validation | yes | Pydantic model validation on API request body |
| V6 Cryptography | no | -- |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Eval endpoint abuse (DoS via repeated large eval runs) | Denial of Service | Single in-flight eval check: reject if already running |
| Golden dataset poisoning | Tampering | Source field on GoldenDatasetDocument tracks provenance; manual review before import |
| Eval results leaking sensitive capture text | Information Disclosure | `individualResults[].input` truncated to 100 chars; same auth as all other endpoints |

## Sources

### Primary (HIGH confidence)
- `backend/src/second_brain/models/documents.py` -- GoldenDatasetDocument (line 178), EvalResultsDocument (line 194) schema verified
- `backend/src/second_brain/db/cosmos.py` -- Feedback, EvalResults, GoldenDataset containers confirmed in CONTAINER_NAMES list
- `backend/src/second_brain/tools/investigation.py` -- InvestigationTools pattern with @tool, approval_mode, async verified
- `backend/src/second_brain/tools/classification.py` -- ClassifierTools.file_capture signature verified (text, bucket, confidence, status, title)
- `backend/src/second_brain/tools/admin.py` -- AdminTools.add_errand_items signature verified (items: list[dict])
- `backend/src/second_brain/processing/admin_handoff.py` -- Non-streaming get_response pattern verified
- `backend/src/second_brain/streaming/adapter.py` -- Streaming file_capture parsing pattern verified
- `backend/src/second_brain/main.py` -- Lifespan wiring of all clients and tools verified
- `agent-framework-azure-ai==1.0.0rc2` -- Version verified via pip show
- `pytest==9.0.2`, `fastapi==0.133.1` -- Versions verified via pip

### Secondary (MEDIUM confidence)
- Phase 19.3 finding: "No built-in classification-accuracy evaluator in azure-ai-evaluation" -- from STATE.md decisions [VERIFIED: STATE.md]
- Phase 20 CONTEXT.md -- Feedback signal architecture and investigation tool additions verified in source code

### Tertiary (LOW confidence)
- None -- all claims verified against source code or project documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use; no new dependencies
- Architecture: HIGH -- patterns directly derived from existing codebase (admin_handoff.py, InvestigationTools, background task pattern)
- Pitfalls: HIGH -- identified from actual codebase patterns and MEMORY.md lessons learned

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable; no external dependency changes expected)
