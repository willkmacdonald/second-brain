# Inventory Investigation Scratch

Raw findings per surface. Gets pruned into `native-observability-inventory.md` as tasks progress. Not a final artifact -- committed only so the evidence trail survives.

## Surface 1: Azure AI Foundry

### Tracing to App Insights

**Code evidence:**
- `main.py:21-26`: `enable_instrumentation()` from `agent_framework.observability` called after `configure_azure_monitor()`. Tracks `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.operation.duration`.
- `agents/middleware.py`: Custom `AuditAgentMiddleware` creates spans named `{agent}_agent_run` with attributes `agent.name`, `agent.duration_ms`. `ToolTimingMiddleware` creates spans `tool_{func_name}` with `tool.name`, `tool.duration_ms`, classification-specific attrs (`classification.bucket`, `classification.confidence`, etc.).
- `streaming/adapter.py`: Sets `span.set_attribute("capture.trace_id", capture_trace_id)` on the classifier span -- but this is the APP span, not the Foundry SDK's internal HTTP spans.
- Gap confirmed by `project_native_foundry_correlation_gap.md`: "native Foundry agent spans in App Insights are not tagged with capture_trace_id, so the per-correlation filter on the native renderer returns empty."

**Key finding:** The Foundry SDK's own OTel spans (HTTP calls to the Foundry service) carry `operation_Id` from the ambient trace context but do NOT propagate app-level ContextVars or custom span attributes. `capture_trace_id` must be injected explicitly.

### Conversation / thread persistence

**Code evidence:**
- `streaming/adapter.py:174-175`: `thread_id` and `run_id` set as span attributes on every capture.
- `streaming/investigation_adapter.py:117`: `conversation_id` passed to Foundry for multi-turn.
- `streaming/sse.py:78-83`: Foundry `thread_id` exposed in SSE events to the mobile client.
- Foundry portal: Agents > [agent name] > Conversation results shows threads with full prompt/output/tool-call transcripts.

**Key finding:** Thread IDs are available in our spans and SSE stream. Portal shows full transcripts. No native search-by-capture_trace_id -- must match by timestamp or store thread_id in decision record.

### Evaluations SDK

**Doc evidence (Microsoft Learn):**
- `azure-ai-evaluation` SDK provides: GroundednessEvaluator, RelevanceEvaluator, FluencyEvaluator, CoherenceEvaluator, SimilarityEvaluator, F1ScoreEvaluator, QAEvaluator.
- All are text-quality evaluators. None score categorical label correctness.
- `evaluate()` function accepts custom callable scorers via the `evaluators` dict.

**Key finding:** No built-in classification-accuracy evaluator. Phase 21 must write custom scorers for: bucket exact-match, confidence calibration, per-bucket precision/recall. Foundry SDK can still host and run them via `evaluate()`.

### Prompt-agent versioning

**Code evidence:**
- `agents/classifier.py`, `agents/admin.py`, `agents/investigation.py`: Use `ensure_*_agent()` which calls `agents_client.create_agent()` or validates existing. Instructions are set at create time or via `update_agent()`.
- Portal: No version history UI. Edit overwrites.

**Key finding:** No native versioning. `AgentReleaseManifest` (repo-versioned JSON snapshot) required for Phase 19.5.
