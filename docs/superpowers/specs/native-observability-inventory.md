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

_Rows TBD (Task 3)._

### 3. Application Insights / Log Analytics

_Rows TBD (Task 4)._

### 4. Azure Monitor

_Rows TBD (Task 5)._

### 5. Sentry.IO

_Rows TBD (Task 6)._

### 6. Azure Cosmos DB

_Rows TBD (Task 7)._

### 7. Azure Container Apps

_Rows TBD (Task 8)._

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
