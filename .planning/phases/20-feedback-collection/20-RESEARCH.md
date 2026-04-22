# Phase 20: Feedback Collection - Research

**Researched:** 2026-04-22
**Domain:** Quality signal capture (implicit + explicit), Cosmos DB writes, Investigation Agent tool extension, mobile UI
**Confidence:** HIGH

## Summary

Phase 20 adds quality signal collection to the Second Brain system. Three implicit signal types (recategorize, HITL bucket pick, errand re-route) emit `FeedbackDocument` writes inline in existing backend handlers. Explicit thumbs up/down feedback is added to the inbox detail modal on mobile. The Investigation Agent gains two new `@tool` functions for querying feedback signals and promoting them to the golden dataset.

The implementation surface is well-scoped: the `FeedbackDocument` and `GoldenDatasetDocument` models already exist in `documents.py`, the `Feedback` and `GoldenDataset` Cosmos containers are already provisioned in `cosmos.py`, and the `InvestigationTools` class has an established `@tool` pattern to follow. The mobile UI change is a small addition to the existing inbox detail modal (thumbs up/down buttons per the approved UI spec). No new dependencies are needed.

**Primary recommendation:** Implement in backend-first order: (1) create feedback API endpoint + implicit signal emit points, (2) add Investigation Agent tools for signal query and golden dataset promotion, (3) add mobile thumbs up/down UI, (4) update Investigation Agent portal instructions. Each step builds on verified backend infrastructure before touching the mobile layer.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Implicit signals are written inline in the existing handlers (recategorize endpoint, HITL resolution flow, errand re-route handler) -- not via Change Feed or background tasks
- **D-02:** Signal write is fire-and-forget with try/except + logger.warning -- a failed Feedback write NEVER blocks the primary user action (recategorize, HITL pick, re-route)
- **D-03:** Each signal creates a `FeedbackDocument` in the Feedback Cosmos container using the model already defined in `documents.py` (signalType, captureText, originalBucket, correctedBucket, captureTraceId)
- **D-04:** Promotion is done through the investigation agent -- no dedicated mobile screen. User asks the agent to show signals, then promotes individual ones via natural language command
- **D-05:** Investigation agent gets new @tool functions: one to query/list feedback signals, one to promote a signal to golden dataset
- **D-06:** Promotion requires agent confirmation before writing -- agent shows the capture text and label, user confirms, then GoldenDatasetDocument is written
- **D-07:** Review and promote flow is conversational: "show me recent misclassifications" -> agent lists them -> "promote signal abc123" -> agent confirms -> user says yes -> written to GoldenDataset container

### Claude's Discretion
- Thumbs up/down UI placement and interaction pattern on inbox items (inline buttons, detail screen, etc.) -- **RESOLVED by UI spec: inside detail modal, between timestamp and bucket sections**
- Investigation agent tool parameter design (time ranges, filters, pagination for signal queries)
- FEED-04 implementation: how the investigation agent answers "what are the most common misclassifications?" -- Cosmos query against Feedback container with aggregation, response formatting
- Whether to add MCP tool equivalents for signal querying alongside the investigation agent @tools
- Exact signal deduplication strategy (if same capture is recategorized twice, store both or update)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FEED-01 | Implicit quality signals are captured automatically (recategorize = misclassification, HITL bucket pick, errand re-routing) | Recategorize handler in `inbox.py:197`, HITL bucket pick uses same recategorize endpoint from capture screen, errand re-route in `errands.py:336`. All three handlers verified -- inline FeedbackDocument write with fire-and-forget pattern. |
| FEED-02 | User can provide explicit feedback on classifications (thumbs up/down) | New feedback API endpoint + mobile UI per approved 20-UI-SPEC.md. InboxItem detail modal in `inbox.tsx` is the attachment point. |
| FEED-03 | Quality signals can be promoted to golden dataset entries after user confirmation | New `promote_to_golden_dataset` @tool on InvestigationTools class. Reads FeedbackDocument, confirms with user, writes GoldenDatasetDocument. Both models already defined. |
| FEED-04 | Investigation agent can answer "what are the most common misclassifications?" from signal data | New `query_feedback_signals` @tool on InvestigationTools. Cosmos SQL query against Feedback container with Python-side aggregation (GROUP BY constrained in Cosmos). |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Implicit signal capture (recategorize, HITL, re-route) | API / Backend | -- | Signal emit is inline in existing FastAPI handlers; fire-and-forget Cosmos write |
| Explicit feedback (thumbs up/down) | Browser / Client (mobile) | API / Backend | Mobile UI collects input; backend API endpoint persists to Cosmos |
| Feedback signal query | API / Backend | -- | Investigation Agent @tool queries Cosmos Feedback container directly |
| Golden dataset promotion | API / Backend | -- | Investigation Agent @tool reads Feedback, writes GoldenDataset; conversational confirmation |
| Misclassification analytics (FEED-04) | API / Backend | -- | Cosmos query + Python-side aggregation; agent formats response |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| azure-cosmos (async) | 4.14.6 | Feedback and GoldenDataset container read/write | Already used throughout project [VERIFIED: pip list] |
| agent-framework-azure-ai | 1.0.0rc2 | @tool decorator for Investigation Agent tools | Already used for existing InvestigationTools [VERIFIED: pip list] |
| pydantic | (project pinned) | FeedbackDocument, GoldenDatasetDocument models | Already defined in documents.py [VERIFIED: codebase] |
| FastAPI | (project pinned) | New /api/feedback endpoint | Already used for all API endpoints [VERIFIED: codebase] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| React Native Pressable | built-in | Thumbs up/down buttons | Mobile UI per approved UI spec |
| pytest + httpx | (project pinned) | Testing feedback API and tool functions | Existing test pattern in conftest.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline signal writes | Cosmos Change Feed | Change Feed adds infrastructure complexity; inline is simpler for 3 emit points per D-01 |
| Python-side aggregation | Cosmos GROUP BY | GROUP BY restricted in cross-partition queries; single-partition (userId=will) GROUP BY works but Python aggregation is the established project pattern |
| MCP tool equivalents | Investigation Agent @tools only | MCP tools could be added later as an additive enhancement; not required for Phase 20 scope |

**Installation:**
```bash
# No new packages needed -- all dependencies already installed
```

## Architecture Patterns

### System Architecture Diagram

```
Mobile App                          Backend API                         Cosmos DB
-----------                         -----------                         ---------

[Inbox Detail Modal]                                                    
  |-- Thumbs Up/Down --->  POST /api/feedback  --------->  [Feedback container]
  |                            (fire-and-forget)               /userId partition
  |
  |-- Recategorize ------>  PATCH /api/inbox/{id}/recategorize
  |                            |
  |                            +-- Cosmos bucket move (existing)
  |                            +-- FeedbackDocument write (NEW, inline)
  |
[Capture Screen]
  |-- HITL Bucket Pick -->  PATCH /api/inbox/{id}/recategorize  (same endpoint)
  |                            |
  |                            +-- FeedbackDocument write (NEW, detect via status)

[Tasks Screen opens]
  |-- GET /api/errands --->  triggers admin processing (existing side effect)

Mobile/Chat                          
  |-- POST /api/errands/{id}/route
       |
       +-- Errand move (existing)    ----->  [Errands container]
       +-- FeedbackDocument write (NEW)      [Feedback container]

[Investigation Chat]
  |-- "show misclassifications" -->  Investigation Agent
       |                                |
       +-- query_feedback_signals ------+---->  [Feedback container]
       |                                         (read, aggregate in Python)
       +-- "promote signal abc123" 
       |                                |
       +-- promote_to_golden_dataset ---+---->  [GoldenDataset container]
                                                 (write after confirmation)
```

### Recommended Project Structure

No new directories needed. New files fit into existing structure:

```
backend/src/second_brain/
  api/
    feedback.py          # NEW: POST /api/feedback endpoint (explicit thumbs)
    inbox.py             # MODIFIED: add FeedbackDocument write in recategorize
    errands.py           # MODIFIED: add FeedbackDocument write in route_errand_item
  tools/
    investigation.py     # MODIFIED: add query_feedback_signals + promote_to_golden_dataset
  models/
    documents.py         # NO CHANGE: FeedbackDocument + GoldenDatasetDocument already defined

mobile/
  app/(tabs)/
    inbox.tsx            # MODIFIED: add thumbs up/down buttons in detail modal

docs/foundry/
  investigation-agent-instructions.md  # MODIFIED: add new tool descriptions
```

### Pattern 1: Fire-and-Forget Cosmos Write (D-02)

**What:** Write a FeedbackDocument to Cosmos without blocking the primary user action.
**When to use:** Every implicit signal emit point (recategorize, HITL, errand re-route).
**Example:**
```python
# Source: Established project pattern (spine event emission, safety_net writes)
# [VERIFIED: codebase -- adapter.py:_safety_net_file_as_misunderstood, errands.py:route_errand_item]

from second_brain.models.documents import FeedbackDocument

# Inside the recategorize handler, AFTER successful bucket move:
try:
    feedback_doc = FeedbackDocument(
        signalType="recategorize",
        captureText=item.get("rawText", ""),
        originalBucket=old_bucket,
        correctedBucket=body.new_bucket,
        captureTraceId=item.get("captureTraceId"),
    )
    feedback_container = cosmos_manager.get_container("Feedback")
    await feedback_container.create_item(
        body=feedback_doc.model_dump(mode="json")
    )
except Exception:
    logger.warning(
        "Failed to write feedback signal for recategorize %s",
        item_id,
        exc_info=True,
    )
```

### Pattern 2: Investigation Agent @tool (D-05)

**What:** Add new @tool functions to InvestigationTools class.
**When to use:** For query_feedback_signals and promote_to_golden_dataset tools.
**Example:**
```python
# Source: Existing InvestigationTools pattern [VERIFIED: investigation.py]

@tool(approval_mode="never_require")
async def query_feedback_signals(
    self,
    signal_type: Annotated[
        str | None,
        Field(
            description=(
                "Filter by signal type: 'recategorize', 'hitl_bucket', "
                "'errand_reroute', 'thumbs_up', 'thumbs_down'. "
                "Pass null for all types."
            )
        ),
    ] = None,
    time_range: Annotated[
        str,
        Field(
            description="Time range: '24h', '3d', '7d', '30d'. Defaults to '7d'."
        ),
    ] = "7d",
    limit: Annotated[
        int,
        Field(description="Maximum number of signals to return. Defaults to 20."),
    ] = 20,
) -> str:
    """Query quality feedback signals from the Feedback container.

    Returns recent signals with capture text, original/corrected bucket,
    and signal type. Use to review misclassifications, HITL resolutions,
    and explicit user feedback.
    """
    # ... Cosmos query + JSON response
```

### Pattern 3: Distinguishing Recategorize vs HITL Bucket Pick

**What:** The recategorize endpoint handles BOTH recategorize (from inbox detail) and HITL bucket pick (from capture screen). The signal type must differ.
**When to use:** In the recategorize handler, determine which signal type to emit.
**Logic:**
```python
# [VERIFIED: codebase -- inbox.py recategorize handler]
# 
# The same-bucket branch (line ~248) handles HITL confirmation:
# when status is "pending" and user picks the SAME bucket,
# it's a HITL confirmation, not a recategorize.
#
# The cross-bucket branch (line ~263+) is always a recategorize.
#
# Signal type determination:
# - same_bucket AND item.status == "pending" => "hitl_bucket" 
# - different_bucket => "recategorize"
# - same_bucket AND item.status != "pending" => no signal (no-op)

if old_bucket == body.new_bucket:
    if item.get("status") == "pending":
        signal_type = "hitl_bucket"
    else:
        # Same bucket, already classified -- user re-tapped current bucket
        signal_type = None  # No signal needed
else:
    signal_type = "recategorize"
```

### Anti-Patterns to Avoid
- **Blocking on feedback write:** Never `await` feedback writes in a way that could fail the primary action. Use try/except with logger.warning per D-02.
- **Cross-partition queries for aggregation:** The Feedback container uses `/userId` partition key. Always pass `partition_key="will"` to keep queries single-partition. [VERIFIED: all other container queries in codebase use this pattern]
- **Agent tool with side effects hidden from user:** The promote_to_golden_dataset tool MUST confirm with the user before writing (D-06). Agent shows what will be promoted, user says yes.
- **Storing duplicate feedback for toggle:** If user taps thumbs-up then thumbs-down on the same item, store BOTH signals (append-only). Deduplication adds complexity for minimal benefit in a single-user system. [ASSUMED -- discretion area]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cosmos container access | Custom DB abstraction | `CosmosManager.get_container("Feedback")` | Already provisioned and accessible [VERIFIED: cosmos.py] |
| Document models | New data classes | `FeedbackDocument` / `GoldenDatasetDocument` from documents.py | Already defined with correct fields [VERIFIED: documents.py] |
| Agent tool registration | Manual function registration | `@tool(approval_mode="never_require")` decorator on InvestigationTools methods | Established pattern with 4 existing tools [VERIFIED: investigation.py] |
| API authentication | Custom auth | Existing `APIKeyMiddleware` via `app.state.api_key` | All routes already protected [VERIFIED: main.py] |
| Mobile toast feedback | Custom notification system | Existing toast pattern in inbox.tsx | Reuse `recategorizeToast` / `toastBar` styles [VERIFIED: inbox.tsx] |

**Key insight:** Phase 20 is almost entirely additive code wired into existing infrastructure. The data models, containers, tool patterns, and UI patterns all exist already. The risk is not in technology choices but in correctly identifying the emit points and wiring signals at the right place in each handler.

## Common Pitfalls

### Pitfall 1: Signal Emit on Error Path
**What goes wrong:** FeedbackDocument is created even when the primary action (recategorize, re-route) fails, recording a signal for an action that never completed.
**Why it happens:** Placing the feedback write too early in the handler, before the primary action succeeds.
**How to avoid:** Emit the signal AFTER the primary action completes successfully. In recategorize, after Step 2 (inbox doc updated) but before Step 3 (old bucket doc delete, which is non-fatal). In errand route, after the item is moved to the new destination.
**Warning signs:** Feedback container has signals where the inbox item still shows the old bucket.

### Pitfall 2: Missing captureTraceId on InboxDocument
**What goes wrong:** When writing the FeedbackDocument, `captureTraceId` is None because the inbox document doesn't have it stored.
**Why it happens:** `captureTraceId` is stored as a dynamic field on the inbox document (not in the Pydantic model -- it's added ad-hoc in `classification.py:_write_to_cosmos`). When the recategorize handler reads the item, `captureTraceId` may or may not be present.
**How to avoid:** Use `item.get("captureTraceId")` defensively. The FeedbackDocument model already allows `captureTraceId: str | None = None`. [VERIFIED: documents.py line 174]
**Warning signs:** All feedback signals have `captureTraceId: null`.

### Pitfall 3: Ruff Auto-Format Stripping Imports
**What goes wrong:** When adding `FeedbackDocument` import to inbox.py via an Edit, the auto-format hook removes it before the usage is added in a subsequent Edit.
**Why it happens:** Known project issue -- ruff removes unused imports between edits. Documented in MEMORY.md Phase 17.1 lesson.
**How to avoid:** Add the import AND the usage in the same Edit/Write operation. Or add the import as the last edit, after the usage code is already in place.
**Warning signs:** `NameError: name 'FeedbackDocument' is not defined` at runtime.

### Pitfall 4: Investigation Agent Tool Registration Gap
**What goes wrong:** New tools are added to InvestigationTools class but not registered in `main.py`'s `app.state.investigation_tools` list.
**Why it happens:** Tool registration is explicit -- each tool method must be appended to the list in `main.py` (lines 708-712). Adding the class method is not enough.
**How to avoid:** Register new tools in both places: (1) the InvestigationTools class, (2) `main.py`'s investigation tool list.
**Warning signs:** Agent never calls the new tools; "unknown tool" errors in Foundry logs.

### Pitfall 5: Cosmos SDK Query Pattern for Aggregation
**What goes wrong:** Attempting to use `GROUP BY correctedBucket` in Cosmos SQL for misclassification counts, which works within a single partition but may return unexpected results or fail silently.
**Why it happens:** Cosmos SQL GROUP BY has restrictions on what expressions can appear in the SELECT. The codebase already notes this (spine/storage.py line 263: "Cosmos GROUP BY is restricted").
**How to avoid:** Fetch all signals with a simple query (filtered by signalType + time range), then aggregate in Python using `collections.Counter`. This is the established project pattern. [VERIFIED: spine/storage.py]
**Warning signs:** Empty or incorrect aggregation results from Cosmos.

### Pitfall 6: Investigation Agent Portal Instructions Not Updated
**What goes wrong:** New tools are registered programmatically but the Investigation Agent's natural language instructions in the Foundry portal don't mention them, so the agent doesn't know when to use them.
**Why it happens:** Agent instructions live in the AI Foundry portal (not in code). They must be manually updated.
**How to avoid:** Update `docs/foundry/investigation-agent-instructions.md` AND paste the updated instructions into the Foundry portal. [VERIFIED: docs/foundry/investigation-agent-instructions.md]
**Warning signs:** Agent never calls feedback tools even when asked about misclassifications.

## Code Examples

### Feedback API Endpoint (POST /api/feedback)

```python
# Source: Pattern from inbox.py, errands.py [VERIFIED: codebase]

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from second_brain.models.documents import FeedbackDocument

router = APIRouter()


class FeedbackRequest(BaseModel):
    """Request body for explicit feedback (thumbs up/down)."""
    inboxItemId: str
    signalType: str  # "thumbs_up" or "thumbs_down"
    captureText: str
    originalBucket: str
    captureTraceId: str | None = None


@router.post("/api/feedback", status_code=201)
async def submit_feedback(request: Request, body: FeedbackRequest) -> dict:
    """Record explicit user feedback on a classification."""
    cosmos_manager = getattr(request.app.state, "cosmos_manager", None)
    if cosmos_manager is None:
        raise HTTPException(status_code=503, detail="Cosmos DB not configured.")

    if body.signalType not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(status_code=400, detail="Invalid signal type.")

    feedback_doc = FeedbackDocument(
        signalType=body.signalType,
        captureText=body.captureText,
        originalBucket=body.originalBucket,
        correctedBucket=None,  # thumbs don't have corrected bucket
        captureTraceId=body.captureTraceId,
    )

    container = cosmos_manager.get_container("Feedback")
    await container.create_item(body=feedback_doc.model_dump(mode="json"))

    return {"status": "recorded", "id": feedback_doc.id}
```

### Inline Feedback Emit in Recategorize Handler

```python
# Source: inbox.py recategorize handler [VERIFIED: codebase]
# Add AFTER Step 2 (inbox doc updated), BEFORE Step 3 (old bucket delete)

# --- Feedback signal (fire-and-forget per D-02) ---
try:
    signal_type = "recategorize"
    if old_bucket == body.new_bucket and item.get("status") == "pending":
        signal_type = "hitl_bucket"
    
    feedback_doc = FeedbackDocument(
        signalType=signal_type,
        captureText=item.get("rawText", ""),
        originalBucket=old_bucket or "",
        correctedBucket=body.new_bucket if signal_type == "recategorize" else None,
        captureTraceId=item.get("captureTraceId"),
    )
    feedback_container = cosmos_manager.get_container("Feedback")
    await feedback_container.create_item(
        body=feedback_doc.model_dump(mode="json")
    )
except Exception:
    logger.warning(
        "Failed to write feedback signal for %s on item %s",
        signal_type,
        item_id,
        exc_info=True,
    )
```

### Cosmos Query for Feedback Signals (Python-side Aggregation)

```python
# Source: Cosmos query pattern from spine/storage.py, admin.py [VERIFIED: codebase]
# Used inside query_feedback_signals @tool

from collections import Counter
from datetime import UTC, datetime, timedelta

time_map = {"24h": 1, "3d": 3, "7d": 7, "30d": 30}
days = time_map.get(time_range, 7)
cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

query = "SELECT * FROM c WHERE c.userId = @userId AND c.createdAt >= @cutoff"
parameters = [
    {"name": "@userId", "value": "will"},
    {"name": "@cutoff", "value": cutoff},
]
if signal_type:
    query += " AND c.signalType = @signalType"
    parameters.append({"name": "@signalType", "value": signal_type})
query += " ORDER BY c.createdAt DESC"

container = cosmos_manager.get_container("Feedback")
signals = []
async for item in container.query_items(
    query=query,
    parameters=parameters,
    partition_key="will",
):
    signals.append(item)
    if len(signals) >= limit:
        break

# For FEED-04 (misclassification analysis):
misclassifications = [s for s in signals if s.get("signalType") == "recategorize"]
bucket_counts = Counter(
    f"{s.get('originalBucket', '?')} -> {s.get('correctedBucket', '?')}"
    for s in misclassifications
)
```

### Mobile Thumbs Up/Down (Inline in Detail Modal)

```tsx
// Source: UI spec 20-UI-SPEC.md [VERIFIED: approved spec]
// Placed in inbox.tsx detail modal between timestamp and bucket sections

const [feedbackState, setFeedbackState] = useState<"none" | "thumbs_up" | "thumbs_down">("none");

const handleFeedback = useCallback(
  async (type: "thumbs_up" | "thumbs_down") => {
    const newState = feedbackState === type ? "none" : type;
    setFeedbackState(newState);
    if (newState === "none" || !selectedItem) return;

    // Fire-and-forget per D-02
    try {
      await fetch(`${API_BASE_URL}/api/feedback`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          inboxItemId: selectedItem.id,
          signalType: newState,
          captureText: selectedItem.rawText,
          originalBucket: selectedItem.classificationMeta?.bucket ?? "Unknown",
        }),
      });
    } catch {
      // Silent failure per D-02 -- do not show error to user
      void reportError({
        eventType: "crud_failure",
        message: `Feedback submit failed`,
        correlationKind: "crud",
        metadata: { operation: "submit_feedback" },
      });
    }
  },
  [feedbackState, selectedItem],
);
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cosmos GROUP BY for aggregation | Python-side aggregation with Counter | Project convention (spine/storage.py) | Avoids cross-partition GROUP BY restrictions; simpler code |
| Separate background workers for signals | Inline fire-and-forget writes | D-01 decision | No Change Feed infrastructure needed for 3 emit points |
| Dedicated feedback review screen | Conversational via Investigation Agent | D-04 decision | Reuses existing chat infrastructure; no new mobile screens |

**Deprecated/outdated:**
- None -- all patterns used are current within this project.

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Append-only strategy for duplicate feedback (store both thumbs-up and thumbs-down if user toggles on same item) | Anti-Patterns section | Low -- could add dedup later if signal noise becomes a problem; single-user system makes this unlikely |

**All other claims in this research were verified against the codebase or cited from official documentation.**

## Open Questions

1. **MCP tool equivalents for feedback query**
   - What we know: The Investigation Agent gets new @tools for feedback. MCP server (`mcp/server.py`) currently only wraps App Insights query tools.
   - What's unclear: Whether to also add feedback query tools to the MCP server for Claude Code access.
   - Recommendation: Defer MCP tools to a follow-up. The Investigation Agent path covers the primary use case (mobile chat). MCP can be additive later.

2. **Pre-populating feedback state on modal open**
   - What we know: The UI spec mentions "If item already has feedback from a prior session: pre-populate the active state on modal open" as OPTIONAL.
   - What's unclear: Whether the inbox list API should return feedback status per item (requires a Cosmos cross-container query or denormalization).
   - Recommendation: Skip pre-population in Phase 20. The feedback is lightweight -- users won't remember if they already gave thumbs-up on a specific item. Avoids API complexity.

3. **InvestigationTools constructor dependency on CosmosManager**
   - What we know: Current InvestigationTools takes `LogsQueryClient` + `workspace_id`. New feedback tools need `CosmosManager` for Feedback container access.
   - What's unclear: Best way to pass CosmosManager to InvestigationTools.
   - Recommendation: Add `cosmos_manager: CosmosManager | None = None` as an optional parameter to `InvestigationTools.__init__`. This matches the project's "optional services" pattern (e.g., LogsQueryClient init is non-fatal). Tools that need it check for None and return a helpful error message.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + httpx (async) |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python3 -m pytest tests/test_feedback.py -x` |
| Full suite command | `cd backend && python3 -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FEED-01a | Recategorize emits feedback signal | unit | `python3 -m pytest tests/test_feedback.py::test_recategorize_emits_feedback -x` | Wave 0 |
| FEED-01b | HITL bucket pick emits hitl_bucket signal | unit | `python3 -m pytest tests/test_feedback.py::test_hitl_bucket_emits_feedback -x` | Wave 0 |
| FEED-01c | Errand re-route emits errand_reroute signal | unit | `python3 -m pytest tests/test_feedback.py::test_errand_reroute_emits_feedback -x` | Wave 0 |
| FEED-01d | Signal write failure does not block primary action | unit | `python3 -m pytest tests/test_feedback.py::test_signal_failure_nonfatal -x` | Wave 0 |
| FEED-02 | POST /api/feedback records thumbs up/down | unit | `python3 -m pytest tests/test_feedback.py::test_explicit_feedback_endpoint -x` | Wave 0 |
| FEED-03 | promote_to_golden_dataset tool writes GoldenDatasetDocument | unit | `python3 -m pytest tests/test_feedback.py::test_promote_to_golden_dataset -x` | Wave 0 |
| FEED-04 | query_feedback_signals returns aggregated misclassification data | unit | `python3 -m pytest tests/test_feedback.py::test_query_feedback_signals -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_feedback.py -x`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_feedback.py` -- covers FEED-01 through FEED-04
- [ ] No new framework install needed (pytest + httpx already configured)
- [ ] Shared fixtures in `conftest.py` already provide `mock_cosmos_manager` with all containers

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Existing APIKeyMiddleware on all routes [VERIFIED: main.py] |
| V3 Session Management | no | No sessions -- stateless API |
| V4 Access Control | yes | userId hardcoded to "will" (single-user system); partition_key="will" prevents data leakage |
| V5 Input Validation | yes | Pydantic model validation on FeedbackRequest body; signalType whitelist check |
| V6 Cryptography | no | No crypto operations in this phase |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Feedback spam (repeated POST /api/feedback) | Denial of Service | Single-user system behind API key; rate limiting not needed |
| Malicious captureText in FeedbackDocument | Tampering | Stored as-is in Cosmos (no execution); only displayed in Investigation Agent text output |
| Signal injection via direct API call | Tampering | API key auth required; single-user system; signals are advisory, not executable |

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** -- all source files read directly via Read tool
  - `backend/src/second_brain/models/documents.py` -- FeedbackDocument, GoldenDatasetDocument models
  - `backend/src/second_brain/tools/investigation.py` -- InvestigationTools @tool pattern
  - `backend/src/second_brain/db/cosmos.py` -- Container provisioning (Feedback, GoldenDataset)
  - `backend/src/second_brain/api/inbox.py` -- Recategorize handler (signal emit point)
  - `backend/src/second_brain/api/errands.py` -- Route errand handler (signal emit point)
  - `backend/src/second_brain/streaming/adapter.py` -- HITL flow understanding
  - `backend/src/second_brain/main.py` -- Investigation tool registration pattern
  - `mobile/app/(tabs)/inbox.tsx` -- Inbox detail modal (UI attachment point)
  - `mobile/app/(tabs)/index.tsx` -- HITL bucket picker flow
  - `mobile/components/InboxItem.tsx` -- InboxItemData interface
  - `docs/foundry/investigation-agent-instructions.md` -- Agent instructions
  - `.planning/phases/20-feedback-collection/20-UI-SPEC.md` -- Approved UI spec
  - `backend/tests/conftest.py` -- Test fixtures and patterns
  - `backend/tests/test_inbox_api.py` -- Recategorize test pattern

### Secondary (MEDIUM confidence)
- [Azure Cosmos DB GROUP BY](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/query/group-by) -- GROUP BY limitations confirmed via project codebase comment (spine/storage.py line 263) and web search [CITED: codebase + web search]

### Tertiary (LOW confidence)
- None -- all findings verified against codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- all patterns verified in existing codebase, all emit points identified and inspected
- Pitfalls: HIGH -- based on direct codebase inspection and MEMORY.md lessons

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (stable -- no external dependency changes expected)
