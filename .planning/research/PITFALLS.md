# Domain Pitfalls

**Domain:** Observability investigation agent + eval framework for existing capture-and-classify system
**Researched:** 2026-04-04

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: KQL Schema Mismatch -- Portal Queries vs Programmatic API Queries

**What goes wrong:** The existing `.kql` files in `backend/queries/` use `AppTraces`, `AppRequests`, `AppExceptions`, `AppDependencies` (Application Insights portal schema). But `azure-monitor-query` `LogsQueryClient` hits the Log Analytics workspace endpoint, where those table names do not exist. The workspace-based schema uses `traces`, `requests`, `exceptions`, `dependencies` with different column casing. Every programmatic query will fail or return empty results.

**Why it happens:** Application Insights has two query contexts: (1) the App Insights "Logs" blade in the portal, which auto-translates `AppTraces` to the underlying workspace tables, and (2) direct Log Analytics workspace queries via the REST API / Python SDK, which require the raw workspace table names. When you copy-paste queries that work in the portal into programmatic code, they break. The project already documented this in MEMORY.md ("Workspace-based App Insights uses `traces`/`requests` tables, not `AppTraces`/`AppRequests`") but the existing KQL files still use the portal schema.

**Consequences:** The investigation agent returns empty results or errors for every question. If the agent wraps errors poorly, users get "no data found" instead of understanding the schema mismatch. This is insidious because the same queries work fine when manually copy-pasted into the portal. The official Azure MCP Server had this exact bug (GitHub issue #250) requiring a fix in PR #280.

**Prevention:**
- Maintain two sets of KQL templates: portal-compatible (existing files, for human use) and workspace-compatible (new files, for programmatic queries via `LogsQueryClient`)
- Validate every KQL template against `LogsQueryClient` before shipping
- The investigation agent's KQL generation system prompt must specify workspace schema table names explicitly: `traces` not `AppTraces`, `customDimensions` column access patterns, lowercase column names where they differ
- Build a schema reference document that maps portal names to workspace names for the investigation agent's context

**Detection:** Agent returns zero rows for queries that should have data. Test early with a simple `traces | take 1` query through the SDK.

**Confidence:** HIGH -- Already documented in project MEMORY.md. Azure MCP Server had the same issue (GitHub #250, fixed in PR #280). Verified against Azure Monitor Query SDK documentation.

**Phase guidance:** Must be addressed in the very first phase that introduces programmatic KQL queries. Build and validate a workspace-compatible KQL template library before any agent logic.

### Pitfall 2: LLM KQL Hallucination -- Wrong Tables, Columns, and Operators

**What goes wrong:** When the investigation agent translates natural language to KQL, the LLM hallucinates table names, column names, operators, and filter values that do not exist in the actual schema. Microsoft's NL2KQL research (arxiv 2404.02933) confirms that schema hallucinations dominate production failures, with filter-literal accuracy dropping as low as 0.10 on novel schemas.

**Why it happens:** GPT-4o has trained on general KQL examples from the internet, but the Second Brain's App Insights workspace has a specific schema with specific custom dimensions (`capture_trace_id`, `component`, `event_type`). Without explicit schema grounding, the LLM guesses column names from training data. It might generate `customDimensions.traceId` instead of `customDimensions.capture_trace_id`, or use `AppTraces` instead of `traces`, or invent operators that work in SQL but not KQL.

**Consequences:** Users get wrong answers, empty results, or runtime errors. Worse: the agent might return plausible-looking but incorrect data (querying the wrong table returns unrelated rows matching loose filters). For a single-user system where Will trusts the answers, this is dangerous -- bad data looks like good data.

**Prevention:**
- Provide the exact schema in the investigation agent's system prompt: table names, column names, custom dimension keys, data types, and example values
- Use a curated library of KQL templates with parameterized slots for common questions (template-first approach, not free-form KQL generation)
- Implement a two-stage approach: (1) map user intent to a known query template, (2) fall back to free-form KQL only for novel questions with explicit schema injection and few-shot examples
- Add a KQL validation step before execution -- at minimum, check that referenced tables exist in a whitelist (`traces`, `requests`, `exceptions`, `dependencies`, `customEvents`, `customMetrics`)
- Include 5-10 example KQL queries (the existing workspace-compatible templates) as few-shot examples in the system prompt

**Detection:** Track "query syntax error" vs "query returned 0 rows" vs "query succeeded" rates. Alert when failure rate exceeds 20%.

**Confidence:** HIGH -- NL2KQL paper and multiple production reports confirm this. The existing custom dimensions structure is non-standard enough to guarantee hallucination without grounding.

**Phase guidance:** Address in the investigation agent phase. Build template-based queries first, add free-form as a stretch goal with guardrails.

### Pitfall 3: LogsQueryClient Partial Results and Timeouts Treated as Success

**What goes wrong:** `azure-monitor-query` `LogsQueryClient.query_workspace()` returns `LogsQueryPartialResult` (not an exception) when queries time out or hit data limits. If the code only checks for exceptions and not `response.status`, partial results are silently treated as complete results. The default server timeout is 3 minutes; the max is 10 minutes.

**Why it happens:** The Python SDK's `query_workspace` returns a union type (`LogsQueryResult | LogsQueryPartialResult`). The partial result contains both `partial_data` and `partial_error`. Most tutorial code shows `for table in response.tables` which works for `LogsQueryResult` but silently returns incomplete data for `LogsQueryPartialResult`. Additionally, the batch query API (`query_batch`) can return a mix of `LogsQueryResult`, `LogsQueryPartialResult`, and `LogsQueryError` objects in the same response.

**Consequences:** The investigation agent shows partial data without indicating incompleteness. A question like "how many captures failed this week?" returns a count based on a subset of data, giving a misleadingly optimistic answer. The user trusts the number because it came from an authoritative-looking system.

**Prevention:**
- Always check `response.status == LogsQueryStatus.SUCCESS` before using results
- For partial results, include the error context in the agent's response: "Note: results may be incomplete due to query timeout"
- Set `server_timeout=600` (max 10 minutes) for aggregate queries
- Limit time ranges in KQL queries (`ago(24h)` or `ago(7d)` defaults, not unbounded)
- Add `| take 500` or `| limit 1000` safeguards to prevent result set explosion
- Build a query execution wrapper that normalizes all three statuses into a consistent result type with an `is_partial` flag

**Detection:** Log the query status on every execution. Alert if partial results exceed 10% of queries.

**Confidence:** HIGH -- Verified from official Azure SDK documentation and troubleshooting guide.

**Phase guidance:** Build the query execution wrapper in the first phase. The wrapper must handle SUCCESS, PARTIAL, and FAILURE before any higher-level agent logic.

### Pitfall 4: Evaluating Classifier with the Same Model That Classifies (Self-Enhancement Bias)

**What goes wrong:** Using GPT-4o as an LLM-as-judge to evaluate GPT-4o's classification creates a self-enhancement bias. Research shows LLMs prefer their own outputs and give inflated scores. The eval framework reports high quality while actual classification degrades.

**Why it happens:** Self-enhancement bias is well-documented in LLM evaluation research. When the same model generates and judges, it shares the same biases, blind spots, and stylistic preferences. Studies confirm this leads to evaluation hallucination -- judges producing inconsistent outputs for semantically equivalent inputs. Position bias (preferring the first option), verbosity bias (longer = better), and self-preference all compound. In pairwise code judging, simply swapping presentation order of responses shifts accuracy by 10%+.

**Consequences:** The eval framework reports high scores while actual quality degrades. The self-monitoring loop never fires alerts because the judge agrees with the classifier. Will only discovers problems when misclassified captures accumulate in the inbox.

**Prevention:**
- For classifier accuracy evals: use deterministic metrics (exact match against golden dataset labels, confusion matrix, per-bucket precision/recall) -- no LLM judge needed
- For Admin Agent quality evals (free-form output): use a different model as judge, or use binary pass/fail rubrics that reduce subjectivity
- For any LLM-as-judge eval: randomize presentation order, use binary scoring, require explicit chain-of-thought reasoning in the judge's response before the score
- Complement LLM-as-judge with implicit signals: did Will reclassify the capture? Delete it? Swipe away an errand item immediately?
- Cross-validate judge scores against human labels on a subset; if correlation is low, the judge is unreliable

**Detection:** Cross-validate LLM-judge scores against human labels on a subset (10-20 items). If Pearson correlation < 0.7, the judge is unreliable.

**Confidence:** HIGH -- Multiple academic papers (arxiv 2511.04205), Weights & Biases research, Arize AI documentation all confirm self-enhancement bias.

**Phase guidance:** Address in the eval framework phase. Start with deterministic metrics for classification. Only add LLM-as-judge for subjective quality after deterministic metrics are proven.

### Pitfall 5: Azure AI Evaluation SDK Consolidation -- Building on a Moving Target

**What goes wrong:** The evaluation SDK is actively migrating from `azure-ai-evaluation` to `azure-ai-projects` v2 (at 2.0.0b4 as of early 2026). The two packages have different APIs, different evaluator patterns (the new `grade(sample, item)` function signature vs the old `__call__` pattern), and the v2 SDK is still in beta. Building on one and having to migrate to the other wastes significant effort.

**Why it happens:** Microsoft is consolidating agents, inference, and evaluation into a single `azure-ai-projects` package. The custom evaluator pattern changed fundamentally: the new SDK uses OpenAI's Eval API protocol internally, evaluators are registered in a project catalog, and code-based evaluators run in a sandboxed environment. Both old and new patterns coexist in documentation, causing confusion about which to use.

**Consequences:** Code built on the old `azure-ai-evaluation` `evaluate()` function needs rewriting when v2 goes GA. Code built on the v2 beta may break with API changes. Either way, eval pipeline code becomes throwaway if not properly abstracted.

**Prevention:**
- Check the state of `azure-ai-projects` v2 SDK at build time -- if stable, use it; if still beta, use the stable `azure-ai-evaluation` with abstraction
- Keep the eval pipeline thin: golden datasets in JSONL files, evaluator logic in standalone Python functions, orchestration as a CLI script
- Do not couple eval logic to SDK evaluator registration -- write evaluators as plain functions first, then wrap for whichever SDK is current
- For classifier accuracy, use code-based evaluators (exact match, confusion matrix) that do not depend on the eval SDK at all -- plain Python with pytest is sufficient
- Pin SDK versions in `pyproject.toml` and monitor release notes

**Detection:** If the eval pipeline imports change more than once, the abstraction layer is missing.

**Confidence:** MEDIUM -- The migration direction is confirmed (multiple sources), but timeline to GA is uncertain. The beta may stabilize before the project ships.

**Phase guidance:** Research the exact SDK state when the eval phase starts. Keep evaluator logic decoupled from SDK registration.

## Moderate Pitfalls

### Pitfall 6: MCP Tool Timeout for Long-Running KQL Queries

**What goes wrong:** Claude Code's MCP tool execution has a default timeout of 60 seconds. Complex KQL queries over a week of data can take 30-120 seconds via `LogsQueryClient`. The MCP tool call silently drops the result if it exceeds the timeout, and Claude Code reports a generic error.

**Why it happens:** The MCP TypeScript SDK has `DEFAULT_REQUEST_TIMEOUT_MSEC = 60000`. KQL query execution time depends on data volume, query complexity, and workspace load. Aggregate queries (`summarize`, `percentile`, time-binned analysis) over longer periods are especially slow. Additionally, SSE transport connections can be dropped by HTTP proxies after ~5 minutes idle.

**Prevention:**
- Use stdio transport for the MCP server (local process, no network timeout issues, recommended by Claude Code docs)
- Set `MCP_TIMEOUT=120000` (120 seconds) in Claude Code configuration
- Design KQL queries with `| take` limits and bounded time ranges (default to `ago(24h)`)
- For expensive queries (weekly summaries, trend analysis), pre-compute results in a daily batch job that writes to Cosmos, rather than querying raw logs in real-time
- Return meaningful error messages when queries approach timeout limits

**Detection:** Log MCP tool call durations. Monitor for timeout errors in Claude Code.

**Confidence:** MEDIUM -- Timeout issues documented in Claude Code GitHub issues (#3033, #20335, #22542). Exact behavior may vary with Claude Code versions.

**Phase guidance:** Address when building the MCP tool. Test with realistic data volumes.

### Pitfall 7: Building a Custom MCP Server When Azure MCP Server Already Exists

**What goes wrong:** Building a custom MCP server from scratch for App Insights KQL queries when the official Azure MCP Server (`@azure/mcp`) already provides `monitor_query_workspace_logs`, `monitor_list_tables`, `monitor_list_workspaces`, and metric query tools. This wastes weeks reimplementing solved problems.

**Why it happens:** The Azure MCP Server was released in 2025 and may not be well-known. It provides 11 Monitor tools and 5 Workbooks tools that cover most observability use cases. The project may also benefit from existing community MCP servers for Log Analytics (multiple repos on GitHub).

**Consequences:** Weeks spent building, testing, and maintaining a custom MCP server that reimplements what Azure already provides. Ongoing maintenance burden as the Azure SDK evolves.

**Prevention:**
- Evaluate the Azure MCP Server first: install it, test `monitor_query_workspace_logs` against the Second Brain workspace, verify it handles workspace-based schema correctly
- If Azure MCP Server works for the basic query case, use it directly and build custom MCP tools only for domain-specific operations (e.g., "trace capture X end-to-end", "show classifier accuracy for last week", "compare error rates before and after deploy")
- If it does not work (the App Insights table bug was fixed in PR #280 but test against the current version), consider the community `log-analytics-mcp-server` or `mcp-kql-server` before building from scratch
- The custom MCP tools should complement the Azure MCP Server, not replace it

**Detection:** If the MCP server implementation estimate exceeds 1 week, evaluate existing solutions first.

**Confidence:** HIGH -- Azure MCP Server is official, documented on Microsoft Learn, with 11 Monitor tools.

**Phase guidance:** First task in the MCP tool phase: spike the Azure MCP Server against the real workspace.

### Pitfall 8: Golden Dataset Rot -- Static Test Data vs Evolving System

**What goes wrong:** The golden dataset for classifier evaluation is built from captures at a point in time. As Will's usage patterns evolve (new destinations, new recipe sites, new project types, new phrasing), the golden dataset no longer represents real-world distribution. Eval scores stay green while real-world accuracy degrades on novel inputs.

**Why it happens:** Golden datasets are point-in-time snapshots. The Second Brain's capture patterns evolve with Will's life: new stores added via voice affinity rules, new recipe sites discovered, new projects started. A golden dataset from April 2026 will not cover captures from June 2026 mentioning new destinations or using new phrasing patterns. This is a single-user system, so the input distribution is entirely driven by one person's changing habits.

**Consequences:** False confidence in classifier quality. The eval pipeline reports 95% accuracy on stale data while real-world accuracy on novel inputs drops.

**Prevention:**
- Build the golden dataset from actual production captures (sample from Cosmos Inbox), not synthetic data
- Include a "dataset refresh" script that pulls recent captures, presents them for manual label review, and adds them to the golden set
- Track eval scores over time AND dataset freshness (days since last capture added); alert on both score drops and staleness
- Include explicit edge cases: multi-bucket captures, ambiguous captures, recipe URLs, voice transcription artifacts, novel destinations
- Target 50-100 captures in the initial golden dataset, refreshed monthly

**Detection:** If the most recent capture in the golden dataset is more than 30 days old, flag for refresh.

**Confidence:** HIGH -- Well-known ML evaluation anti-pattern, amplified by single-user system dynamics.

**Phase guidance:** Build the dataset refresh workflow alongside the initial golden dataset, not as an afterthought.

### Pitfall 9: Implicit Signals Without a Feedback Storage Layer

**What goes wrong:** The eval framework plans to use implicit signals (reclassifications, deletions, errand item swipe-to-remove) but there is no storage layer to record these as structured evaluation events. The current Cosmos schema tracks captures and errands but not user correction actions.

**Why it happens:** The existing API endpoints handle CRUD operations but do not log corrections as evaluation data. When Will reclassifies a capture via the inbox, the backend updates the inbox document's `classificationMeta` but does not record "user changed bucket from X to Y" as a separate evaluation signal. Similarly, when Will swipes away an errand item, the item is deleted but there is no record of "this item was rejected."

**Consequences:** Without structured feedback data, the eval framework cannot compute implicit accuracy metrics. The team has to parse App Insights logs to reconstruct user corrections, which is fragile, incomplete, and tied to the 30-day retention window.

**Prevention:**
- Add evaluation event tracking to existing API endpoints: when `recategorize` is called, emit a structured event with `from_bucket`, `to_bucket`, `original_confidence`; when an errand item is deleted within 1 minute of creation, flag as "likely rejected"
- Store events in either a new EvalEvents Cosmos container or as structured App Insights custom events (cheaper, leverages existing infrastructure)
- Design the event schema before building the eval framework -- it consumes this data
- Capture at minimum: reclassification events, deletion-within-N-minutes events, low-confidence manual selection events, and errand item rapid-removal events

**Detection:** If the eval pipeline has to parse unstructured App Insights logs to find correction signals, the feedback storage layer is missing.

**Confidence:** HIGH -- Verified by reading existing `models/documents.py` and API routes. No evaluation event model exists.

**Phase guidance:** Must be built early, before or as the first task of the eval framework phase.

### Pitfall 10: Mobile Dashboard Over-Engineering for a Single-User System

**What goes wrong:** Building an elaborate real-time dashboard with multiple chart types, date range selectors, and interactive drill-down when Will is the only user and checks it occasionally. Charting libraries (react-native-gifted-charts, Victory Native) add complexity, native dependencies, and maintenance burden for a feature used a few times a week.

**Why it happens:** Dashboards are visually impressive and fun to build. The natural instinct is to build a rich monitoring experience. But for a single-user hobby project, the ROI is low -- Will can ask the investigation agent a question in the chat interface instead of reading pre-built charts.

**Consequences:** Weeks spent on chart rendering, responsive layouts, data formatting, date picker components, and chart library compatibility with Expo. Meanwhile, the investigation agent chat interface provides the same answers with much less code.

**Prevention:**
- Start with the investigation agent chat interface as the primary observability surface
- Build the mobile dashboard as a "health summary" screen with 3-5 key metrics as text (not charts): capture count today, error count, last failure time, classifier confidence average, Admin Agent success rate
- Only add charts if the text summary proves insufficient after real-world use
- If charts are eventually needed, use react-native-gifted-charts (pure JS, Expo compatible, no native module dependencies, 75+ chart types)

**Detection:** If the dashboard phase estimate exceeds 2 weeks, scope is too large.

**Confidence:** HIGH -- Judgment call based on project context (single user, hobby project, learning focus).

**Phase guidance:** Build the chat interface first. Add the summary screen second. Charts only if needed later.

## Minor Pitfalls

### Pitfall 11: KQL Injection via Investigation Agent

**What goes wrong:** If the investigation agent constructs KQL by string-concatenating user input, accidental input could alter query semantics. While this is a single-user system, the principle matters for code quality.

**Prevention:** Use parameterized KQL templates where user values are inserted into `where` clauses with proper escaping. Since KQL does not have parameterized queries like SQL, sanitize inputs: validate that user-provided values match expected types (UUIDs for trace IDs, known strings for component names, time ranges as `ago()` expressions). Strip KQL operators (`|`, `where`, `extend`, `project`) from user-provided values.

**Confidence:** MEDIUM -- KQL injection is less severe than SQL injection because Log Analytics is read-only, but it could return unintended data or cause query errors.

**Phase guidance:** Address when building the KQL query construction layer.

### Pitfall 12: App Insights 30-Day Data Retention Boundary

**What goes wrong:** App Insights data is retained for 30 days. If the investigation agent or eval pipeline queries beyond this window, results are silently empty. Golden dataset evaluations referencing historical trace IDs return nothing.

**Prevention:**
- Investigation agent system prompt must include the 30-day retention limit and communicate it to users
- Eval pipeline stores evaluation results in Cosmos (persistent) rather than depending on App Insights for historical data
- Consider exporting critical telemetry summaries to Cosmos or Blob Storage for trend analysis beyond 30 days
- Daily/weekly aggregation jobs can compute and persist summary metrics that outlive the raw telemetry

**Confidence:** HIGH -- Already documented in `backend/queries/README.md`.

**Phase guidance:** Address in both the investigation agent and eval framework phases.

### Pitfall 13: Custom Evaluator Sandbox Limits in Azure AI Foundry

**What goes wrong:** Azure AI Foundry's code-based custom evaluators run in a sandboxed environment with: no network access, 2-minute execution limit per grade call, 2GB memory, limited packages (numpy, pandas, scikit-learn, rapidfuzz, pydantic, etc., but no custom packages). If the classifier accuracy evaluator needs to fetch ground truth from Cosmos or call Azure OpenAI, it cannot run in the sandbox.

**Prevention:**
- Classifier accuracy evaluators should be simple code-based comparisons (exact match, fuzzy match via rapidfuzz which is available in the sandbox) operating on pre-prepared JSONL data
- Prepare evaluation datasets as self-contained JSONL files with both predictions and ground truth labels before submitting to the eval API
- Use prompt-based evaluators (LLM-as-judge) only for subjective quality metrics where the sandbox's LLM call handles the external API dependency
- For complex evaluators needing external access (Cosmos queries, multiple API calls), run them locally as Python scripts via a CLI rather than in the Foundry sandbox

**Confidence:** HIGH -- Verified from official Microsoft Learn documentation on custom evaluators (published 2026-03-06).

**Phase guidance:** Address in the eval framework phase when designing evaluator architecture.

### Pitfall 14: Investigation Agent Chat Reusing Capture SSE Patterns Without Adaptation

**What goes wrong:** The existing SSE streaming in `streaming/adapter.py` is designed for the capture flow: it emits CLASSIFIED, LOW_CONFIDENCE, MISUNDERSTOOD, and COMPLETE events in a specific sequence. Reusing this adapter for the investigation agent chat produces confusing event types that do not make sense for a Q&A conversation (there is no "classification" happening, no "bucket" to report).

**Prevention:**
- Build a separate SSE streaming function for investigation agent responses, modeled as a simple text stream with progress indicators
- The investigation agent needs events like: QUERY_STARTED (with the KQL being executed), QUERY_RESULT (with the data), AGENT_RESPONSE (with the natural language summary), ERROR (with diagnostics)
- Do not reuse the capture-flow event vocabulary; the investigation agent is a different interaction pattern (Q&A vs capture-classify)
- The existing `react-native-sse` client library on mobile already handles arbitrary event types, so new event names are free

**Confidence:** HIGH -- Direct analysis of existing adapter code.

**Phase guidance:** Address when building the investigation agent's API endpoint.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Programmatic KQL query library | Schema mismatch (Pitfall 1) + Partial results (Pitfall 3) | Build and validate workspace-compatible templates with proper status handling first |
| Investigation agent NL-to-KQL | LLM hallucination (Pitfall 2) | Template-first with schema grounding; free-form KQL as guarded fallback |
| MCP tool for Claude Code | Timeout (Pitfall 6) + Build vs buy (Pitfall 7) | Evaluate Azure MCP Server first; use stdio transport; set MCP_TIMEOUT |
| Investigation agent API + streaming | SSE pattern mismatch (Pitfall 14) | New event vocabulary for Q&A flow, separate from capture-flow adapter |
| Mobile observability surface | Over-engineering (Pitfall 10) | Chat interface first, text health summary second, charts only if proven needed |
| Golden dataset creation | Dataset rot (Pitfall 8) | Build from production captures with monthly refresh workflow |
| Eval framework architecture | SDK churn (Pitfall 5) + Sandbox limits (Pitfall 13) | Decouple evaluator logic from SDK; prepare self-contained JSONL files |
| Classifier accuracy eval | Self-enhancement bias (Pitfall 4) | Deterministic metrics (exact match, confusion matrix), not LLM-as-judge |
| Implicit signal collection | Missing feedback storage (Pitfall 9) | Add evaluation event tracking to existing API endpoints before building eval pipeline |
| Data retention awareness | 30-day boundary (Pitfall 12) | Persist eval results to Cosmos; include retention limit in agent system prompt |

## Sources

- [Azure Monitor Query Python SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/monitor-query-readme?view=azure-python) -- LogsQueryClient, partial results, timeout handling, async client (HIGH confidence)
- [Azure MCP Server Monitor Tools](https://learn.microsoft.com/en-us/azure/developer/azure-mcp-server/tools/azure-monitor) -- 11 Monitor tools + 5 Workbooks tools for Log Analytics queries (HIGH confidence)
- [Azure MCP Server Issue #250](https://github.com/Azure/azure-mcp/issues/250) -- App Insights table query failures, fixed in PR #280 (HIGH confidence)
- [Custom Evaluators - Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/custom-evaluators) -- grade() function, sandbox constraints, supported packages (HIGH confidence)
- [NL2KQL: Natural Language to Kusto Query](https://arxiv.org/html/2404.02933v1) -- Schema hallucination dominates NL-to-KQL failures (HIGH confidence)
- [LLM-as-a-Judge Exploration](https://wandb.ai/site/articles/exploring-llm-as-a-judge/) -- Self-enhancement bias, position bias, verbosity bias (HIGH confidence)
- [LLM Judge Fairness Research](https://www.resultsense.com/insights/2025-10-01-llm-judge-fairness-research-business-implications) -- Evaluation hallucination patterns (MEDIUM confidence)
- [Azure AI Projects v2 Migration Guide](https://medium.com/@badrvkacimi/migrating-to-azure-ai-projects-v2-the-unified-foundry-sdk-you-need-to-know-0102d969df1f) -- SDK consolidation direction (MEDIUM confidence)
- [Claude Code MCP Timeout Issues](https://github.com/anthropics/claude-code/issues/3033) -- SSE timeout, tool execution limits (MEDIUM confidence)
- [MCP Best Practices](https://modelcontextprotocol.info/docs/best-practices/) -- Single-purpose servers, transport selection (MEDIUM confidence)
- [Building Golden Datasets for AI Evaluation](https://www.getmaxim.ai/articles/building-a-golden-dataset-for-ai-evaluation-a-step-by-step-guide/) -- Dataset curation, refresh cadence (MEDIUM confidence)
- [Azure Monitor Malicious KQL Query](https://securecloud.blog/2022/04/27/azure-monitor-malicious-kql-query/) -- KQL injection risks (LOW confidence, single source)
- [Avoiding Common Pitfalls in LLM Evaluation](https://www.honeyhive.ai/post/avoiding-common-pitfalls-in-llm-evaluation) -- Evaluation anti-patterns overview (MEDIUM confidence)
- [Claude Code MCP Documentation](https://code.claude.com/docs/en/mcp) -- Transport types, timeout configuration (HIGH confidence)
