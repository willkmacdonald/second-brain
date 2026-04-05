# Project Research Summary

**Project:** The Active Second Brain -- v3.1 Observability & Evals
**Domain:** AI agent observability, natural language telemetry investigation, LLM evaluation framework
**Researched:** 2026-04-04
**Confidence:** HIGH

## Executive Summary

v3.1 adds three capabilities to the Second Brain: (1) a conversational investigation agent that translates natural language into KQL queries over App Insights, accessible from both mobile and Claude Code, (2) an evaluation framework that measures Classifier and Admin Agent quality using golden datasets, implicit signals, and deterministic metrics, and (3) a self-monitoring loop that alerts when quality degrades. The existing v3.0 infrastructure already logs rich telemetry (per-capture trace IDs, component tags, OTel spans, four KQL query templates, Azure Monitor alerts) -- v3.1 makes that telemetry queryable and actionable without opening the Azure Portal.

The recommended approach is to build two independent tracks that converge late. The **investigation track** (App Insights query integration, Foundry investigation agent, mobile chat, MCP tool for Claude Code) delivers immediate operational value and depends on `azure-monitor-query` SDK and the existing Foundry Agent Service pattern. The **eval track** (golden datasets, custom evaluators via `azure-ai-evaluation`, feedback collection, score tracking, degradation alerts) provides long-term quality assurance and depends on deterministic metrics first, LLM-as-judge second. Both tracks share a foundation phase (LogsQueryClient setup, new Cosmos containers, workspace-compatible KQL templates).

The primary risks are KQL schema mismatches between portal and programmatic queries (already documented in project memory, also hit by the Azure MCP Server team in GitHub #250), LLM hallucination of KQL table/column names (mitigated by template-first query construction with structured tool parameters), and self-enhancement bias in evals (mitigated by using deterministic metrics for classification accuracy instead of LLM-as-judge). The eval SDK landscape is in flux (`azure-ai-evaluation` migrating toward `azure-ai-projects` v2), so evaluator logic should be written as plain Python functions first, wrapped for whichever SDK is current at build time.

## Key Findings

### Recommended Stack

The backend adds two Azure SDKs: `azure-monitor-query` (v2.0.0, GA) for programmatic KQL queries against the Log Analytics workspace, and `azure-ai-evaluation` (v1.16.x) for the eval framework with custom evaluators and batch evaluation. A standalone MCP server using the official `mcp` package (v1.27.0, includes FastMCP built-in) provides Claude Code integration via stdio transport. The mobile app needs `victory-native` for dashboard charts only if text metrics prove insufficient -- no other new dependencies. The chat UI is a custom FlatList component reusing the existing `react-native-sse` streaming infrastructure.

**Core technologies:**
- `azure-monitor-query` (>=2.0.0): Programmatic KQL queries via async `LogsQueryClient` -- reuses `DefaultAzureCredential`, no pandas needed
- `azure-ai-evaluation` (>=1.16.0): Batch eval API with custom code-based evaluators, `AIAgentConverter` for Foundry agent thread-to-eval conversion
- `mcp` (>=1.27.0): MCP server for Claude Code with stdio transport -- standalone process, NOT in the Docker image
- Custom FlatList chat: Zero-dependency chat UI for investigation agent, avoids `react-native-gifted-chat` compatibility issues

**Critical version notes:**
- `azure-monitor-query` v2.0.0 removed `MetricsClient` (moved to separate package) -- irrelevant since we only need logs queries
- `azure-ai-projects` is already a transitive dependency; pin explicitly only if needed for `AIAgentConverter`, watch for version conflicts with `agent-framework-azure-ai`
- `azure-ai-evaluation` pulls in ~50-100MB of dependencies; consider `[project.optional-dependencies]` under `eval` extra to keep Docker image lean

### Expected Features

**Must have (table stakes):**
- TS-1: Investigation agent backend (NL to KQL to execute to summarize)
- TS-2: Mobile chat interface for investigation agent (SSE streaming, multi-turn)
- TS-3: Claude Code MCP tool for App Insights queries (evaluate Azure MCP Server first, build custom only if needed)
- TS-4: Classifier golden dataset + accuracy eval (50-100 curated captures, deterministic metrics)
- TS-5: Admin Agent quality eval (task adherence, routing accuracy, tool call correctness)
- TS-6: Eval score tracking over time (Cosmos + App Insights custom events)
- TS-7: Alert on eval score degradation (Azure Monitor scheduled query rules)

**Should have (differentiators):**
- D-1: Implicit quality signals from user behavior (recategorizations, HITL selections, errand re-routing -- zero extra effort)
- D-2: Mobile observability dashboard (3-5 metric cards, text-only initially)
- D-5: Quick action chips in investigation chat (one-tap common queries)

**Defer (even within v3.1):**
- D-2 charts: Start text-only, add Victory Native charts only if proven insufficient
- D-3: Auto-promotion of quality signals to golden dataset (start with manual review)
- D-4: On-demand eval trigger from mobile (add after eval pipeline is proven)
- Historical trend charts on mobile (use Foundry portal for visual analytics)
- Multi-agent pipeline eval (evaluate Classifier and Admin independently first)

### Architecture Approach

The architecture extends the existing three-layer pattern (Mobile, FastAPI backend on ACA, Azure services) with minimal new integration surfaces. The investigation agent is a third persistent Foundry agent following the identical `ensure_*_agent()` pattern. It uses parameterized @tool functions that construct KQL internally -- not free-form LLM-generated KQL -- and streams responses via AG-UI SSE protocol with `TEXT_MESSAGE_CONTENT` events. The MCP server is a completely standalone Python process (stdio transport) that queries App Insights directly; it does NOT go through the backend API. The eval framework runs as a CLI + GitHub Actions job, NOT inside the FastAPI request-response cycle. Three new Cosmos containers (Feedback, EvalResults, GoldenDataset) store evaluation data.

**Major components:**
1. `api/insights.py` + `streaming/insights_adapter.py` -- Investigation agent chat endpoint with SSE streaming
2. `tools/insights.py` -- @tool functions with parameterized KQL queries (query_captures, get_system_health, trace_capture, get_bucket_distribution)
3. `agents/investigator.py` -- Third persistent Foundry agent registration (mirrors Classifier/Admin pattern)
4. `mcp/server.py` -- Standalone MCP server for Claude Code with raw KQL capability (guarded with timeout + row limits)
5. `api/feedback.py` -- Explicit feedback collection (thumbs up/down on inbox items)
6. `evals/` -- Golden dataset management, custom evaluators, eval runner CLI
7. Mobile Insights tab -- Chat UI (FlatList) + dashboard cards (text metrics)

### Critical Pitfalls

1. **KQL schema mismatch** (CRITICAL) -- Portal uses `AppTraces`/`AppRequests`, programmatic SDK uses `traces`/`requests`. Build and validate workspace-compatible KQL templates before any agent logic. The Azure MCP Server had this exact bug (GitHub #250).
2. **LLM KQL hallucination** (CRITICAL) -- GPT-4o will guess wrong table/column names without explicit schema grounding. Use parameterized @tool functions with structured parameters, NOT free-form KQL generation. Template-first, free-form only as guarded fallback.
3. **Partial results treated as success** (CRITICAL) -- `LogsQueryClient` returns `LogsQueryPartialResult` (not an exception) on timeout. Always check `response.status == LogsQueryStatus.SUCCESS`. Build a query wrapper that normalizes all statuses with an `is_partial` flag.
4. **Self-enhancement bias in evals** (CRITICAL) -- Using GPT-4o to judge GPT-4o classification gives inflated scores. Use deterministic metrics (exact match, confusion matrix, per-bucket precision/recall) for classifier accuracy. Reserve LLM-as-judge for Admin Agent subjective quality only.
5. **Eval SDK in flux** (MODERATE) -- `azure-ai-evaluation` migrating toward `azure-ai-projects` v2. Write evaluators as plain Python functions first, wrap for SDK second. Keep the eval pipeline thin and decoupled.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Query Foundation + Cosmos Containers
**Rationale:** Everything downstream depends on the ability to run KQL programmatically and store evaluation data. This is a pure infrastructure phase with no user-facing output.
**Delivers:** `LogsQueryClient` initialization in lifespan, `log_analytics_workspace_id` config setting, workspace-compatible KQL template library (translated from existing portal-schema .kql files), query execution wrapper with partial-result handling, three new Cosmos containers (Feedback, EvalResults, GoldenDataset) with Pydantic models, `Log Analytics Reader` RBAC for Container App managed identity.
**Addresses:** Foundation for TS-1 through TS-7
**Avoids:** KQL schema mismatch (Pitfall 1), partial results as success (Pitfall 3)

### Phase 2: Investigation Agent (Backend)
**Rationale:** Highest user value -- ability to ask "what happened?" in natural language. Depends on Phase 1's query infrastructure.
**Delivers:** Investigation Agent registered in Foundry, `agents/investigator.py`, `tools/insights.py` with parameterized @tools (query_captures, get_system_health, trace_capture, get_bucket_distribution), `api/insights.py` chat endpoint, `streaming/insights_adapter.py` with TEXT_MESSAGE_CONTENT events.
**Addresses:** TS-1
**Avoids:** LLM KQL hallucination (Pitfall 2) via parameterized tools, SSE pattern mismatch (Pitfall 14) via separate adapter

### Phase 3: Mobile Investigation Chat
**Rationale:** Puts the investigation agent in Will's hands on his primary device. Depends on Phase 2's backend.
**Delivers:** Insights screen in mobile app, FlatList chat UI with SSE streaming, quick action chips (D-5), dashboard summary cards with text metrics (D-2).
**Addresses:** TS-2, D-2, D-5
**Avoids:** Dashboard over-engineering (Pitfall 10) by starting text-only

### Phase 4: Claude Code MCP Tool
**Rationale:** Developer experience during coding sessions. Fully independent of Phases 2-3 (queries App Insights directly, standalone process). Can run in parallel with Phase 3.
**Delivers:** Standalone `mcp/server.py` with 5 tools (query_app_insights, get_system_health, recent_captures, trace_capture, recent_errors), Claude Code project-level `.mcp.json` configuration.
**Addresses:** TS-3
**Avoids:** Build vs buy (Pitfall 7) by evaluating Azure MCP Server first, timeout issues (Pitfall 6) via stdio transport + bounded queries

### Phase 5: Feedback Collection + Implicit Signals
**Rationale:** Collects the evaluation data that Phase 6 consumes. Must precede the eval framework so the pipeline has real data from day one.
**Delivers:** `api/feedback.py` endpoint, FeedbackDocument model, thumbs up/down on mobile inbox detail, evaluation event tracking on recategorize/HITL/errand routing endpoints.
**Addresses:** D-1, prerequisite for TS-4/TS-5
**Avoids:** Missing feedback storage (Pitfall 9) by building the storage layer before the eval pipeline

### Phase 6: Eval Framework (Classifier + Admin Agent)
**Rationale:** Core quality measurement. Depends on Phase 1 (Cosmos containers), Phase 5 (feedback data), and existing App Insights telemetry for implicit signals.
**Delivers:** Golden dataset seeding CLI, custom evaluators (BucketAccuracyEvaluator, ConfidenceCalibrationEvaluator, ImplicitSignalEvaluator, ErrandRoutingAccuracyEvaluator), eval runner CLI (`uv run -m second_brain.evals.runner`), Admin Agent eval with TaskAdherenceEvaluator + ToolCallAccuracyEvaluator.
**Addresses:** TS-4, TS-5
**Avoids:** Self-enhancement bias (Pitfall 4) via deterministic metrics first, SDK churn (Pitfall 5) via decoupled evaluator logic, golden dataset rot (Pitfall 8) by building from production captures with refresh workflow, sandbox limits (Pitfall 13) by preparing self-contained JSONL

### Phase 7: Self-Monitoring Loop
**Rationale:** Closes the loop -- automated eval runs, score tracking, degradation alerts, trend visibility. Depends on Phase 6's eval pipeline being functional.
**Delivers:** Eval score persistence to Cosmos + App Insights custom events (TS-6), Azure Monitor scheduled query alerts for score degradation (TS-7), GitHub Actions weekly eval cron, eval scores visible in mobile dashboard, on-demand eval trigger (D-4), golden dataset evolution with manual review (D-3).
**Addresses:** TS-6, TS-7, D-3, D-4
**Avoids:** 30-day App Insights retention (Pitfall 12) by persisting results to Cosmos

### Phase Ordering Rationale

- **Phase 1 must come first:** `LogsQueryClient` and Cosmos containers are prerequisites for everything. The workspace-compatible KQL template library prevents the most critical pitfall (schema mismatch) from cascading into later phases.
- **Phases 2-3 are the highest-value track:** Natural language investigation delivers immediate operational value. These have the clearest dependency chain (backend agent, then mobile UI).
- **Phase 4 is fully independent:** The MCP server is a standalone process that queries App Insights directly. It can be built in parallel with Phase 3 or deferred with no impact on other phases.
- **Phase 5 before Phase 6:** The eval framework consumes feedback data. Building feedback collection first ensures the eval pipeline has real data to work with.
- **Phases 6-7 are the quality track:** Eval framework first (measure quality), self-monitoring second (alert on degradation). Placing this track later also gives time for implicit signals to accrue from normal usage.
- **Two tracks converge at Phase 7:** Dashboard shows eval scores, investigation agent can query eval results, and degradation alerts tie investigation to evaluation.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** Investigation agent system prompt engineering -- needs careful schema grounding, few-shot KQL examples, and testing against real workspace data. The NL-to-KQL translation quality is the highest-risk technical area in the milestone.
- **Phase 6:** Eval SDK state check -- verify `azure-ai-evaluation` vs `azure-ai-projects` v2 migration status at build time. Custom evaluator sandbox constraints need validation against actual requirements. The `AIAgentConverter` API for Admin Agent thread-to-eval conversion may need implementation-time research.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Well-documented Azure SDK (`azure-monitor-query`), standard Cosmos container setup. Existing project memory already covers the schema mismatch.
- **Phase 3:** Standard React Native FlatList + existing SSE infrastructure. No new patterns.
- **Phase 4:** MCP server with stdio transport is well-documented. Evaluate Azure MCP Server first -- may not need custom build at all.
- **Phase 5:** Simple CRUD endpoint + Cosmos writes. Follows existing patterns.
- **Phase 7:** Azure Monitor scheduled query rules already built in v3.0 Phase 14. GitHub Actions cron is standard.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommended packages are GA with official Microsoft/MCP SDK docs. `azure-ai-evaluation` is the newest (v1.16.x) but well-documented. Victory Native is MEDIUM (needs Expo SDK 54 compatibility validation at install time). |
| Features | MEDIUM-HIGH | Feature scope is well-defined with clear dependency chains. Two independent tracks reduce risk. The investigation agent's NL-to-KQL quality is the main uncertainty -- template-first approach mitigates this. |
| Architecture | HIGH | Extends existing patterns (persistent Foundry agent, SSE streaming, Cosmos containers). No new architectural paradigms. MCP server is the only fully new component type, and it is standalone with no integration surface into the backend. |
| Pitfalls | HIGH | All critical pitfalls verified against official docs, academic papers, and project history. The KQL schema mismatch is already documented in project memory. Self-enhancement bias is well-established in literature. |

**Overall confidence:** HIGH

### Gaps to Address

- **Victory Native + Expo SDK 54 compatibility:** MEDIUM confidence. Use `npx expo install` and validate at install time. Fallback: text-only metrics (preferred for v3.1 anyway). Charts are deferred by default.
- **`azure-ai-evaluation` SDK stability:** Check migration status toward `azure-ai-projects` v2 when Phase 6 starts. If v2 is GA, use it directly. If still beta, use stable `azure-ai-evaluation` with an abstraction layer over evaluator functions.
- **Azure MCP Server current state:** The App Insights table bug (GitHub #250) was fixed in PR #280, but the exact release version needs verification against the real workspace. Test before deciding build vs buy for Phase 4.
- **Log Analytics Reader RBAC:** Container App managed identity and local dev credential both need `Log Analytics Reader` role on the workspace. Verify RBAC is in place before Phase 1 integration testing.
- **Investigation Agent prompt quality:** NL-to-KQL translation quality depends heavily on system prompt engineering with schema context and few-shot examples. Cannot be assessed until the agent is built and tested against real queries. Budget time for prompt iteration in Phase 2.

## Sources

### Primary (HIGH confidence)
- [azure-monitor-query SDK docs](https://learn.microsoft.com/en-us/python/api/overview/azure/monitor-query-readme?view=azure-python) -- LogsQueryClient, async client, partial results, timeout handling
- [azure-ai-evaluation SDK docs](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme?view=azure-python) -- evaluate() API, custom evaluators, batch evaluation
- [Agent Evaluation with Foundry SDK](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/agent-evaluate-sdk?view=foundry-classic) -- AIAgentConverter, TaskAdherenceEvaluator, ToolCallAccuracyEvaluator
- [Custom Evaluators in Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/evaluation-evaluators/custom-evaluators?view=foundry-classic) -- Code-based evaluators, sandbox constraints, supported packages
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) -- FastMCP built-in, stdio transport, v1.27.0
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) -- Transport types, tool configuration
- [Azure MCP Server Monitor Tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/azure-monitor) -- query_workspace_logs, 11 Monitor tools
- [NL2KQL Research (arxiv 2404.02933)](https://arxiv.org/html/2404.02933v1) -- Schema hallucination in NL-to-KQL translation
- [Azure MCP Server Issue #250](https://github.com/Azure/azure-mcp/issues/250) -- App Insights table query failures, fixed in PR #280

### Secondary (MEDIUM confidence)
- [LLM-as-a-Judge (Weights & Biases)](https://wandb.ai/site/articles/exploring-llm-as-a-judge/) -- Self-enhancement bias, position bias, evaluation patterns
- [Azure AI Projects v2 Migration](https://medium.com/@badrvkacimi/migrating-to-azure-ai-projects-v2-the-unified-foundry-sdk-you-need-to-know-0102d969df1f) -- SDK consolidation direction
- [Golden Dataset Building (Maxim AI)](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/) -- Dataset curation, refresh patterns
- [Victory Native for Expo](https://kushabhi5.medium.com/using-victory-native-for-charts-in-an-expo-react-native-project-bd57d805cb8c) -- Expo compatibility reference
- [Implicit Feedback Patterns (Winder AI)](https://winder.ai/user-feedback-llm-powered-applications/) -- Zero-effort quality signals from user behavior

### Tertiary (LOW confidence)
- [Azure Monitor KQL Injection](https://securecloud.blog/2022/04/27/azure-monitor-malicious-kql-query/) -- KQL injection risks (read-only mitigates severity)

---

## Files in This Research Set

| File | Purpose |
|------|---------|
| `.planning/research/STACK.md` | Technology recommendations -- 4 new backend packages, MCP server, mobile charting, what NOT to add |
| `.planning/research/FEATURES.md` | Feature landscape -- 7 table stakes, 5 differentiators, 11 anti-features, dependency graph, user scenarios |
| `.planning/research/ARCHITECTURE.md` | Architecture patterns -- investigation agent, MCP server, eval pipeline, data flows, build order |
| `.planning/research/PITFALLS.md` | Domain pitfalls -- 5 critical, 5 moderate, 4 minor, phase-specific warnings |
| `.planning/research/SUMMARY.md` | This file -- executive summary and roadmap implications |

---
*Research completed: 2026-04-04*
*Ready for roadmap: yes*
