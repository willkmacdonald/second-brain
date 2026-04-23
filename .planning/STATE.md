---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Observability & Evals
status: planning
stopped_at: Phase 20.1 context gathered
last_updated: "2026-04-23T03:27:18.415Z"
last_activity: 2026-04-23
progress:
  total_phases: 15
  completed_phases: 11
  total_plans: 36
  completed_plans: 35
  percent: 97
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-05)

**Core value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.
**Current focus:** Phase 20 — Feedback Collection

## Current Position

Phase: 21
Plan: Not started
Status: Ready to plan
Last activity: 2026-04-23

Progress: [█████████░] 94%

## Performance Metrics

**Velocity (v3.0):**

- Total plans completed: 45
- Average duration: 3.1 min
- Timeline: 2026-03-01 to 2026-03-23 (22 days)

**Velocity (v2.0):**

- Total plans completed: 16
- Average duration: 3.3 min
- Timeline: 2026-02-26 to 2026-03-01 (4 days)

**Velocity (v3.1):**

- Plans completed: 18 fully + 2 code-complete awaiting bundled human-verify checkpoint (19.2-04 + 19.2-05)
- Last plan duration: 6 min (20-01 -- feedback signal infrastructure; 2 tasks, 9 tests)
- Timeline: 2026-04-05 to present

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v3.0 decisions archived to .planning/milestones/v3.0-ROADMAP.md

**v3.1 decisions:**

- KQL programmatic queries use workspace schema (traces/requests), NOT portal schema (AppTraces/AppRequests)
- Investigation agent uses parameterized @tool functions, NOT free-form LLM-generated KQL
- Classifier evals use deterministic metrics (exact match, confusion matrix), NOT LLM-as-judge
- MCP server is standalone process with stdio transport, NOT inside Docker image
- Eval pipeline runs as CLI + GitHub Actions, NOT inside FastAPI request-response cycle
- Evaluate Azure MCP Server first before building custom MCP tool
- LogsQueryClient init non-fatal (warning + None) matching optional services pattern
- SYSTEM_HEALTH consolidated from 5 portal sections to 1 programmatic query
- [Phase 16]: Eval document models use standalone BaseModel (not BaseDocument) for non-bucket containers
- [Phase 16]: Cosmos container creation must use management plane (az CLI), not data plane RBAC (403 on DDL)
- [Phase 16]: Always regenerate uv.lock after pyproject.toml dependency changes before deploying
- [Phase 16.1]: uv version pinned to 0.5.4 in CI matching Dockerfile for lockfile format consistency
- [Phase 16.1]: Revision suffix uses sha- prefix (not bare SHA) so Azure naming rules always satisfied
- [Phase 16.1]: Health check polls 12s x 15 attempts (3min) balancing fast detection with cold start time
- [Phase 16.1]: Image SHA mismatch hard-fails; traffic weight non-100% is warning only (Azure transient behavior)
- [Phase 16.1]: Deploy summary uses if: always() so failed deploys still produce visible diagnostics
- [Phase 17]: SYSTEM_HEALTH_ENHANCED uses summarize (not toscalar+print) to support percentile() function
- [Phase 17]: server_timeout=30 on investigation queries to leave headroom under agent's 60s timeout
- [Phase 17]: Original SYSTEM_HEALTH and RECENT_FAILURES preserved as fallback alongside enhanced versions
- [Phase 17]: Investigation Agent tool_choice defaults to auto (not required) so agent can respond without calling tools
- [Phase 17]: Investigation text output is PRIMARY deliverable (SSE "text" events), not suppressed as reasoning
- [Phase 17]: SoftRateLimiter warns at 10 queries/min but never blocks requests
- [Phase 17.3]: Sentry disabled in __DEV__ to avoid noise from React strict mode double-rendering
- [Phase 17.3]: tracesSampleRate 1.0 appropriate for single-user app (no cost concern)
- [Phase 17.3]: initSentry() at module scope before rendering, not in useEffect (catches early crashes)
- [Phase 17.3]: Placeholder values for Sentry org/project/DSN -- user replaces before first EAS build
- [Phase 18]: Used useMarkdown hook from react-native-marked instead of Markdown component to avoid nested FlatList conflict
- [Phase 18]: Dashboard metrics parsed from investigation agent prose via regex (no separate backend endpoint)
- [Phase 18]: isRecordingRef guard prevents cross-screen speech event leaks (ref not state to avoid stale closures)
- [Phase 18]: Sentry.captureMessage additive alongside console.error (no-op in dev, active in production EAS builds)
- [Phase 18]: Dashboard prompt forces both system_health AND recent_errors tool calls for data provenance consistency with deep-link
- [Phase 17.4]: ErrorFallback uses error: unknown with instanceof narrowing (Sentry FallbackRender contract)
- [Phase 17.4]: Recipe tests use autouse DNS mock fixture to prevent live resolution
- [Phase 17.4]: MOBL-04/MOBL-05 eval items deferred to Phase 21 (not implemented in Phase 18)
- [Phase 17.4]: Client factory pattern for warmup self-heal (avoids private SDK attr access)
- [Phase 17.4]: Foundry health cache on app.state (not module global) for test isolation
- [Phase 17.4]: Investigation timeout reduced to 30s (from 60s) with user-friendly error message
- [Phase 17.4]: Review prompt scoped to PR diff only (not repo-wide) to reduce noise
- [Phase 19]: MCP server is single-file (server.py ~300 lines) wrapping existing query functions
- [Phase 19]: RESULT_LIMIT=20 for MCP (higher than Investigation Agent's 10) -- Claude Code has more screen space
- [Phase 19]: trace_lifecycle truncation keeps LAST N records to preserve terminal outcome
- [Phase 19]: Claude Code CLI writes MCP config to .mcp.json (not .claude/settings.json)
- [Phase 19]: prerelease=allow in mcp/pyproject.toml [tool.uv] for agent-framework-azure-ai RC
- [Phase 19]: Investigate skill uses conversation context + stable IDs for follow-ups (replaces server-side thread management)
- [Phase 19]: Deprecation notes use generic wording to satisfy zero-reference verification on old script paths
- [Phase 19.2-01]: Investigation spike memo gates Plan 02 scope -- memo §5 numbered recommendations become Plan 02 task list verbatim; no pre-plan speculation
- [Phase 19.2-01]: Single root cause for 4 broken_emitter segments -- agent_emitter.py:63 passes raw _WorkloadEvent to record_event (expects IngestEvent RootModel); one-line wrap fix repairs classifier+admin+investigation simultaneously; same shape bug latent at telemetry.py:105,120 and recipe.py:185
- [Phase 19.2-01]: Mobile push-path: YES for mobile_capture, NO for mobile_ui -- Plan 02 ships Option B (post-capture fire-and-forget) not Option A (pre-capture with offline queue); upgrade to Option A is additive if transport-failure blind spot becomes costly
- [Phase 19.2-01]: Option B emit centralised inside attachCallbacks with single-fire guard, covering all 7 + 3 legacy terminal paths -- per-sendX wrappers would miss HITL paths because hitlTriggered suppresses COMPLETE->onComplete dispatch
- [Phase 19.2-01]: Outcome mapping -- success (CLASSIFIED / COMPLETE-non-HITL), degraded (MISUNDERSTOOD / LOW_CONFIDENCE / UNRESOLVED / legacy CUSTOM HITL), failure (ERROR / RUN_ERROR / SSE transport error)
- [Phase 19.2-01]: backend_api native-correlation gap (AppRequests untagged by capture_trace_id) DEFERRED from Plan 02 -- follow-up bundled with project_followup_audit_first_findings.md
- [Phase 19.2-01]: Duplicate Key Vault secret cleanup (sb-api-key vs second-brain-api-key) OUT-OF-SCOPE for Plan 02 -- pre-existing hygiene, tracked separately
- [Phase 19.2-02]: Applied SPIKE-MEMO §5 six numbered fixes verbatim (5.1-5.6) in memo-prescribed order; no speculative additions, no prescribed skips
- [Phase 19.2-02]: §5.3 recipe migration threads capture_trace_id via the existing capture_trace_id_var ContextVar already set by the classifier adapter -- no new plumbing
- [Phase 19.2-02]: §5.4 regression coverage uses (a) focused spine_stream_wrapper tests against _RootAccessingSpineRepo + (b) static source scan that fails CI if any future edit reintroduces record_event(_WorkloadEvent(...)) without the IngestEvent wrap
- [Phase 19.2-02]: §5.5 mobile emit centralised in attachCallbacks (not per-sendX wrappers) with closure-scoped single-fire guard covering all 7 + 3 legacy terminal paths; per-sendX wrappers would miss every HITL path because hitlTriggered=true suppresses COMPLETE
- [Phase 19.2-02]: §5.6 classifier-side emit verification implemented at spine_stream_wrapper level rather than full capture-handler integration -- wrapper is the only emit boundary the real handler delegates to, so wrapper-level RootAccessingSpineRepo test satisfies the integration guarantee without wiring Foundry/Cosmos mocks
- [Phase 19.2-02]: Mobile Jest unit tests for Option B terminal paths DEFERRED -- mobile package has no test framework installed; coverage provided via end-to-end trace inspection after EAS build deploys (SPIKE-INTEGRATED-RELEASE-VERIFY.md Step 7)
- [Phase 19.2-02]: Plan 02 will NOT merge alone -- integrated-release banner and must-have truths both enforce Plans 02-05 deploying together
- [Phase 19.2-03]: Operator-facing ledger policy codified in backend/src/second_brain/spine/ledger_policy.py (LEDGER_EXPECTED_CHAINS + SEGMENT_LEDGER_METADATA) — separate from raw audit registry; SPIKE-MEMO §4 decisions encoded in code, not read at runtime
- [Phase 19.2-03]: LEDGER_EXPECTED_CHAINS starts from EXPECTED_CHAINS unchanged — memo's YES/NO mobile decision already aligned with required flags; override layer ready for future memo revisions without schema change
- [Phase 19.2-03]: Transaction-ledger rows are correlated-only -- get_recent_transaction_events filters IS_DEFINED(correlation_kind/correlation_id) server-side so probe/health noise stays in native diagnostics
- [Phase 19.2-03]: RESEARCH Option A enrichment -- spine_correlation (which segments) JOIN spine_events (duration/operation) by (segment_id, timestamp) in the read path; avoids forward-only schema change on spine_correlation upsert
- [Phase 19.2-03]: Purposeful empty-state metadata on SegmentLedgerResponse -- mode (transactional|native_only) + empty_state_reason string rendered verbatim by UI; defaults to transactional/None for unlisted segments
- [Phase 19.2-03]: Query(...) chosen over Field(...) for FastAPI route-parameter bounds -- Field silently skips ge/le on route params; regression-tested with 422 on out-of-bounds window_seconds
- [Phase 19.2-03]: api.py added as single Write (not stepwise Edits) for imports + route handlers -- ruff auto-format hook strips unused imports between edits (MEMORY.md Phase 17.1 lesson)
- [Phase 19.2-04]: Web TS types for ledger response (TransactionLedgerRow / SegmentLedgerResponse / TransactionEvent / TransactionPathResponse) mirror Plan 03 Pydantic models verbatim; Pydantic Optional[T]=None -> TS T | null (not undefined) to match JSON-null wire format
- [Phase 19.2-04]: spine.segmentLedger + spine.transactionPath added to web/lib/spine.ts with encodeURIComponent on both id args -- preserves project_followup_phase1_web_hardening.md follow-up (same bug was latent in segmentDetail pre-Phase-1 hardening)
- [Phase 19.2-04]: Ledger fetch wrapped in try/catch console.warn -- non-fatal graceful degradation during integrated-release rollout window where Plan 04 web build may deploy before Plan 03 backend build (or vice versa). Falls through to native telemetry renderer, which is pre-19.2 behavior. "Best, most robust solution" over "simplest."
- [Phase 19.2-04]: Two empty-state branches encapsulated inside <LedgerSection /> component (not the segment page) -- page just passes raw ledger.mode + ledger.empty_state_reason through. Adding a third empty-state type later becomes a single-file change.
- [Phase 19.2-04]: page.tsx done as single Write (import merge + component import + first usage in one file write) to prevent auto-format stripping unused SegmentLedgerResponse + LedgerSection symbols mid-task (MEMORY.md Phase 17.1 lesson)
- [Phase 19.2-04]: Native renderer dispatch unchanged -- new "Diagnostics (native telemetry)" h2 label added above it but the schema->AppInsights/Foundry/Cosmos/Mobile dispatch stays verbatim. Regression guard: existing segment pages still render the same native renderer as before.
- [Phase 19.2-05]: Transaction page rewrite replaces spine.correlation with spine.transactionPath and adds three conditional gap callouts (missing_required red, unexpected yellow, present_optional muted) — fulfills CONTEXT.md drill-down step 3 ('show me the full path across segments' with explicit 'backend_api seen, classifier missing' reporting); whole-file single Write used to prevent ruff auto-format stripping unused TransactionPathResponse import mid-task
- [Phase 19.2-05]: Plan 04 + Plan 05 human-verify checkpoints BUNDLED into single consolidated approval per operator instruction + SPIKE-INTEGRATED-RELEASE-VERIFY.md rule (don't ship alone, verify after Plans 02-05 deployed together) — Plan 05 does not pause on its own checkpoint; single approval unblocks phase 19.2 closeout
- [Phase 19.3]: Foundry First design rule confirmed -- portal shows full prompt/output/tool transcripts for all 3 agents; decision records store deep-link refs only
- [Phase 19.3]: No built-in classification-accuracy evaluator in azure-ai-evaluation -- Phase 21 needs custom scorers hosted via Foundry evaluate()
- [Phase 19.3]: AgentReleaseManifest confirmed necessary -- Foundry has no native prompt-agent instruction versioning
- [Phase 19.3]: Cosmos trace_headers() mechanism proven -- Phase 19.4 extends existing helper, no bespoke instrumentation
- [Phase 19.3]: In-process Change Feed listener viable for Phase 20 -- no separate Azure Functions deployment needed
- [Phase 19.3]: Log-based scheduled query alerts sufficient for Phase 22 -- no custom OTel metrics infrastructure
- [Phase 19.3]: OTel baggage propagation through Foundry SDK unverified -- #1 spike question for Phase 19.4
- [Phase 19.4-01]: SpanProcessor on_start fires before capture handler sets ContextVar -- Site 1 (AppRequests) needs explicit get_current_span().set_attribute() fix
- [Phase 19.4-01]: activityId_g holds Cosmos server-side activity ID, NOT x-ms-client-request-id -- MEMORY.md documentation incorrect
- [Phase 19.4-01]: Cosmos correlation via AppDependencies (SpanProcessor-tagged) more reliable than AzureDiagnostics (activityId_g) -- no mapping table needed
- [Phase 19.4-01]: Plans 02+04 merge into single plan -- SpanProcessor covers Sites 2+4 without per-site code; 6 tasks from memo section 5
- [Phase 19.4-01]: trace_headers() still valuable for AzureDiagnostics defense-in-depth but PRIMARY correlation path is AppDependencies
- [Phase 19.4-02]: get_current_span().set_attribute() used to retroactively tag AppRequests span (SpanProcessor on_start fires before handler sets ContextVar)
- [Phase 19.4-02]: Cosmos correlation KQL switched from AzureDiagnostics activityId_g to AppDependencies Properties.capture.trace_id (more reliable, no mapping table)
- [Phase 19.4]: Cosmos correlation verified via AppDependencies (SpanProcessor-tagged) not AzureDiagnostics activityId_g -- consistent with spike memo section 6 decision
- [Phase 19.4]: Plan 03 Task 1 (add trace_headers to remaining sites) skipped -- already completed in Plan 02 commit 89af305
- [Phase 19.4]: Checkpoint D approved: live capture confirmed all 4 sites carry capture.trace_id, end-to-end spine-to-native drill-down verified
- [Phase 19.4.1]: ES module live binding (export let) for API_KEY so all import sites see runtime updates without code changes
- [Phase 19.4.1]: React Context + SecureStore pattern: provider reads on mount, syncs to config.ts via setRuntimeApiKey
- [Phase 19.4.1]: ApiKeyGate as Modal overlay (not navigation guard) so all 4 tabs remain visible
- [Phase 19.4.1]: KQL uses union of AppTraces+AppExceptions with SeverityLevel>=3 for last error time; last_error_time as ISO string, client computes age
- [Phase 19.4.1]: Tasks tab useFocusEffect triggers GET /api/errands (Admin Agent processing side-effect) -- moved from Status per D-04
- [Phase 19.4.1]: Status screen uses ScrollView instead of SectionList -- no expandable sections, just dashboard cards and spine tiles
- [Phase 19.4.1]: formatErrorAge computed client-side from backend lastErrorTime ISO string -- avoids timezone issues
- [Phase 20-01]: Fire-and-forget pattern for inline feedback signal writes per D-02 -- try/except wraps every FeedbackDocument write so failures never block primary actions
- [Phase 20-01]: POST /api/feedback writes directly (not fire-and-forget) since it IS the primary action
- [Phase 20-01]: signalType whitelist validation rejects anything outside thumbs_up/thumbs_down on explicit endpoint
- [Phase 20-02]: Two-step promote flow (preview then confirm) per D-06 -- agent shows preview first, only writes GoldenDatasetDocument after user confirmation
- [Phase 20-02]: CosmosManager passed as optional param (None default) to InvestigationTools so telemetry-only tools work without Cosmos
- [Phase 20-03]: captureTraceId added to InboxItemData interface to match backend response and enable feedback correlation

### Pending Todos

None.

### Roadmap Evolution

- Phase 16.1 inserted after Phase 16: Improve deployment process (URGENT)
- Phase 16.1 complete: pre-build uv lockfile validation + commit-correlated revision naming (Plan 01) + post-deploy health verification, image SHA check, revision cleanup, deploy summary (Plan 02)
- Phase 17.3 inserted after Phase 17: Address critical observability gaps (URGENT) -- COMPLETE (Sentry crash reporting verified on device)
- Phase 17.4 inserted after Phase 17.3: Foundry Observability and Codex Code Review (URGENT) -- Zero visibility into Foundry agent internals; investigation agent hangs are a black box; discovered during 18-04 gap closure (2026-04-13)
- Phase 19.1 inserted after Phase 19: address observability gap (URGENT)
- Phase 19.2 inserted after Phase 19.1: transaction-first spine (URGENT) -- ledger-first drill-down model; 5 plans, spike-gated; Plan 01 complete 2026-04-18

### Blockers/Concerns

- [Resolved]: Log Analytics Reader RBAC assigned to Container App managed identity (Phase 16-03)
- [Open]: azure-ai-evaluation SDK migration status (toward azure-ai-projects v2) -- check when Phase 21 starts

## Accumulated Context

### Roadmap Evolution

- Phase 19.4.1 inserted after Phase 19.4: fix mobile UX issues (URGENT)
- Phase 20.1 inserted after Phase 20: Design team UI improvements (URGENT)

## Session Continuity

Last session: --stopped-at
Stopped at: Phase 20.1 context gathered
Resume action: Continue with Phase 20 Plan 02 (signal promotion pipeline)
