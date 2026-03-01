# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

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

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 8 | 28 | Initial project, learned GSD workflow |
| v2.0 | 5 | 16 | Mature GSD usage, UAT-driven gap closure, scope redefinition |

### Top Lessons (Verified Across Milestones)

1. **UAT catches what automated checks miss** — true in both v1.0 (HITL flow bugs) and v2.0 (pending recategorize, orphan docs)
2. **Smaller milestones ship faster** — v1.0 was "partial" because scope was too large; v2.0 shipped clean by cutting scope at audit
