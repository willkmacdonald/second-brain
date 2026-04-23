# Phase 21: Eval Framework - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Deterministic quality measurement for the Classifier and Admin Agent. Golden datasets with 50+ curated test cases, evaluators that compute precision/recall/accuracy by running captures through the real Foundry agents, score storage in Cosmos, and on-demand triggering via the investigation agent (mobile chat or /investigate skill from Claude Code).

</domain>

<decisions>
## Implementation Decisions

### Eval execution model
- **D-01:** Eval runner lives as a backend API endpoint (`/api/eval/run`) that kicks off the eval as a background task (`asyncio.create_task`), returns immediately with a run ID
- **D-02:** Classifier eval sends each golden dataset entry through the real Foundry Classifier agent (full thread creation + agent run), comparing the returned bucket against `expectedBucket` — no direct GPT-4o shortcut
- **D-03:** Test cases run sequentially — one agent call at a time, no concurrency. A 50-case run takes 3-5 minutes, which is acceptable for on-demand eval
- **D-04:** Admin Agent eval uses the same real-agent-run pattern but with dry-run tool handlers that intercept `add_errand_items` to check routing destination without writing to Cosmos

### Trigger & results UX
- **D-05:** Mobile trigger is via investigation agent command — user says "run classifier eval" or "run admin eval" in the investigation chat. Agent calls a new @tool that hits the eval API endpoint. No new mobile UI screens needed
- **D-06:** Claude Code trigger is via the existing `/investigate` skill — routes through the investigation agent on the deployed API, which calls the same eval @tool. No new MCP tool needed
- **D-07:** Results are displayed as a formatted investigation agent chat response (markdown with accuracy, per-bucket precision/recall table, failures highlighted). No dashboard cards in this phase

### Admin Agent eval scope
- **D-08:** Admin Agent eval focuses on routing accuracy only — did items end up at the correct destination? No tool call sequence verification
- **D-09:** Admin Agent eval runs captures through the real Admin Agent with dry-run tool handlers — intercepts tool calls to check what would have been routed without side effects

### Dataset seeding
- **D-10:** Initial golden dataset is seeded by exporting real captures from Cosmos Inbox, manually curating/labeling them, then importing as GoldenDatasetDocuments with `source='manual'`
- **D-11:** The export/curation/import script is a deliverable within Phase 21 — not pre-work
- **D-12:** Admin Agent golden dataset entries have `inputText` + `expectedDestination` — routing accuracy only, no expected item extraction verification
- **D-13:** Admin Agent test cases require a known set of affinity rules as test fixtures to ensure deterministic expected destinations

### Claude's Discretion
- Eval status polling mechanism (SSE vs polling endpoint vs webhook)
- Classifier eval result formatting in the investigation agent response
- How the dry-run tool handler works for Admin Agent eval (mock tools, tool interception, or sandbox mode)
- Whether to add an `expectedDestination` field to GoldenDatasetDocument or use a separate AdminGoldenDatasetDocument model
- Export script output format (JSON file for human review before import)
- How to handle multi-bucket split captures in the classifier golden dataset (test the split detection, or treat as individual bucket tests)
- Confidence calibration metric calculation approach

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Data models
- `backend/src/second_brain/models/documents.py` — FeedbackDocument (line 160), GoldenDatasetDocument (line 178), EvalResultsDocument (line 194) — all three models already defined

### Cosmos containers
- `backend/src/second_brain/db/cosmos.py` — Feedback, EvalResults, GoldenDataset containers already provisioned (lines 27-29)
- `backend/scripts/create_eval_containers.py` — Container creation script (reference for partition keys: all use `/userId`)

### Investigation agent tools pattern
- `backend/src/second_brain/tools/investigation.py` — InvestigationTools class with @tool pattern (`approval_mode="never_require"`, async). New eval trigger @tool follows this pattern. Already has `query_feedback_signals` and `promote_to_golden_dataset` from Phase 20

### Classifier agent
- `backend/src/second_brain/agents/classifier.py` — Classifier agent registration (ensure_classifier_agent). Agent instructions live in Foundry portal, not in repo
- `backend/src/second_brain/tools/classification.py` — ClassifierTools with `file_capture` @tool — eval needs to parse the tool call to extract predicted bucket

### Admin Agent
- `backend/src/second_brain/tools/admin.py` — AdminTools with 6 @tool functions. Eval needs dry-run versions that intercept `add_errand_items`

### Capture flow
- `backend/src/second_brain/api/capture.py` — Capture endpoint showing how text flows through Classifier agent (line 202). Eval mimics this flow

### Requirements
- `.planning/REQUIREMENTS.md` §Eval Framework — EVAL-01 through EVAL-05

### Phase 20 context (direct dependency)
- `.planning/phases/20-feedback-collection/20-CONTEXT.md` — Feedback signal capture and golden dataset promotion decisions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GoldenDatasetDocument` model — fully defined with inputText, expectedBucket, source, tags fields
- `EvalResultsDocument` model — fully defined with evalType, aggregateScores, individualResults, modelDeployment fields
- `InvestigationTools` class — add `run_eval` @tool following existing pattern
- Cosmos containers (Feedback, EvalResults, GoldenDataset) — already provisioned and accessible via `CosmosManager`
- `ensure_classifier_agent()` — self-healing agent registration, reusable for eval runner
- `AzureAIAgentClient` already wired in `main.py` lifespan — eval runner can reuse `app.state` clients

### Established Patterns
- @tool functions on InvestigationTools with `approval_mode="never_require"` and async implementation
- Background task pattern: `asyncio.create_task` used in admin processing (triggered by GET /api/errands)
- Cosmos document writes via `CosmosManager` container access (`request.app.state.cosmos_manager`)
- Agent thread creation + run pattern in `streaming/adapter.py` and `streaming/investigation_adapter.py`

### Integration Points
- `InvestigationTools` class — add `run_classifier_eval` and `run_admin_eval` @tools
- New API route `/api/eval/run` — background task endpoint returning run ID
- Investigation agent instructions in Foundry portal — needs update to know about eval tools
- `ClassifierTools` and `AdminTools` — eval runner needs access to agent clients to create threads and runs

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

- Eval scores dashboard card on Status screen (deferred from Phase 18 — "eval scores card deferred to Phase 21" note)
- Eval results quick action chip on investigation chat (deferred from Phase 18 — "eval results chip deferred to Phase 21" note)
- Tool call sequence verification for Admin Agent eval (deeper EVAL-03 compliance)
- Synthetic edge case generation for golden dataset expansion
- GitHub Actions eval workflow (belongs in Phase 22: Self-Monitoring Loop)

</deferred>

---

*Phase: 21-eval-framework*
*Context gathered: 2026-04-23*
