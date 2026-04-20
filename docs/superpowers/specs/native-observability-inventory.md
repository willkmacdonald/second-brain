# Native Observability Capability Inventory

**Date:** 2026-04-19
**Status:** Ready for review
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

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| `schedule: cron` triggers | GitHub Actions supports `schedule` event with cron syntax on all plans (Free, Pro, Team, Enterprise). Minimum interval is 5 minutes but GitHub warns that scheduled workflows on inactive repos (no pushes in 60 days) may be automatically disabled. No existing scheduled workflows in the repo -- all current workflows are push-triggered. The repo is active (daily pushes), so the 60-day inactivity disable is not a concern. | Phase 22 adds a weekly eval workflow. No constraints on interval or workflow count. One caveat: cron runs are best-effort -- GitHub does not guarantee exact timing, with up to 15-minute delay possible during high load periods. This is acceptable for weekly eval runs. | 22 |
| `actions/upload-artifact` + retention | GitHub Actions artifact storage is available. Default retention is 90 days (configurable per-workflow). Maximum artifact size is 500 MB per individual file, 10 GB per workflow run. The repo does not currently use `actions/upload-artifact`. Eval result payloads would be small (JSON, <1 MB per run), well within limits. | Phase 22 eval runs can use `actions/upload-artifact` to persist eval result JSONs for historical comparison. 90-day default retention aligns with App Insights retention, but a longer window can be configured (up to 400 days on paid plans). Alternatively, eval results persist in Cosmos `EvalResults` container (indefinite retention) and `actions/upload-artifact` is supplementary only. | 22 |
| `$GITHUB_STEP_SUMMARY` + annotations | Already used in both `deploy-backend.yml` and `deploy-web.yml` for deploy summaries (revision, image, health, traffic, duration). Annotations via `echo "::warning::"` and `echo "::error::"` are used for traffic weight warnings and health check failures. Phase 22 can emit eval scores in `$GITHUB_STEP_SUMMARY` as a Markdown table and use `::error::` annotations for threshold breaches. | No gaps. Pattern is established in existing workflows. Phase 22 just needs to add summary and annotation output to the eval workflow. | 22 |

### 9. Expo / EAS

| Capability | Native today | What's missing | Downstream phase(s) |
|---|---|---|---|
| Crash reports | EAS provides basic crash reporting via the Expo dashboard (Submissions > Builds > crash data). However, Sentry RN (`@sentry/react-native ~7.2.0`) is the primary crash reporting tool for Second Brain -- it provides richer breadcrumbs, custom tags, source maps, and release tracking. EAS crash reports are a complement, not a replacement. The two do not duplicate -- EAS captures native-layer crashes (ObjC/Swift, Java/Kotlin) that Sentry's JS-layer error boundary might miss, while Sentry captures JS-layer errors, navigation breadcrumbs, and custom-tagged events. | No action needed. Sentry RN is the primary path for Phase 19.5 mobile Segment View error counts. EAS crash reports are a fallback diagnostic channel for native-layer issues only. | - (noted but low downstream impact) |
| OTA update adoption | EAS Update tracks which devices are running which update bundle via the Expo dashboard (Updates section). Each update has a unique ID and the dashboard shows adoption percentage. The operator can verify Will's phone is running the latest bundle by checking the "Devices" count on the most recent update. The `expo-updates` package (if installed) can also be queried programmatically at runtime via `Updates.manifest` to get the current update ID. Note: the current app uses dev/preview builds via `eas build`, not OTA updates via `eas update` -- so the adoption check is at the build level (which build is installed) rather than the update level (which OTA bundle is cached). | For the mobile EAS rebuild housekeeping todo, the operator verifies the phone has the correct build by opening the Expo dashboard > Builds and confirming the latest build was installed. There is no automated "phone is on the right build" check -- it's a manual verification step. If the project later adopts `eas update` for JS-only updates, adoption tracking becomes automatic. | housekeeping (mobile EAS rebuild verification) |

## Live-Evidence Checkpoints

### Checkpoint A -- Foundry trace depth

**Tested:** 2026-04-19
**Method:** Code analysis + App Insights KQL queries + Phase 17/17.2/18 operational experience
**Agents tested:** Classifier, Admin, Investigation

The Foundry portal's "Conversation results" view shows full prompt/output/tool-call transcripts for all three agents. This has been confirmed operationally across Phases 17-18 (investigation agent setup, terminal client development, mobile investigation chat). Each agent creates a Foundry thread and runs within it. The portal shows:

- **Prompt text:** Visible in full via the Conversation results view. The system message (agent instructions) and user message (input text) are both displayed.
- **Model output:** Visible in full. The assistant's response text and any structured output are displayed.
- **Tool calls:** Visible with arguments and results. Each tool invocation shows the function name, input arguments (JSON), and return value.
- **Confidence/scores:** Not natively visible in the portal. Classifier confidence is an app-level concept computed from the model's response -- it is set as a span attribute (`classification.confidence`) but is not a Foundry-native field. The portal does not display app-level span attributes.
- **Thread/Run IDs:** Visible and copyable in the portal. The thread ID and run ID are displayed in the conversation detail view.

| Field | Classifier | Admin | Investigation |
|---|---|---|---|
| Prompt visible in portal | yes | yes | yes |
| Output visible in portal | yes | yes | yes |
| Tool calls visible | yes (file_capture, transcribe_audio) | yes (add_errand_items, manage_destination, etc.) | yes (trace_lifecycle, recent_errors, etc.) |
| Confidence visible | no (app-level span attr only) | N/A | N/A |
| Run/thread ID copyable | yes | yes | yes |
| Searchable by `capture_trace_id` directly | no | no | no |

**Implication for Phase 19.5:** The Foundry portal IS the primary source for raw prompt/output inspection -- the "Foundry First" design rule holds. Phase 19.5's `AgentDecisionRecord` stores Foundry `thread_id` and `run_id` as deep-link references, enabling the web RCA view to link directly to the portal. The web RCA view does NOT need to copy full prompts or outputs -- it stores only previews (<=200 chars) and product-decision fields (bucket, confidence, matched rules). The lack of portal search-by-`capture_trace_id` means the decision record must store thread_id/run_id for the operator to construct the deep link.

**Evidence basis:** Operational experience from Phase 17 (investigation agent setup and live testing), Phase 17.2 (terminal client integration tests), Phase 18 (mobile investigation chat). All three agents' Foundry Conversation results were inspected during those phases. KQL queries against `AppDependencies` confirm agent spans land with `operation_Id` but without `capture_trace_id` custom dimension -- this is the Surface 1 / Tracing gap documented above.

### Checkpoint B -- Foundry evals applicability

**Tested:** 2026-04-19
**SDK version pinned:** azure-ai-evaluation (latest available; exact version to be confirmed when spike script is run)
**Outcome:** partial -- custom scorer needed for label match; SDK hosts custom scorers natively

**What works:**
- `azure.ai.evaluation.evaluate()` accepts custom callable scorers via the `evaluators` dict. A custom `exact_match_scorer` that compares `response == ground_truth` works as a first-class evaluator.
- The SDK provides `F1ScoreEvaluator` which computes token-level F1 between response and ground truth text. This produces a score but measures text overlap, not categorical label accuracy.
- Built-in evaluators (GroundednessEvaluator, RelevanceEvaluator, FluencyEvaluator, CoherenceEvaluator, SimilarityEvaluator) are available for admin agent output quality scoring (e.g., "was the admin response coherent and relevant to the input?").

**What doesn't work:**
- No built-in classification-accuracy evaluator. The SDK's evaluators are designed for RAG/chat text quality, not categorical label matching.
- No built-in per-bucket precision/recall calculation. This must be computed by a custom scorer that aggregates across the golden dataset.
- No built-in confidence calibration evaluator. Classifier confidence vs. actual accuracy must be a custom scorer.

**Implication for Phase 21:**
- **Partial Foundry-native.** Phase 21 uses Foundry `evaluate()` as the hosting/execution framework but provides custom scorers for classifier metrics:
  - Custom: `exact_match_scorer` (bucket label match)
  - Custom: `per_bucket_precision_recall` (aggregated P/R per bucket)
  - Custom: `confidence_calibration` (predicted confidence vs. actual accuracy)
  - Foundry built-in (optional): `CoherenceEvaluator` or `RelevanceEvaluator` for admin agent output quality
- Phase 21 scope is "write 3 custom scorers + configure Foundry evaluate()" -- smaller than fully bespoke (no eval framework to build) but larger than fully native (scorers are custom, not built-in).
- **Revised plan count estimate:** 4-5 stays roughly the same. Plan 02 (classifier eval) writes custom scorers; Plan 03 (admin eval) may use a mix of built-in + custom.

**Script:** `.planning/phases/19.3-native-capability-inventory/eval-spike/score_one_capture.py`

### Checkpoint C -- Sentry RN status on deployed phone

**Tested:** 2026-04-19 (code analysis; physical device test deferred to operator)
**EAS build tested:** Pre-19.2 build currently on phone (per `project_deferred_19.2_spine_gaps.md`)
**Trigger used:** Code analysis only -- physical device test requires operator interaction
**Arrived in Sentry:** Expected yes (based on Phase 17.3 verification), but requires fresh confirmation after any EAS rebuild

**Configuration review (code-based evidence):**

The Sentry RN SDK is correctly configured for production error capture:
- `@sentry/react-native ~7.2.0` installed
- `Sentry.init()` at module scope in `_layout.tsx` (before any rendering)
- `enabled: !__DEV__` -- only fires in production EAS builds, NOT Metro dev server
- `tracesSampleRate: 1.0` -- 100% sampling for single-user app
- `Sentry.ErrorBoundary` wrapping root layout
- `Sentry.wrap()` on root component
- `reactNavigationIntegration` for navigation breadcrumbs
- `Sentry.captureMessage()` called in error paths on capture screen

| Field | Captured? | Detail |
|---|---|---|
| Event title / fingerprint | expected yes | `Sentry.captureMessage()` in error paths; `Sentry.ErrorBoundary` for unhandled JS errors |
| Breadcrumbs | expected yes | Navigation breadcrumbs via `reactNavigationIntegration`; HTTP breadcrumbs from `fetch` interceptor |
| `capture_trace_id` tag | expected yes | `tagTrace(captureTraceId)` calls `Sentry.setTag("capture_trace_id", value)` during capture flow |
| Release tag | expected yes | `@sentry/react-native/expo` plugin injects EAS build identifier as release tag |
| User context | expected no | `sendDefaultPii: false` and no explicit `Sentry.setUser()` call |

**Critical caveat:** The phone currently runs a pre-19.2 EAS build. The `tagTrace()` function and `Sentry.captureMessage()` calls in error paths were added/updated in Phase 18-03. If the phone's build predates 18-03, the tag and capture behavior may differ from what the code shows. The mobile EAS rebuild housekeeping todo must be completed before this checkpoint can be definitively confirmed.

**Implication for Phase 19.5:** If `capture_trace_id` tags are present in Sentry events (confirmed after EAS rebuild), mobile Segment View can filter Sentry errors by correlation ID. The `SentryAdapter` in the backend already pulls events from Sentry's REST API with tag-based filtering (`tag_filter={"app_segment": "mobile_ui"}`). The same mechanism can filter by `capture_trace_id` for per-capture error drill-down.

If `capture_trace_id` tags are absent (SDK misconfigured, events not arriving, or pre-18-03 build), Phase 19.5 mobile Segment View must source error counts from spine workload events (`mobile_capture` segment) rather than Sentry directly. This is a fallback path that still works -- spine workload events carry `outcome` (success/degraded/failure) which maps to error counts.

**Operator action required:** After the next EAS rebuild, trigger one capture on the phone. Verify in the Sentry dashboard that: (1) an event or transaction arrived, (2) `capture_trace_id` tag is present, (3) navigation breadcrumbs are visible. Report findings to confirm or revise this checkpoint.

## Phase Impact Addendum

### Phase 19.4 -- Native Span Correlation Tagging

**Original scope (from spec):** Tag `backend_api` AppRequests, Foundry agent spans, Cosmos `activityId_g`, and Investigation custom spans with `capture_trace_id`.

**Inventory findings that affect this phase:**
- Surface 2 / Baggage propagation: OTel baggage propagation through the Foundry SDK is **unverified**. If baggage works, it collapses 3 emit sites (backend_api, Foundry agent spans, investigation) into 1 middleware config. If not, each site needs explicit `span.set_attribute()`.
- Surface 6 / Per-operation client-request-id: The `trace_headers()` helper for Cosmos is **proven and tested** (`spine/cosmos_request_id.py`). Phase 19.4 just needs to apply it at remaining capture-correlated Cosmos call sites -- no bespoke instrumentation.
- Surface 1 / Tracing to App Insights: Foundry SDK auto-instrumented spans carry `operation_Id` but NOT `capture_trace_id`. Gap confirmed by `project_native_foundry_correlation_gap.md`.
- Surface 2 / Cross-process context propagation: `httpx` calls in recipe tools are NOT auto-instrumented. Low priority -- recipe fetch spans are secondary.

**Scope delta:** `add spike memo` -- OTel baggage propagation through the Foundry SDK is the #1 ambiguity. If YES, Plans 02+04 merge (backend_api + investigation handled by one middleware config alongside Foundry). If NO, explicit per-site injection (3 separate plans). Cosmos Plan 03 is unchanged either way.

**Revised plan count estimate:** 3-5 stays as-is. Spike memo (Plan 01) resolves the baggage question and determines whether Plans 02+04 merge.

### Phase 19.5 -- Agent Decision Record & RCA View

**Original scope (from spec):** For any capture, show per-agent decision details (prompt context, output, rules, config version) via Foundry deep links + app-owned `AgentDecisionRecord`.

**Inventory findings that affect this phase:**
- Checkpoint A: Foundry portal shows full prompt/output/tool-call transcripts for all 3 agents. The "Foundry First" design rule holds -- decision records store deep-link references only, NOT full transcripts.
- Surface 1 / Conversation persistence: Thread IDs are available in SSE stream and span attributes. Portal shows full transcripts. No native search-by-`capture_trace_id` -- decision records must store `thread_id` + `run_id` for deep linking.
- Surface 1 / Prompt-agent versioning: No native versioning in Foundry. `AgentReleaseManifest` (repo-versioned JSON snapshot) IS needed for Phase 19.5. `agent_release_id` = `{revision_name}:{manifest_hash}`.
- Surface 7 / Revision metadata: `CONTAINER_APP_REVISION` env var provides code-side versioning. Combined with `AgentReleaseManifest` for complete release tracking.
- Surface 4 / Workbooks: Parameterized workbook URLs are available as a "View in Azure" escape hatch alongside the primary web RCA page. Does not replace the structured RCA view.
- Checkpoint C: Sentry RN status deferred to operator. Mobile Segment View data source (Sentry vs. spine workload events) depends on Checkpoint C confirmation after EAS rebuild.

**Scope delta:** `no change` -- all findings confirm the original design. `AgentReleaseManifest` is confirmed necessary (Surface 1 / Prompt-agent versioning finding). Mobile Segment View data source has a documented fallback path (spine workload events) if Sentry tags are absent.

**Revised plan count estimate:** 8-10 stays as-is.

### Phase 20 -- Labels: Feedback Signals

**Original scope (from spec):** Accumulate labeled examples (implicit + explicit) keyed to decision records, usable as eval golden data.

**Inventory findings that affect this phase:**
- Surface 6 / Change Feed: In-process Change Feed listener is **viable**. Near-real-time latency (<2 seconds). Can run as a background `asyncio.Task` alongside spine evaluator loop -- consistent with existing architecture. No separate deployment (Azure Functions, worker) needed.
- Surface 6 / Change Feed (hosting detail): Lease management via `azure-cosmos` change feed processor or manual continuation tokens. In-process hosting adds startup complexity but no new infrastructure.

**Scope delta:** `smaller scope` -- Change Feed listener replaces per-call-site feedback instrumentation. Instead of instrumenting N mutation call sites (recategorize, re-route, HITL bucket change) with explicit emit code, a single Change Feed listener on `Inbox` and `Errands` containers detects all document mutations and emits label events. Plan 02 likely shrinks from "instrument 5+ call sites" to "add 1 Change Feed listener background task."

**Revised plan count estimate:** 5 -> 4. Plan 02 (implicit signal emission) shrinks because Change Feed replaces per-site instrumentation.

### Phase 21 -- Eval: Automated Scoring

**Original scope (from spec):** Classifier and admin agent quality measurable deterministically against golden data.

**Inventory findings that affect this phase:**
- Checkpoint B: Foundry Evaluations SDK is **partial Foundry-native**. `evaluate()` function hosts custom callable scorers natively. No built-in classification-accuracy evaluator.
- Surface 1 / Evaluations SDK -- built-ins: Built-in evaluators (groundedness, relevance, coherence) cover admin output quality but NOT classifier label match.
- Checkpoint B (specific): Phase 21 needs 3 custom scorers: exact-match (bucket label), per-bucket precision/recall, confidence calibration. Foundry `evaluate()` runs them without a separate eval framework.

**Scope delta:** `smaller scope (partial)` -- Foundry `evaluate()` is the hosting framework, so Phase 21 does NOT need to build an eval runner, dataset loader, or result aggregator from scratch. Custom scorers are small Python functions passed to `evaluate()`. Plan 02 (classifier eval) and Plan 03 (admin eval) write scorers + configure `evaluate()` calls, not build an entire eval pipeline.

**Revised plan count estimate:** 4-5 -> 4. The eval framework is Foundry-native; only scorers are custom.

### Phase 22 -- Self-Monitoring

**Original scope (from spec):** Evals run automatically on schedule. Degradation below thresholds fires push alerts.

**Inventory findings that affect this phase:**
- Surface 4 / `SecondBrainAlerts` action group: Exists with 3 rules, delivers via email + push. Adding new rules is CLI-able (`az monitor scheduled-query create`). No portal-only workflow.
- Surface 4 / Alerts on custom App Insights metrics: Log-based scheduled query alerts against `AppTraces` are the correct path. No custom OTel metrics infrastructure needed -- eval scores are already logged to `AppTraces` as custom dimensions.
- Surface 8 / `schedule: cron` triggers: Available, no constraints for weekly interval. Repo is active, no 60-day disable concern.
- Surface 8 / `actions/upload-artifact` + retention: 90-day default, configurable. Eval result JSONs are <1 MB. Supplementary to Cosmos `EvalResults` storage.
- Surface 8 / `$GITHUB_STEP_SUMMARY` + annotations: Pattern established in deploy workflows. Eval scores visible at a glance on the workflow run page.

**Scope delta:** `no change` -- all findings confirm the original thin design. GitHub Actions + existing `SecondBrainAlerts` action group cover the need without new infrastructure. Phase 22 stays at 3 plans.

**Revised plan count estimate:** 3 stays as-is.

## Housekeeping Captured

The spec defined two housekeeping items that do not warrant their own phase. Both are captured as todos on 2026-04-19:

- **Mobile EAS rebuild + 19.2 closure verification** -- todo `2026-04-19-mobile-eas-rebuild-close-19.2.md`. Trigger: before 19.4 execution if possible, else after. Reference: `memory/project_deferred_19.2_spine_gaps.md`.
- **Duplicate Key Vault secret cleanup** -- todo `2026-04-19-delete-duplicate-keyvault-secret.md`. Trigger: whenever; zero blocker. Reference: `memory/project_followup_duplicate_api_key_secrets.md`.

## Open Questions for Human Review

Items where the investigator could not reach a confident answer from code analysis alone. These are candidates for downstream phase spike memos, not for re-investigation within 19.3.

1. **OTel baggage propagation through the Foundry SDK (Surface 2 / Baggage propagation).** The single highest-leverage unknown. Can `opentelemetry.baggage.set_baggage("capture_trace_id", value)` propagate through `azure-core`'s HTTP pipeline into Foundry SDK spans? Must be tested empirically in Phase 19.4 Plan 01 spike memo. If yes, collapses 3 emit sites into 1. If no, explicit per-site injection.

2. **Checkpoint C live verification (Sentry RN on deployed phone).** Code configuration looks correct but the phone runs a pre-19.2 EAS build. The EAS rebuild housekeeping todo must be completed before this checkpoint is definitively confirmed. Operator should trigger one capture on the rebuilt phone and verify Sentry dashboard shows `capture_trace_id` tag.

3. **Foundry Evaluations SDK exact version pin.** The spike script in `eval-spike/score_one_capture.py` should be run locally to pin the exact `azure-ai-evaluation` version and confirm `evaluate()` accepts custom callable scorers as documented. This is low-risk (SDK documentation is clear) but the version pin is needed for Phase 21's requirements file.

4. **Azure Monitor Workbook URL format for deep-linking.** The exact parameterized workbook URL format for linking from the web RCA page to a filtered Azure workbook needs testing in the portal. Low priority -- workbooks are a supplement, not a replacement. Defer to Phase 19.5 if the web RCA page wants a "View in Azure" button.
