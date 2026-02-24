# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-21)

**Core value:** One-tap capture from a phone instantly routes through an agent chain that classifies, files, and sharpens thoughts into concrete next actions -- with zero organizational effort.
**Current focus:** Phase 04.3 in progress -- agent-user UX with unclear item

## Current Position

Phase: 04.3 of 9 (Agent-User UX with unclear item) -- IN PROGRESS
Plan: 3 of 4 in current phase
Status: Plan 03 complete (follow-up conversation flow); 1 plan remaining
Last activity: 2026-02-24 -- Phase 04.3 Plan 03 executed (follow-up endpoint + capture screen conversation)

Progress: [########..] 77%

## Performance Metrics

**Velocity:**
- Total plans completed: 19
- Average duration: 3.9 min
- Total execution time: 1.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-backend-foundation | 3/3 | 12 min | 4 min |
| 02-expo-app-shell | 2/2 | 5 min | 2.5 min |
| 03-text-classification-pipeline | 2/2 | 7 min | 3.5 min |
| 04-hitl-clarification-and-ag-ui-streaming | 6/6 | 34 min | 5.7 min |
| 04.1-backend-deployment-to-azure-container-apps | 2/2 | 5 min | 2.5 min |
| 04.2-swipe-to-delete-inbox-items | 1/1 | 5 min | 5 min |
| 04.3-agent-user-ux-with-unclear-item | 3/4 | 10 min | 3.3 min |

**Recent Trend:**
- Last 5 plans: 04.2-01 (5 min), 04.3-01 (4 min), 04.3-02 (2 min), 04.3-03 (4 min)
- Trend: Full-stack plans (backend + mobile) consistently 4-5 min

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 9-phase comprehensive build order derived from 43 requirements; text capture loop (Phases 1-4) proven before expanding
- [Roadmap]: Phases 5, 6, 7, 9 depend only on Phase 3 (parallelizable but recommended serial for solo dev)
- [Roadmap]: Phase 8 (Digests) depends on both Phase 6 (Action) and Phase 7 (People) to have meaningful content
- [01-01]: AzureOpenAIChatClient uses sync DefaultAzureCredential (not async) since the client expects TokenCredential
- [01-01]: Agent and AG-UI endpoint registered at module level (not in lifespan) following research Pattern 1
- [01-01]: Key Vault fetch in lifespan with graceful fallback if unavailable
- [01-01]: Ruff per-file ignore for main.py (E402, I001) to support load_dotenv-before-imports pattern
- [01-02]: Agent creation moved to lifespan (from module level) to pass runtime CosmosManager to CRUD tools
- [01-02]: Class-based CosmosCrudTools pattern to bind container references without module-level globals
- [01-02]: Ruff N815 per-file ignore for camelCase Cosmos DB document field names
- [01-02]: Graceful Cosmos DB fallback in lifespan -- server starts without Cosmos configured
- [01-03]: API key middleware added in lifespan (not module level) because app.state.api_key set during lifespan Key Vault fetch
- [01-03]: Public paths as frozenset for O(1) lookup: /health, /docs, /openapi.json
- [01-03]: Integration tests use MockAgentFrameworkAgent rather than real agent (no Azure credentials needed)
- [02-01]: SafeAreaView from react-native-safe-area-context for consistent safe area handling
- [02-01]: Toast: ToastAndroid on Android, Alert.alert on iOS (no third-party library for MVP)
- [02-01]: Removed default App.tsx/index.ts -- expo-router uses app/_layout.tsx as entry
- [02-02]: EventSource<AGUIEventType> generic parameter for type-safe custom AG-UI event listeners
- [02-02]: Inline state-driven toast instead of third-party library
- [02-02]: Fire-and-forget: only RUN_FINISHED and error events, no TEXT_MESSAGE_CONTENT (Phase 4)
- [03-01]: Shared AzureOpenAIChatClient across all agents (one client, not one per agent)
- [03-01]: Orchestrator autonomous, Classifier interactive (Phase 4 HITL readiness)
- [03-01]: All four bucket scores stored in ClassificationMeta.allScores for future threshold tuning
- [03-01]: Bi-directional linking: InboxDocument.filedRecordId <-> BucketDocument.inboxRecordId
- [03-01]: Used str type for bucket param (not Literal) for Agent Framework JSON schema compatibility
- [03-01]: AsyncDefaultAzureCredential for Key Vault, sync DefaultAzureCredential for AzureOpenAIChatClient
- [03-02]: onComplete receives accumulated result string (not void) for classification feedback
- [03-02]: Stay on screen after capture (removed router.back) for rapid-fire input
- [03-02]: Accept echo bug in accumulated result for Phase 3 (Phase 4 will filter)
- [03-02]: Fallback to "Captured" toast when result is empty/falsy
- [04-01]: Raw Workflow instead of WorkflowAgent for HITL resume (WorkflowAgent doesn't expose run(responses=...))
- [04-01]: Custom AG-UI endpoint replaces add_agent_framework_fastapi_endpoint for mixed AgentResponseUpdate + BaseEvent streams
- [04-01]: Echo filter by author_name: suppress Orchestrator text-only updates, pass through Classifier content
- [04-01]: Classifier removed from autonomous mode to enable request_info emission for HITL
- [04-02]: Shared attachCallbacks helper extracts SSE event routing for both sendCapture and sendClarification
- [04-02]: sendCapture returns { cleanup, threadId } to support HITL thread reference from capture screen
- [04-02]: Input area uses minHeight/maxHeight (not flex: 1) to make room for step dots and streaming text below
- [04-02]: Tab navigation: (tabs) group inside Stack root layout with modal screens alongside
- [04-02]: Old app/index.tsx removed to avoid expo-router route conflict with (tabs)/index.tsx
- [04-03]: InboxItem uses inline getRelativeTime utility (no library) for relative timestamps
- [04-03]: Detail card as Modal overlay within inbox screen, not a separate route
- [04-03]: Conversation screen fetches item detail via GET /api/inbox/{threadId} for context display
- [04-03]: Expired HITL sessions handled gracefully with resubmission message
- [04-04]: request_clarification returns "Clarification -> {uuid} | {text}" format parsed by adapter regex
- [04-04]: Respond endpoint uses upsert_item on existing Inbox doc (not classify_and_file re-call)
- [04-04]: HITL_REQUIRED event includes inboxItemId and questionText for client resolution
- [04-04]: Clarification detection prioritized over confidence detection in adapter scanning
- [04-05]: Top 2 buckets on capture screen derived from questionText heuristic (first 2 BUCKETS mentioned)
- [04-05]: Top 2 buckets on conversation screen derived from allScores sorting (data-driven)
- [04-05]: clarificationText as primary question source; generic question is fallback only
- [04-05]: isPending checks both 'pending' and 'low_confidence' for backward compatibility
- [04.1-01]: uv 0.5.4 pinned in Dockerfile for reproducible builds (COPY --from=ghcr.io/astral-sh/uv:0.5.4)
- [04.1-01]: Port 8000 in container (standard), not 8003 (local dev only in __main__ block)
- [04.1-01]: Graceful chat client fallback: server starts without Azure OpenAI credentials (matches Key Vault/Cosmos pattern)
- [04.1-01]: uv.lock tracked in git for reproducible Docker builds
- [04.1-02]: ACR_NAME hardcoded in workflow (wkmsharedservicesacr) -- simpler than GitHub variable for solo project
- [04.1-02]: GitHub repository variables (not secrets) for AZURE_CLIENT_ID, TENANT_ID, SUBSCRIPTION_ID
- [04.1-02]: Single-job workflow with 5 steps; path filter backend/** for targeted triggers
- [04.1-02]: SHA-based image tagging (github.sha) for immutable, traceable deployments
- [04.1-02]: OIDC Workload Identity Federation (azure/login@v2) -- no stored secrets
- [04-06]: Classifier removed from autonomous mode agents list -- only Orchestrator is autonomous; Classifier pauses on request_clarification for HITL
- [04-06]: Respond endpoint returns SSE error (not fake success) when inbox_item_id is missing or processing fails
- [04-06]: Badge count derived in separate useEffect(items) instead of inside fetchInbox to avoid stale closure
- [04-06]: fetchInbox useCallback has empty dep array since deduplication uses functional state updater
- [04.2-01]: Swipeable from react-native-gesture-handler (no reanimated dependency needed)
- [04.2-01]: GestureHandlerRootView wraps root layout for gesture support
- [04.2-01]: DELETE /api/inbox/{item_id} cascade deletes bucket document via filedRecordId + classificationMeta.bucket
- [04.2-01]: Cascade delete is non-fatal -- missing bucket doc logged as warning, inbox delete still proceeds
- [04.2-01]: Optimistic UI removal with re-fetch on API failure; Alert.alert confirmation before delete
- [04.2-01]: Config fix: api_key_secret_name was "sb-api-key" but Key Vault secret is "second-brain-api-key"
- [04.3-01]: request_clarification replaced entirely by request_misunderstood -- old tool conflated uncertain-between-buckets with truly-unclear
- [04.3-01]: Low-confidence items get status="pending" (was "low_confidence") -- consistent with mobile isPendingStatus
- [04.3-01]: Pending return string "Filed (needs review)" distinct from "Filed" for capture screen toast differentiation
- [04.3-01]: Misunderstood inbox docs have no classificationMeta and no bucket filing -- truly unclear input has no classification
- [04.3-01]: Low-confidence HITL_REQUIRED fallback removed from adapter -- pending items complete silently without user interruption
- [04.3-02]: Preserved original confidence/allScores during recategorize to maintain classification context
- [04.3-02]: Non-fatal old bucket doc deletion -- orphaned doc is harmless per CONTEXT.md research
- [04.3-02]: User appended to agentChain only if not already present (prevents duplicates on re-recategorize)
- [04.3-03]: Stream interception over client-side max-round logic: endpoint wraps SSE stream to replace MISUNDERSTOOD with UNRESOLVED at round >= 2
- [04.3-03]: Orphan cleanup at round 2: request_misunderstood tool creates new inbox doc before endpoint can intercept, so endpoint deletes orphan
- [04.3-03]: handleFollowUpSubmit declared before handleSubmit to avoid TypeScript block-scoped variable error
- [04.3-03]: datetime import moved from inline to module-level in main.py for use by both respond and follow-up endpoints

### Roadmap Evolution

- Phase 04.1 inserted after Phase 4: Backend Deployment to Azure Container Apps (URGENT) — cannot do real UAT without deployed backend
- Phase 04.2 inserted after Phase 04.1: Swipe-to-delete inbox items (URGENT) — needed for data hygiene during testing
- Phase 04.3 inserted after Phase 4: agent-user UX with unclear item (URGENT)

### Pending Todos

None yet.

### Blockers/Concerns

- [Resolved]: React Native AG-UI client custom-built using react-native-sse with EventSource<AGUIEventType> generic typing (Phase 2)
- [Resolved]: Cosmos DB partition key decision — /userId only (finalized in Phase 1 context)
- [Research]: Whisper + expo-audio integration needs targeted research spike before Phase 5

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 04.3-03-PLAN.md
Resume file: .planning/phases/04.3-agent-user-ux-with-unclear-item/04.3-03-SUMMARY.md
