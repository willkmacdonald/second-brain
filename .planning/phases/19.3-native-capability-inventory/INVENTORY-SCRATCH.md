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

## Surface 2: OpenTelemetry

### Span attributes

**Code evidence:**
- `streaming/adapter.py`: 30+ `span.set_attribute()` calls covering `capture.trace_id`, `capture.outcome`, `capture.type`, `capture.thread_id`, `capture.run_id`, `capture.buckets`, etc.
- `agents/middleware.py`: `AuditAgentMiddleware` sets `agent.name`, `agent.duration_ms`. `ToolTimingMiddleware` sets `tool.name`, `tool.duration_ms`, `classification.*` attrs.
- `processing/admin_handoff.py`: Sets `admin.*` attrs and `capture.trace_id`.
- `streaming/investigation_adapter.py`: Sets `investigate.*` attrs.

These are all app-created spans. The Foundry SDK auto-creates its own spans via `azure-core-tracing-opentelemetry` which only carry `operation_Id`.

### Baggage propagation

**Code evidence:**
- No imports of `opentelemetry.baggage` anywhere in backend codebase.
- `capture_trace_id` propagated via Python `ContextVar` (`capture_trace_id_var` in `tools/classification.py:38-39`).
- ContextVar is thread-local / task-local -- invisible to OTel's trace context propagation.

**Doc evidence:**
- OTel Python SDK supports baggage via `opentelemetry.baggage.set_baggage()`.
- `azure-core` HTTP pipeline uses `opentelemetry` for distributed tracing but the baggage propagation into auto-instrumented spans is NOT guaranteed by `azure-core-tracing-opentelemetry`.
- The W3C `baggage` header is a separate concern from `traceparent` -- SDK must explicitly opt into injecting it.

**Key finding:** Unverified whether Foundry SDK propagates OTel baggage. This is the #1 Phase 19.4 spike question.

## Surface 3: Application Insights / Log Analytics

### Auto-instrumentation

**Code evidence:**
- `main.py:14-19`: `configure_azure_monitor(logger_name="second_brain")` -- scoped to app loggers only.
- `pyproject.toml`: `azure-monitor-opentelemetry>=1.8.6` and `azure-core-tracing-opentelemetry` as direct dependencies.
- Tables populated: `AppRequests` (FastAPI routes), `AppDependencies` (Azure SDK HTTP), `AppTraces` (Python logging), `AppExceptions` (unhandled errors).
- `httpx` NOT instrumented: `opentelemetry-instrumentation-httpx` not in pyproject.toml.

### Custom dimension shape

**Code evidence:**
- `observability/kql_templates.py`: 30+ KQL templates using `tostring(Properties.capture_trace_id)`, `tostring(Properties.component)`, etc.
- Workspace schema: `Properties` is the dynamic column name (NOT `customDimensions` which is portal schema).
- Pattern is well-established and proven across Phases 16-19.

### Retention

**From MEMORY.md:** Log Analytics workspace `shared-services-logs` (ID `572d91c2-3209-4b92-b431-5ffb7e8ce4ad`, 90-day retention).
- No table-level overrides.
- No archive tier.
- No ingestion sampling.

## Surface 4: Azure Monitor

### Workbooks

**Doc evidence:**
- Azure Monitor Workbooks gallery includes: Performance, Failures, Usage, Availability, App Map templates for App Insights.
- No LLM/agent-specific templates. Custom workbooks can be created with arbitrary KQL + parameterized inputs.
- Workbook URLs support parameters for deep-linking.

**Key finding:** Workbooks are a supplement to the web RCA view, not a replacement. Good for "View in Azure" escape hatch.

### SecondBrainAlerts

**From MEMORY.md:** Action Group "SecondBrainAlerts" with 3 rules (API-Error-Spike, Capture-Processing-Failures, API-Health-Check). Email to will@willmacdonald.com + push notifications.

**Key finding:** Adding rules is CLI-able. Phase 22 adds eval degradation rules without restructuring.

### Custom metric alerting

**Doc evidence:**
- Two paths: log-based alerts (scheduled query rules against AppTraces) or custom OTel metrics.
- Log-based alerts are simpler for Phase 22 since eval scores are already logged as custom dimensions.

**Key finding:** Phase 22 uses log-based scheduled query alerts, not custom OTel metrics. No new infrastructure needed.

## Surface 5: Sentry.IO

### Python SDK (backend)

**Code evidence:**
- `sentry-sdk` NOT in `backend/pyproject.toml`.
- Backend uses Sentry only via REST API pull adapter (`spine/adapters/sentry.py`) for mobile error events.
- Backend errors go through App Insights exclusively.

### React Native SDK

**Code evidence:**
- `@sentry/react-native ~7.2.0` in `mobile/package.json`.
- `lib/sentry.ts`: `Sentry.init()` with `tracesSampleRate: 1.0`, `enabled: !__DEV__`, `sendDefaultPii: false`, `reactNavigationIntegration`.
- `_layout.tsx`: `initSentry()` at module scope, `Sentry.ErrorBoundary`, `Sentry.wrap()`.
- `(tabs)/index.tsx`: `Sentry.captureMessage()` in error paths.

### Custom tags

**Code evidence:**
- `lib/sentry.ts:19-23`: `tagTrace()` sets `capture_trace_id`, `correlation_kind`, `correlation_id` via `Sentry.setTag()`.
- `lib/sentry.ts:25-29`: `clearTraceTags()` removes them after capture.
- Backend `sentry.py` adapter: `tag_filter={"app_segment": "mobile_ui"}` filters events by custom tag.
- `lib/ag-ui-client.ts:4`: imports `tagTrace` and calls it during capture flow.

**Key finding:** Tags are set correctly in code. Live verification deferred to Checkpoint C. If tags arrive in Sentry, mobile-side correlation works.

### Log-to-span correlation

**Evidence:**
- `configure_azure_monitor()` auto-correlates logs to spans via `operation_Id` in `AppTraces`.
- Custom span attributes do NOT auto-propagate to log records. Verified by Phase 17 experience where `SeverityLevel` mapping was the issue, not correlation.

### Cross-process context propagation

**Code evidence:**
- `pyproject.toml`: has `azure-core-tracing-opentelemetry` as dependency. This auto-instruments Azure SDK HTTP calls.
- `tools/recipe.py`: Uses raw `httpx.AsyncClient` -- no OTel instrumentation. `opentelemetry-instrumentation-httpx` not in dependencies.
- The Foundry Agent Service endpoint is async -- agent runs happen server-side, not in our process boundary.
