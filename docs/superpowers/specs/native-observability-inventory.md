# Native Observability Capability Inventory

**Date:** 2026-04-19
**Status:** Draft (in progress)
**Parent spec:** docs/superpowers/specs/2026-04-19-observability-evolution-design.md

## Scope

Audits 9 native surfaces the Second Brain depends on, grouped by surface. Each row
captures what the platform gives us natively and what we would still need to build.
Every row names at least one downstream phase it affects.

## Surfaces audited

1. Azure AI Foundry
2. OpenTelemetry
3. Application Insights / Log Analytics
4. Azure Monitor
5. Sentry.IO
6. Azure Cosmos DB
7. Azure Container Apps
8. GitHub Actions
9. Expo / EAS

## Inventory

### 1. Azure AI Foundry

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Tracing to App Insights | `enable_instrumentation()` from `agent_framework.observability` exports `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.operation.duration` as OTel metrics. Custom `AuditAgentMiddleware` + `ToolTimingMiddleware` emit additional spans with agent name, duration, classification attrs to `AppDependencies`. Spans land with `operation_Id` but NOT with `capture_trace_id` as a custom dimension -- the native Foundry SDK does not auto-propagate app-level context vars into its internal HTTP calls. | `capture_trace_id` not present on Foundry-emitted spans in App Insights. Native drill-down filter returns empty ("runs (0)") for captures that ran. Fix requires explicit span attribute injection at the middleware layer or OTel baggage propagation (unverified for Foundry SDK). | 19.4, 19.5 |
| Conversation / thread persistence | Foundry Agent Service persists threads, runs, and messages server-side. Each agent run produces a `thread_id` and `run_id` visible in the Foundry portal under Agents > [agent] > Conversation results. Prompt text, model output, and tool calls (with arguments and results) are visible in the portal UI. Retention follows the Foundry project's data retention policy (default: indefinite within the project). Thread IDs are exposed in our SSE stream and recorded in span attributes. | No native search-by-`capture_trace_id` in the Foundry portal -- operator must match by timestamp + thread_id. The portal does not expose a parameterized deep-link that takes an external correlation ID. | 19.5 |
| Evaluations SDK -- built-ins | `azure-ai-evaluation` provides built-in evaluators for LLM output quality: groundedness, relevance, fluency, coherence, similarity, F1 score. These are text-quality evaluators designed for RAG/chat scenarios. There is no built-in label-match or classification-accuracy evaluator -- the SDK's evaluators score text quality, not categorical correctness. Custom callable scorers can be passed to `evaluate()` for bespoke metrics. | No native classification-accuracy evaluator. Phase 21 must provide a custom scorer for bucket-label exact match, confidence calibration, and per-bucket precision/recall. Foundry built-ins may still cover admin output quality (groundedness of admin responses). | 21 |
| Prompt-agent versioning | Foundry portal does NOT maintain a version history of prompt-agent instructions. When instructions are edited in the portal, the previous version is overwritten. The SDK (`agents_client.update_agent()`) similarly overwrites without versioning. No "which version was active at time T" query is possible natively. | Phase 19.5 needs `AgentReleaseManifest` -- a repo-versioned JSON snapshot of agent instructions, promoted via GitHub Action on each change. `agent_release_id` stored in decision records references this manifest, not a Foundry-native version. | 19.5 |

The Foundry portal's Conversation results view is the primary mechanism for inspecting raw prompts and outputs -- Phase 19.5's design rule ("Foundry First") holds. However, the lack of native search-by-correlation-ID means the RCA view must store Foundry `thread_id` + `run_id` references in the app-owned `AgentDecisionRecord` so the operator can construct a portal deep-link.

### 2. OpenTelemetry

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Span attributes (explicit) | Extensively used. `AuditAgentMiddleware` and `ToolTimingMiddleware` set attributes on app-created spans (`agent.name`, `agent.duration_ms`, `tool.name`, `capture.trace_id`, `capture.outcome`, `classification.bucket`, etc.). `span.set_attribute("capture.trace_id", capture_trace_id)` is called on classifier, admin, and investigation adapter spans. These are the APP spans, not the SDK auto-instrumented spans. | The explicit `set_attribute` calls only tag app-created spans. Foundry SDK internal spans (HTTP calls to the agent service) are auto-instrumented by `azure-core-tracing-opentelemetry` but inherit only `operation_Id`, not custom attributes. Phase 19.4 must either (a) use baggage to propagate `capture_trace_id` into SDK-generated spans or (b) accept that only app spans are filterable and build a mapping layer. | 19.4 |
| Baggage propagation | Not currently used. No `opentelemetry.baggage` imports anywhere in the codebase. The `capture_trace_id` is propagated via a Python `ContextVar` (`capture_trace_id_var` in `tools/classification.py`), which is invisible to OTel. | Baggage propagation through the Foundry SDK is unverified. The Foundry SDK uses `azure-core`'s HTTP pipeline, which respects W3C trace-context headers but does NOT extract/inject OTel baggage by default. Phase 19.4 spike memo must test whether setting `opentelemetry.baggage.set_baggage("capture_trace_id", value)` before an agent call results in the baggage being present on Foundry SDK HTTP spans. If yes, this collapses 3 emit sites into 1 middleware config. If no, explicit `span.set_attribute()` at each site. | 19.4 |
| Log-to-span correlation | Automatic via `configure_azure_monitor()`. When `logger.info(...)` is called inside an active span, the resulting `AppTraces` row carries `operation_Id` matching the parent span's trace ID. Custom dimensions from span attributes do NOT automatically propagate to log records -- `capture_trace_id` set on a span is not present in `AppTraces.Properties` for log records emitted within that span. | To get `capture_trace_id` on log records, it must be passed explicitly as a log record attribute (e.g., `logger.info("msg", extra={"capture_trace_id": value})`) or injected via a logging filter. Current code does not do this systematically. | 19.4, 19.5 |
| Cross-process context propagation | W3C trace-context headers are injected/extracted automatically by `azure-core-tracing-opentelemetry` for outbound HTTP calls made through Azure SDK clients (Cosmos, Foundry, Key Vault). `httpx` calls in `tools/recipe.py` do NOT use an OTel-instrumented transport -- they use raw `httpx.AsyncClient` without the `opentelemetry-instrumentation-httpx` package. The Foundry Agent Service is a managed endpoint that does not propagate trace context back to our process. | `httpx` calls (recipe URL fetching) are not auto-instrumented. Phase 19.4 should add `opentelemetry-instrumentation-httpx` if recipe fetch spans matter for correlation. Foundry agent calls are fire-and-forget from a tracing perspective -- the Foundry service runs the agent asynchronously, so there is no return-path context propagation. | 19.4 |

OTel baggage propagation through the Foundry SDK is the single highest-leverage unknown for Phase 19.4. If baggage works, `capture_trace_id` can be set once in middleware and flow through all SDK calls automatically. If it does not, Phase 19.4 needs explicit `span.set_attribute()` at every emit site (classifier adapter, admin handoff, investigation adapter) plus a mapping strategy for Cosmos `activityId_g`. Phase 19.4 Plan 01 spike memo must resolve this empirically.

### 3. Application Insights / Log Analytics

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Auto-instrumentation (FastAPI, httpx, Cosmos, Foundry, AOAI) | `configure_azure_monitor(logger_name="second_brain")` auto-instruments: FastAPI routes to `AppRequests`, Azure SDK HTTP calls (Cosmos, Key Vault, Foundry, AOAI) to `AppDependencies`, Python logging to `AppTraces`, unhandled exceptions to `AppExceptions`. The `azure-core-tracing-opentelemetry` package provides automatic span creation for all Azure SDK calls. `httpx` is NOT auto-instrumented (no `opentelemetry-instrumentation-httpx` in dependencies). | `httpx` calls (recipe URL fetching via Jina Reader, direct fetch, Playwright) are invisible in App Insights. Low priority -- recipe fetching is a secondary concern. | 19.4, 19.5 |
| Custom dimension shape (`Properties` dynamic column) | Span attributes set via `span.set_attribute()` land in the `Properties` dynamic column (workspace schema) / `customDimensions` (portal schema). Accessed via `tostring(Properties.capture_trace_id)` in KQL. This is the established pattern across 30+ KQL templates in `observability/kql_templates.py`. Custom dimensions are indexed for equality filters. | No missing gaps -- the pattern is proven and in production. The only issue is that `capture_trace_id` is not yet set as a custom dimension on Foundry SDK auto-instrumented spans (Surface 1 / Tracing gap). | 19.4 |
| Retention / archive / sampling | Log Analytics workspace `shared-services-logs` has 90-day retention (per MEMORY.md, confirmed at workspace creation). No table-level retention overrides. No archive tier configured. No ingestion sampling configured -- all telemetry is collected at 100%. For a single-user hobby project, cost is negligible. | Content-rich data (full prompts, full model outputs) should NOT be stored in App Insights -- the 90-day hard retention and per-GB ingestion cost make it unsuitable for long-term decision records. Phase 19.5's `AgentDecisionRecords` go to Cosmos (indefinite retention, no per-GB ingestion cost) per the "Foundry First" design rule. App Insights stores references and summaries only. | 19.5 |

### 4. Azure Monitor

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Workbooks (template gallery) | Azure Monitor Workbooks provide a gallery of templates for App Insights data visualization: performance, failures, usage, availability. Templates are KQL-driven and customizable. No LLM/agent-specific templates exist natively. However, custom workbooks can be built with arbitrary KQL and parameterized inputs. A workbook can query `AppDependencies`, `AppTraces`, `AppRequests` with filter parameters. | No agent-observability-specific templates. Phase 19.5 could build a custom "Agent RCA" workbook as an alternative to a bespoke web page, but the web page provides tighter integration (linking spine ledger to decision records to Foundry portal). Workbooks are a good supplement for ad-hoc investigation but do not replace the structured RCA view. | 19.5 |
| Workbook parameterized URLs | Yes. Workbooks support URL parameters via `?param_name=value` syntax. A workbook can accept `capture_trace_id` as a parameter and use it in KQL queries. This enables deep-linking from the web RCA page to a workbook filtered to a specific capture. The URL format is `https://portal.azure.com/#blade/AppInsightsExtension/UsagesExtension/.../ComponentId/.../WorkbookTemplateName/...`. | The URL format is verbose and Azure-portal-specific. Phase 19.5 can use parameterized workbook links as a "View in Azure" escape hatch alongside the primary web RCA page, not as a replacement. | 19.5 |
| `SecondBrainAlerts` action group | Action group `SecondBrainAlerts` exists in `shared-services-rg` with 3 alert rules: API-Error-Spike, Capture-Processing-Failures, API-Health-Check. Delivers via email to `will@willmacdonald.com` and Azure Monitor push notification to the Azure mobile app. Adding new alert rules is CLI-able via `az monitor metrics alert create` or `az monitor scheduled-query create` -- no portal-only workflow required. | No eval-specific alert rules exist yet. Phase 22 must add rules for `eval.classifier.accuracy < threshold` and `eval.admin.routing_accuracy < threshold`. These are log-based alerts (scheduled query rules), not metric alerts, since eval scores will be logged to `AppTraces` as custom dimensions rather than emitted as OTel metrics. | 22 |
| Alerts on custom App Insights metrics | Two paths: (1) **Log-based alerts** via `az monitor scheduled-query create` -- query `AppTraces` for metric values in Properties, trigger when threshold breached. Works with any data in App Insights tables. (2) **Custom OTel metrics** via `opentelemetry.metrics` -- emit as pre-aggregated metrics, alert via `az monitor metrics alert create`. Path 1 is simpler for Phase 22 since eval scores are already logged to `AppTraces`; Path 2 requires additional OTel meter setup. | Phase 22 should use Path 1 (log-based scheduled query alerts) for eval score degradation. No additional OTel metrics infrastructure needed -- just a KQL query against `AppTraces` where `Properties.eval_metric_name == "classifier.accuracy"` and value below threshold. | 22 |

### 5. Sentry.IO

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Python SDK integrations (backend) | NOT installed on backend. `sentry-sdk` is not in `pyproject.toml`. Backend error tracking goes exclusively through App Insights via `configure_azure_monitor()`. The backend uses Sentry only as a pull source via the Sentry REST API (`spine/adapters/sentry.py`) to fetch mobile error events into spine segments. | No gap -- backend error tracking through App Insights is the correct architecture. Adding `sentry-sdk` to the backend would create duplicate error reporting with no benefit. | - (no downstream impact) |
| React Native SDK post-18-03 | `@sentry/react-native ~7.2.0` installed with: `Sentry.init()` at module scope in `_layout.tsx`, `Sentry.ErrorBoundary` wrapping the root layout, `Sentry.wrap()` on the root component, `reactNavigationIntegration` for navigation breadcrumbs, `tracesSampleRate: 1.0` (100% for single-user), `enabled: !__DEV__` (disabled in dev mode). `Sentry.captureMessage()` called in error paths on the main capture screen. Deferred live test in Checkpoint C to confirm events are arriving in the Sentry dashboard. | Live validation deferred to Checkpoint C. The SDK configuration looks correct but the phone may be running a pre-18-03 EAS build. The `enabled: !__DEV__` guard means Sentry only fires in production EAS builds, not the Metro dev server -- so live testing requires an EAS build on the phone. | 19.5 |
| Custom tags for correlation | `tagTrace(captureTraceId)` in `lib/sentry.ts` calls `Sentry.setTag("capture_trace_id", value)`, `Sentry.setTag("correlation_kind", "capture")`, `Sentry.setTag("correlation_id", value)`. Tags are searchable in the Sentry UI via the `capture_trace_id` tag. `clearTraceTags()` removes them after capture completes. The backend Sentry adapter (`spine/adapters/sentry.py`) passes `tag_filter` to filter events by `app_segment` tag. | If Sentry RN events carry `capture_trace_id` as a tag (confirmed live in Checkpoint C), then mobile Segment View in Phase 19.5 can filter Sentry errors by correlation ID. If tags are absent (SDK misconfigured or events not arriving), Phase 19.5 must source mobile error counts from spine workload events or `AgentDecisionRecords` instead. | 19.4, 19.5 |

### 6. Azure Cosmos DB

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Diagnostic logs + `activityId_g` | Cosmos diagnostic logs land in `AzureDiagnostics` table (Azure diagnostics mode) with `activityId_g` holding the `x-ms-client-request-id` value. Columns use `_s`/`_d`/`_g` suffixes (e.g., `statusCode_s`, `duration_s`, `collectionName_s`). Filter by `Category == "DataPlaneRequests"`. KQL templates in `observability/kql_templates.py` already query this table with `activityId_g` filtering. | The mapping from `capture_trace_id` to `activityId_g` requires that every Cosmos call site passes `capture_trace_id` as `x-ms-client-request-id`. Currently only classifier tools and admin handoff do this (via `trace_headers()`). Other Cosmos call sites (inbox reads, errand operations, affinity rule lookups) do not -- but these are not capture-correlated operations. Phase 19.4 must audit which Cosmos calls are capture-correlated and add `trace_headers()` where missing. | 19.4 |
| Per-operation client-request-id (write path) | `spine/cosmos_request_id.py` provides `trace_headers(request_id)` helper that returns `{"initial_headers": {"x-ms-client-request-id": request_id}}` for unpacking into Cosmos SDK calls. The Python `azure-cosmos` SDK accepts `initial_headers` in `request_options` natively -- no SDK fork or monkey-patching needed. Used in `tools/classification.py` (lines 161, 279) and `processing/admin_handoff.py` (lines 123, 187). | The mechanism works. Phase 19.4 does NOT need bespoke instrumentation for Cosmos -- just apply `trace_headers()` at remaining capture-correlated call sites. The helper and the SDK mechanism are proven. | 19.4 |
| Change Feed -- detect recategorization | Cosmos Change Feed is available for all containers via the Python SDK (`azure-cosmos` async `ChangeFeedIterator`). Latency is near-real-time (typically <2 seconds). Hosting options: (1) in-process with FastAPI via a background `asyncio.Task` (pattern already used for spine evaluator loop and liveness emitters), (2) Azure Functions with Cosmos trigger (separate deployment), (3) separate Container Apps worker. In-process is viable and consistent with existing architecture -- Phase 20 can add a Change Feed listener for `Inbox` and `Errands` containers as another background task alongside spine evaluator. Document mutations for recategorization, HITL bucket changes, and errand re-routes are all detectable as container item updates. | The Change Feed listener needs to: (a) filter for relevant mutation types (bucket field changed, destination field changed), (b) emit label events referencing the `AgentDecisionRecord` for the original classification, (c) handle lease management for exactly-once processing. In-process hosting means no new infrastructure but adds startup complexity. Phase 20 Plan 02 decides hosting. | 20 |

### 7. Azure Container Apps

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Revision metadata + git SHA in name | Container Apps revision names embed git SHA via `--revision-suffix "sha-$(echo $GITHUB_SHA \| cut -c1-7)"` in the deploy workflow. The active revision name is available in-process via the `CONTAINER_APP_REVISION` environment variable (injected by Container Apps runtime automatically). This means the backend can read `os.environ.get("CONTAINER_APP_REVISION")` at request time to get `second-brain-api--sha-3fa1498` or similar, which contains the git commit that built this image. Phase 19.5 can use this as the `agent_release_id` in decision records -- tying each decision to the exact code + agent instruction version that was deployed. | The revision name contains the git SHA but NOT the agent instruction content hash. If agent instructions change in the Foundry portal without a code deploy, the revision name stays the same. The `AgentReleaseManifest` (repo-versioned JSON) is still needed to version agent instructions independently of code deploys. The revision name covers code-side versioning; the manifest covers Foundry-side versioning. Together they form the complete `agent_release_id`. | 19.5 |
| System logs (scale, revisions) | Container Apps system logs (`ContainerAppSystemLogs_CL` in Log Analytics) capture scale events, revision transitions, and container lifecycle events. Console logs (`ContainerAppConsoleLogs_CL`) show stdout/stderr (primarily uvicorn access logs). Python `logger.info()` goes to App Insights, not console logs. | System logs are low-value for observability phases -- they cover infrastructure events (cold starts, scale-to-zero, revision transitions) that are noise for capture-level investigation. No downstream phase depends on these logs. They exist as a fallback diagnostic channel for Container Apps-level issues. | - |

### 8. GitHub Actions

_Rows TBD (Task 9)._

### 9. Expo / EAS

_Rows TBD (Task 10)._

## Live-Evidence Checkpoints

### Checkpoint A -- Foundry trace depth
_TBD (Task 11)._

### Checkpoint B -- Foundry evals applicability
_TBD (Task 12)._

### Checkpoint C -- Sentry RN status on deployed phone
_TBD (Task 13)._

## Phase Impact Addendum

### Phase 19.4 -- Native Span Correlation Tagging
_TBD (Task 14)._

### Phase 19.5 -- Agent Decision Record & RCA View
_TBD (Task 14)._

### Phase 20 -- Labels: Feedback Signals
_TBD (Task 14)._

### Phase 21 -- Eval: Automated Scoring
_TBD (Task 14)._

### Phase 22 -- Self-Monitoring
_TBD (Task 14)._

## Housekeeping Captured
_TBD (Task 15)._
