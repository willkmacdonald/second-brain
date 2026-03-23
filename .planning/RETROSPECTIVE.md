# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v3.0 — Admin Agent & Shopping Lists

**Shipped:** 2026-03-23
**Phases:** 12 | **Plans:** 33

### What Was Built
- Admin Agent as second persistent Foundry agent with 6 tools (errands, destinations, affinity rules, recipe fetch)
- Dynamic destination affinity system replacing hardcoded store routing, with voice-managed rules and HITL auto-learning
- Multi-bucket splitting for mixed-content captures using batched tool call pairing
- Recipe URL extraction with three-tier fetch (Jina Reader, httpx, Playwright) and source attribution
- On-device voice transcription via iOS SFSpeechRecognizer, eliminating cloud API costs
- End-to-end observability: per-capture trace IDs, structured logging, 4 KQL queries, 3 Azure Monitor alerts
- Security hardening: timing-safe auth, parameterized Cosmos queries, error sanitization, upload validation
- Status & Priorities screen with destination-grouped errands, processing banner, admin notifications

### What Worked
- **Status-screen-triggered processing** — processing only when user opens Status screen matches real workflow perfectly, avoids wasted background cycles
- **UAT-driven gap closure loops** — Phases 11.1, 12.1 both had gap closure plans (03/04 and 02) that fixed real bugs found in UAT
- **Inserted decimal phases for urgent work** — 11.1, 12.1, 12.2, 12.3, 12.3.1, 12.5 all handled naturally without disrupting the main roadmap
- **Security audit as dedicated phase (12.3.1)** — codebase mapper → concerns doc → dedicated phase was thorough and systematic
- **Tech debt cleanup as final phase (15)** — collecting all debt from milestone audit and fixing in one pass before completion

### What Was Inefficient
- **Naming evolved too late** — "shopping lists" renamed to "errands" in Phase 12.2 after 4 phases of shopping-specific naming. Earlier generalization would have avoided the rename phase entirely.
- **REQUIREMENTS.md not updated during inserted phases** — DEST-01-07, VOICE-OD-01-03 weren't registered until Phase 15 forced it. Inserted phases should update traceability immediately.
- **Retry query regression** — Phase 12.2 rename accidentally dropped the failed/pending conditions from the retry query (added in 12.1-02). Rename operations need explicit regression checks on query logic.
- **7 decimal phases** — v3.0 had more inserted phases than planned phases (7 inserted vs 4 planned). Scope estimation for specialist agent work needs improvement.

### Patterns Established
- **Processing-on-demand via API side-effect** — GET /api/errands triggers background processing as a side effect, returning processingCount for mobile polling. Cleaner than fire-and-forget at capture time.
- **pending_calls dict for SDK batched tool calls** — Azure AI SDK delivers function_call contents in one update and function_result in another. Dict-based pairing by call_id is the correct pattern.
- **Three-tier fetch strategy** — Jina Reader (fast, clean) → httpx (fallback, raw) → Playwright (heavyweight, JS-rendered). Each tier catches different site types.
- **Delivery heuristic for agent responses** — keyword-based classification of agent responses determines which need user-facing notification vs silent completion
- **ContextVar + Cosmos doc for trace propagation** — ContextVar for synchronous call chain, persisted on Cosmos doc for async background processing

### Key Lessons
1. **Naming decisions compound** — choosing "shopping lists" over "errands" early created a full rename phase later. Generic naming from the start saves a phase.
2. **Inserted phases should update traceability immediately** — not just at the end. Makes milestone audit cleaner.
3. **Rename operations need query regression checks** — any file rewrite (not just find-replace) risks dropping conditional logic.
4. **Admin Agent workflow: capture → review → process** — auto-processing at capture time was wrong. Users want to review before triggering agent work.
5. **Dynamic over hardcoded from day one** — KNOWN_STORES/KNOWN_DESTINATIONS went through 3 forms before landing on dynamic Cosmos queries. Start dynamic.

### Cost Observations
- Model mix: ~60% sonnet (agents, execution), ~40% opus (orchestration, verification, planning)
- 22 days from first commit to milestone ship
- v3.0 plans averaged 3.2 min each — consistent with v1.0 (3.2 min) and v2.0 (3.3 min)
- Notable: 137 commits for 33 plans = ~4 commits per plan (higher than v2.0 due to gap closure work)

---

## Milestone: v2.0 — Foundry Migration & HITL Parity

**Shipped:** 2026-03-01
**Phases:** 5 | **Plans:** 16

### What Was Built
- Foundry Agent Service migration with persistent Classifier agent
- FoundrySSEAdapter replacing 540-line AGUIWorkflowAdapter with ~170-line async generators
- HITL parity: low-confidence bucket selection, misunderstood follow-up (text + voice), recategorize
- Application Insights observability with OTel spans and token usage tracking
- Unified capture screen with Voice/Text toggle, inline text capture, processing stages
- ContextVar-based in-place follow-up updates eliminating orphan reconciliation

### What Worked
- **Phase-by-phase incremental migration** — each phase (infra → agent → streaming → HITL) was independently testable and shippable
- **UAT-driven gap closure** — testing on real devices caught issues that automated checks missed (pending recategorize bug, follow-up orphans, classifier boundary tuning)
- **GSD workflow** — research → plan → execute → verify loop caught issues before they compounded
- **Scope redefinition at audit** — recognizing that shipping migration separately from specialist agents was the right cut point

### What Was Inefficient
- **Phase 9 had 7 plans** (3 gap fixes + 3 UAT fixes) — HITL parity needed more upfront research on edge cases before the first plan
- **Orphan reconciliation was built then deleted** — Plan 09-01 built a reconciliation pattern that Plan 09-07 replaced with ContextVar prevention. Should have researched the prevention approach first.
- **Phase 4.3 patterns not fully carried forward** — some v1 HITL patterns needed rediscovery during v2 migration

### Patterns Established
- **ContextVar for @tool state injection** — Foundry @tools can't accept extra params, but ContextVars pass state through the call stack
- **Async generator SSE adapters** — simpler than class-based adapters, easier to compose with wrapper generators for side effects
- **Wrapper generator pattern** — `_stream_with_*` wrappers for post-stream side effects (thread persistence, follow-up context) keep the core adapter pure
- **OTel spans inside async generators** — preserves trace context across async boundaries (not in endpoint handlers)
- **Same-bucket promotion** — recategorize endpoint must handle pending → classified even when bucket doesn't change

### Key Lessons
1. **Prevention > reconciliation** — preventing orphan docs via ContextVar is simpler and more reliable than post-hoc cleanup
2. **UAT on real devices is non-negotiable** — automated verification catches code correctness but misses UX issues and edge-case backend bugs
3. **Scope creep at milestone level** — defining v2.0 as "Proactive Second Brain" (6 specialist agents + push + scheduling) was too ambitious. Shipping the migration separately was the right call.
4. **Connected Agents don't work with local @tools** — this was the most impactful research finding, forcing the FastAPI routing architecture

### Cost Observations
- Model mix: ~70% sonnet (agents), ~30% opus (orchestration)
- 4 days from first commit to milestone ship
- Notable: v2.0 plans averaged 3.3 min each — similar velocity to v1.0 (3.2 min)

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Days | Key Change |
|-----------|--------|-------|------|------------|
| v1.0 | 8 | 28 | ~5 | Initial project, learned GSD workflow |
| v2.0 | 5 | 16 | 4 | Mature GSD usage, UAT-driven gap closure, scope redefinition |
| v3.0 | 12 | 33 | 22 | Heavy inserted-phase usage (7 decimal), security audit phase, tech debt cleanup phase |

### Top Lessons (Verified Across Milestones)

1. **UAT catches what automated checks miss** — true in v1.0 (HITL flow bugs), v2.0 (pending recategorize, orphan docs), and v3.0 (batched tool calls, classifier over-analysis, retry query regression)
2. **Smaller milestones ship faster** — v1.0 was "partial" because scope was too large; v2.0 shipped clean by cutting scope; v3.0 grew organically via inserted phases but shipped complete
3. **Gap closure as dedicated plans works** — v2.0 Phase 9 and v3.0 Phases 11.1/12.1/15 all used targeted gap closure plans successfully
4. **Naming decisions compound across phases** — v3.0 proved generic naming should be chosen from the start to avoid full-rename phases later
