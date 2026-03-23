---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Admin Agent & Shopping Lists
status: unknown
last_updated: "2026-03-23T16:03:20.723Z"
progress:
  total_phases: 19
  completed_phases: 19
  total_plans: 61
  completed_plans: 61
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-01)

**Core value:** One-tap capture from a phone instantly routes through an agent that classifies, files, and clarifies -- with zero organizational effort.
**Current focus:** Phase 15 -- V3.0 Tech Debt Cleanup (gap closure)

## Current Position

Phase: 15 of 15 (V3.0 Tech Debt Cleanup)
Plan: 1 of 1
Status: Phase 15 complete -- all tech debt fixes applied
Last activity: 2026-03-23 -- Completed 15-01 (V3.0 Tech Debt Cleanup)

Progress: [██████████] 100% (Phase 15)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 28
- Average duration: 3.2 min
- Total execution time: 1.5 hours

**Velocity (v2.0):**
- Total plans completed: 16
- Average duration: 3.3 min
- Timeline: 2026-02-26 to 2026-03-01 (4 days)

**Velocity (v3.0):**
- Total plans completed: 15
- Average duration: 2.9 min

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 10 | 01 | 2 min | 3 | 4 |
| 10 | 02 | 2 min | 3 | 4 |
| 11 | 01 | 3 min | 2 | 4 |
| 11 | 02 | 5 min | 3 | 3 |
| 11.1 | 01 | 3 min | 2 | 5 |
| 11.1 | 02 | 4 min | 2 | 2 |
| 11.1 | 03 | 2 min | 2 | 2 |
| 11.1 | 04 | 3 min | 2 | 0 |
| 12 | 01 | 2 min | 2 | 3 |
| 12 | 02 | 2 min | 2 | 4 |
| 12.1 | 01 | 5 min | 3 | 9 |
| 12.1 | 02 | 2 min | 2 | 2 |
| 12.2 | 01 | 2 min | 2 | 6 |
| 12.2 | 03 | 2 min | 2 | 4 |
| Phase 12.2 P02 | 3 min | 2 tasks | 4 files |
| Phase 12.3 P01 | 3 min | 2 tasks | 3 files |
| Phase 12.3 P02 | 5 min | 2 tasks | 3 files |
| Phase 12.3 P03 | 6 min | 2 tasks | 4 files |
| Phase 12.3 P04 | 1 min | 2 tasks | 2 files |
| Phase 12.3 P05 | 3 min | 2 tasks | 3 files |
| Phase 12.3.1 P01 | 3 min | 2 tasks | 8 files |
| Phase 12.3.1 P02 | 3 min | 2 tasks | 10 files |
| Phase 12.3.1 P03 | 3 min | 2 tasks | 5 files |
| Phase 12.5 P01 | 2 min | 2 tasks | 5 files |
| Phase 12.5 P02 | 4 min | 2 tasks | 2 files |
| Phase 12.5 P03 | 2 min | 2 tasks | 3 files |
| Phase 13 P01 | 6 min | 2 tasks | 7 files |
| Phase 13 P02 | 2 min | 2 tasks | 4 files |
| Phase 13 P03 | 2 min | 2 tasks | 1 files |
| Phase 14 P01 | 12 min | 2 tasks | 8 files |
| Phase 14 P02 | 6 min | 2 tasks | 6 files |
| Phase 14 P03 | 2 min | 2 tasks | 5 files |
| Phase 15 P01 | 3 min | 2 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
v2.0 decisions archived to .planning/milestones/v2.0-ROADMAP.md

**v3.0 decisions:**
- [10-01] ShoppingListItem does not inherit BaseDocument -- no userId, timestamps, or classificationMeta needed
- [10-01] Tool parameter is list[dict] not list[ShoppingListItem] to avoid agent schema generation issues
- [10-01] Unknown stores silently fall back to "other" without error
- [10-02] Admin Agent registration is non-fatal -- app continues if Foundry registration fails
- [10-02] Separate AzureAIAgentClient instance for Admin Agent (own agent_id, own middleware)
- [11-01] autouse fixture pattern for Cosmos read_item mock -- returns mutable dicts to match real Cosmos behavior
- [11-02] getattr with safe defaults for admin refs -- graceful degradation when Admin Agent registration fails
- [11-02] Admin Agent only on initial captures, not follow-ups -- follow-ups are reclassification, not new captures
- [11-02] Admin Agent instructions already correct in Foundry portal -- no manual update needed
- [11.1-01] Extend classified_event with optional params (not new event type) -- backward-compatible
- [11.1-01] Conditional dict: buckets/itemIds absent (not null) for single-item events
- [11.1-01] process_admin_captures_batch delegates to existing process_admin_capture -- code reuse
- [11.1-01] Safety net triggers on empty file_capture_results list, not detected_tool check
- [11.1-02] Check buckets.length > 1 (not just existence) for multi-split vs single toast branching
- [11.1-02] Multi-split toast omits confidence -- multiple confidences would be confusing
- [11.1-02] Classifier multi-intent instructions favor keeping as single item when split is ambiguous
- [11.1-03] Store all function_calls in pending_calls dict -- future-proof for new tools
- [11.1-03] Pop from pending_calls on function_result -- prevents stale entries
- [11.1-03] stream_follow_up_capture intentionally unchanged -- single-tool pattern correct for reclassification
- [11.1-04] Instruction rewrite: "After determining the primary bucket" replaces "Before classifying" to prevent over-analysis
- [11.1-04] Explicit conjunction markers (and also, plus, oh and) as sole trigger for multi-intent splitting
- [11.1-04] Rule 6 added: conversational phrasing treated identically to imperative phrasing
- [12-01] Store display name mapping as constant dict with title-case fallback for unknown stores
- [12-01] Per-partition query loop over KNOWN_STORES (not cross-partition fan-out) for Cosmos best practice
- [12-02] StatusSectionRenderer renders header only -- SectionList handles item rendering via renderItem prop
- [12-02] Optimistic delete uses refetch instead of snapshot rollback to avoid stale closure issues with rapid deletes
- [12-02] Lightning bolt icon for Status tab to convey action/working
- [12.1-01] Processing triggers as side effect of GET /api/shopping-lists (not a separate endpoint)
- [12.1-01] Delete-on-success replaces processed upsert -- shopping list items are the durable output
- [12.1-01] CosmosResourceNotFoundError on delete is non-fatal (user may have swipe-deleted)
- [12.1-01] 3-second polling interval for auto-refresh while processing is active
- [12.1-01] processingCount field added to ShoppingListResponse for mobile banner control
- [12.1-02] Include ALL pending items in retry (not just stale ones) -- idempotent agent safer than permanently stuck items
- [12.1-02] admin_handoff.py NOT modified -- delete failure handler keeps log-only behavior per user decision
- [12.2-01] Field rename store->destination mirrors the broader errands concept (destinations can be physical or online)
- [12.2-03] Migration script uses upsert_item for idempotency -- safe to re-run if interrupted
- [12.2-03] Verification count check blocks old container deletion on mismatch -- prevents data loss
- [Phase 12.2]: DELETE endpoint path simplified from /api/errands/items/{id} to /api/errands/{id} per CONTEXT.md
- [Phase 12.3]: Azure CLI management plane for Cosmos container creation (data plane gets 403 with AAD)
- [Phase 12.3]: Destination slug used as document id for idempotent upserts in seed script
- [Phase 12.3]: KNOWN_DESTINATIONS kept for backward compatibility until Plan 03 replaces with dynamic routing
- [Phase 12.3]: Admin tools accept any destination slug dynamically, default fallback is 'unrouted' not 'other'
- [Phase 12.3]: needsRouting=True set automatically when destination is 'unrouted'
- [Phase 12.3]: Affinity rule conflict detection is case-insensitive on itemPattern
- [Phase 12.3]: manage_destination remove checks for existing errand items before deletion
- [Phase 12.3]: Response delivery heuristic uses keyword indicators (?, conflict, rule, created, deleted, destination) to classify agent responses
- [Phase 12.3]: Routing context injection wrapped in try/except with graceful fallback to raw text
- [Phase 12.3]: DELETE /api/errands/{id} accepts any destination string (no hardcoded validation)
- [Phase 12.3]: Notification dismiss deletes inbox item (response has been delivered)
- [Phase 12.3]: Migration script retains local KNOWN_DESTINATIONS (self-contained, not imported from documents.py)
- [Phase 12.3]: Horizontal scrollable chips for destination picker (not dropdown) -- better UX for quick tapping
- [Phase 12.3]: Admin notifications render above processing banner -- notifications are higher priority
- [Phase 12.3]: Route request always sets saveRule: true -- system auto-learns user preferences by default
- [Phase 12.3.1]: PUBLIC_PATHS reduced to /health only -- /docs and /openapi.json now conditional on environment
- [Phase 12.3.1]: Upload validation uses dual check: file.size header first, then len(bytes) as fallback
- [Phase 12.3.1]: VALID_BUCKETS uses frozenset for immutability (prevents accidental mutation of shared constant)
- [Phase 12.3.1]: Routing context format uses admin.py tool version as canonical (Agent trained on DESTINATIONS: / ROUTING RULES: headers)
- [Phase 12.5]: expo-speech-recognition ^3.1.1 wraps Apple SpeechAnalyzer for Expo compatibility
- [Phase 12.5]: speech.ts is stateless functions only -- component uses useSpeechRecognitionEvent hooks directly
- [Phase 12.5]: X-Capture-Source header is observability-only, does not affect classification
- [Phase 12.5]: wasRecordingRef coordinates stop action with async end event for submission control
- [Phase 12.5]: isFollowUpRecordingRef distinguishes primary capture vs follow-up in shared end event handler
- [Phase 12.5]: On-device path skips Uploading stage -- goes straight to Classifying
- [Phase 12.5]: Empty transcription still submitted to classifier (may trigger HITL per CONTEXT.md)
- [Phase 12.5]: EAS development build required for expo-speech-recognition native module (Expo Go insufficient)
- [Phase 12.5]: Stale closure bug fixed with ref-based transcript tracking for async submission
- [Phase 12.5]: Cloud fallback not tested (requires older iOS device) -- accepted as-is per CONTEXT.md
- [Phase 13]: Playwright browser launched once in lifespan, new context per fetch (cheap isolation)
- [Phase 13]: JSON-LD Recipe data extracted as supplementary context alongside truncated visible text
- [Phase 13]: Visible text truncated to 12000 chars (~3000 tokens) for LLM context limits
- [Phase 13]: Playwright startup nested inside admin try block -- recipe tools only useful with admin agent
- [Phase 13]: Resource blocking targets image/media/font/stylesheet only (XHR/fetch preserved for SPAs)
- [Phase 13]: Recipe delivery indicators use specific phrases (items added, no recipe found, error fetching) -- bare "from" too broad
- [Phase 13]: Source attribution subtitle uses Pressable+Linking.openURL for browser navigation on tap
- [Phase 13]: Source fields are optional (None default) -- regular errand items unaffected
- [Phase 13]: Admin Agent retry mechanism: auto-retry with nudge prompt when agent calls only intermediate tools (fetch_recipe_url) without output tools (add_errand_items)
- [Phase 13]: Output tool counting (_count_output_tool_invocations) prevents silent data loss -- inbox item only deleted after output tool invocation
- [Phase 13]: Non-recipe URLs handled by classifier confidence gating -- no Admin-side error path needed
- [Phase 13]: fetch_recipe_url removed from Classifier agent tools (only Admin Agent needs it)
- [Phase 14]: ContextVar (capture_trace_id_var) reuses follow_up_context pattern for trace ID propagation
- [Phase 14]: captureTraceId stored directly on inbox document body (not in classificationMeta)
- [Phase 14]: Log level policy: ERROR=unrecoverable, WARNING=degraded, INFO=lifecycle, DEBUG=routine
- [Phase 14]: configure_azure_monitor scoped with logger_name="second_brain" to filter SDK noise
- [Phase 14]: Telemetry JSON body uses snake_case to match Python convention (mobile transforms camelCase)
- [Phase 14]: reportError is fire-and-forget -- errors during reporting silently swallowed
- [Phase 14]: All 4 capture functions return traceId for UI access; follow-ups accept optional traceId for continuity
- [Phase 14]: Backend telemetry endpoint uses WARNING level for guaranteed App Insights visibility
- [Phase 14]: KQL queries use AppTraces table name (portal) while alert rules use 'traces' table (workspace-based scheduled queries)
- [Phase 14]: API-Health-Check alert severity 1 (5xx = service-level), error spike and capture failures severity 2 (warning)
- [Phase 14]: Push notifications via Azure mobile app (azureapppush) for mobile-first workflow
- [Phase 15]: Fixed test_fetch_failure assertion to match actual code output (no extractable content, not Error fetching)
- [Phase 15]: patch.object on instance methods for network isolation in multi-tier fetch tests

### Research Findings (Critical for v3.0)

- Admin Agent processes silently in background -- no SSE streaming of Admin work to user
- Individual item documents in Cosmos (not embedded arrays) for atomicity
- youtube-transcript-api blocked on Azure IPs -- use YouTube Data API v3 for production
- Agent-driven store routing via Foundry portal instructions, not code
- Separate AzureAIAgentClient instance for Admin Agent (no thread/tool cross-contamination)

### Pending Todos

None.

### Roadmap Evolution

- Phase 11.1 inserted after Phase 11: Classifier Multi-Bucket Splitting (URGENT)
- Phase 12.1 inserted after Phase 12: Admin agent deletes processed inbox items (URGENT)
- Phase 12.2 inserted after Phase 12.1: Rename Admin infrastructure from shopping lists to generic errands system (URGENT)
- Phase 12.3 inserted after Phase 12: Destination affinity and knowledge system for errand routing (URGENT)
- Phase 14 added: App Insights Operational Audit
- Phase 12.3.1 inserted after Phase 12.3: Implement fixes for security issues and from output of dead code analysis (URGENT)
- Phase 12.5 added: On-Device Voice Transcription (replace cloud Whisper with iOS SpeechAnalyzer)

### Blockers/Concerns

- [Open]: YouTube Data API v3 setup needs research before Phase 13 starts
- [Resolved]: Admin Agent instruction quality for store routing -- validated: "need milk" correctly routed to jewel store

## Session Continuity

Last session: 2026-03-23
Stopped at: Completed 15-01-PLAN.md -- V3.0 tech debt cleanup
Resume action: Phase 15 complete. All v3.0 tech debt resolved.
