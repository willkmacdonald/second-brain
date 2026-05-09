# Phase 24: Foundry GA Migration — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-09
**Phase:** 24-foundry-ga-migration
**Areas discussed:** Voice path topology, Tools class binding pattern, Admin retry semantics, Wave parallelization + commit ordering

---

## Voice path topology (D-07b implementation)

### Round 1 (rejected, then revisited)

| Option | Description | Selected |
|--------|-------------|----------|
| Direct transcription call | Cloud transcription becomes plain async function call (NOT a registered tool). Classifier registers ONLY file_capture. tool_choice='required' unambiguous. ~15 lines. | |
| Single-tool transcription sub-agent | Tiny Agent(tools=[transcribe_audio], tool_choice='required'). More framework-first; framework spans free. Heavier than warranted. | |
| Defer the split — keep voice path as-is for now | Skip architectural split, only do tool_choice='required' switch. WARNING: violates D-07b reasoning chain. | ✓ |

**User's choice:** Defer the split — keep voice path as-is

**Notes:** Initial choice flagged as inconsistent with D-07b. Re-asked.

### Round 2 (locked)

| Option | Description | Selected |
|--------|-------------|----------|
| Defer split + keep safety net | Don't split voice path. Don't delete Python safety net. Don't use tool_choice='required'. Classifier keeps both tools + Python catch. forced_tool_failure NOT added. Clean carve-out, but loses D-07b's MISUNDERSTOOD-vs-ERROR distinction. | |
| Split voice path — reverse my earlier answer | Go with design as written: direct transcription call OR single-tool sub-agent. Pick (a) direct call. Classifier ONLY file_capture, tool_choice='required', delete safety net, add forced_tool_failure. | |
| Defer entire D-07b change | SDK-only migration. Voice split, tool_choice='required', safety-net delete, forced_tool_failure all become follow-up phase 24.1. Most conservative. | |

**User's freeform response:** "the on-device transcription works VERY well - and I believe removes a lot of complexity in the overall design. I think I missed the rationale for a different approach"

**Notes:** Will recognized that on-device transcription (Phase 12.5) is primary; cloud is rare fallback. Initial concern about complexity was real but smaller than design implies. Re-asked with that framing.

### Round 3 (locked)

| Option | Description | Selected |
|--------|-------------|----------|
| Direct transcription call | Cloud transcription becomes plain async function call (NOT a registered tool). Classifier registers ONLY file_capture. tool_choice='required' unambiguous. Safety net deleted. forced_tool_failure SSE sub-code added. ~15 lines for fallback path. Matches D-07b. | ✓ |
| Sub-agent for transcription | Tiny Agent(tools=[transcribe_audio], tool_choice='required'). Heavier than warranted for rare fallback. | |
| Keep cloud-transcription as-is | Don't touch fallback. Keep safety net + tool_choice='auto'. SDK-only migration. forced_tool_failure not added. Defer D-07b entirely. | |

**User's choice:** Direct transcription call (Recommended)

**Notes:** Locked. Once Will saw the on-device-primary framing, the direct call became the obviously correct choice.

---

## Tools class binding pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Bound methods on tools class | Keep InvestigationTools/AdminTools/ClassifierTools classes. Drop @tool(approval_mode=...). Pass tools=[instance.method,...] to Agent. Cosmos DI via __init__ preserved. Smaller diff. Existing tests survive. Design's parenthetical 'preserves Cosmos manager DI without globals' nudges this way. | ✓ |
| Plain async functions with closure-captured deps | Convert each method to top-level async def. Deps from factory closure or module global. More 'framework-first idiomatic' per Microsoft examples. Bigger diff. Test fixture rework. Globals smell; closures add indirection. | |
| Mixed — bound methods for stateful tools, plain functions for stateless | Hybrid. Reviewers must judge each tool's category. Adds review burden. Probably overkill. | |

**User's choice:** Bound methods on tools class (Recommended)

**Notes:** Decision applies to all 16 production tools across 3 agent classes (Investigation 9, Admin 6, Classifier 1).

---

## Admin retry semantics (23.2)

| Option | Description | Selected |
|--------|-------------|----------|
| tool_choice='required' + post-hoc check + 1 retry | Force model to call SOME tool (string form, probe-verified). Read response.messages to see which tool fired. If neither output tool fired, retry once with directive prompt. Justifiable under D-07: framework primitive didn't fully solve 'specifically output tools required.' One bounded retry with explicit-justification entry. Background path — latency acceptable. | ✓ |
| tool_choice='auto' + Python retry loop (status quo) | Match RC behavior exactly. No forcing; existing retry loop just rewritten for GA response shape. Most conservative. D-07 entry says 'no framework primitive pins a subset; auto + retry preserves observed admin behavior.' Smaller blast radius for admin migration. | |
| Spike the 'mode' dict schema first, then decide | Add small probe in 23.2 planning to try {'mode': 'required', 'name': '...'} shapes against live Foundry. If schema works, retry collapses to single framework-pinned run. Best D-07 outcome IF schema exists. Risk: could burn time and fall back to A or B anyway. | |

**User's choice:** tool_choice='required' + post-hoc check + 1 retry (Recommended)

**Notes:** Probe 3 showed the OpenAI-style provider-dict raises ContentError. The undocumented 'mode' schema spike was rejected as time-risky. The bounded retry is recorded as a D-07 explicit-justification entry rather than a fidelity failure.

---

## Wave parallelization + commit ordering

### Sub-question 1: Wave parallelization within task groups

| Option | Description | Selected |
|--------|-------------|----------|
| Fully sequential | Each plan is its own commit, in order. Avoids parallel executor agents writing to main.py / lifespan / config.py concurrently. Matches design's 'sequential commits on local main' framing. ~5-7 commits per task group, 15-20 total. | ✓ |
| Parallel waves where dependency edges allow | Within task group, plans touching disjoint files run in same wave. Agent rewrite + lifespan stays serial. Faster overall. Risk: parallel executors writing to overlapping files. | |
| Hybrid — sequential 23.1, parallel 23.2/23.3 once patterns are set | 23.1 sequential (most learning, biggest unknowns). 23.2/23.3 inherit and parallelize disjoint work. Trades early-phase safety for later-phase speed. | |

**User's choice:** Fully sequential (Recommended)

### Sub-question 2: Custom-span deletion vs middleware addition order in 23.1

| Option | Description | Selected |
|--------|-------------|----------|
| Middleware first, then delete custom spans | Commit N: add agents/middleware/capture_trace.py + wire on Investigation. Commit N+1: delete custom tracer.start_as_current_span wrapping. Brief overlap (N has both; N+1 has only middleware) but capture.trace_id always tagged at source. Local main commits stay individually runnable for debugging. | ✓ |
| Atomic — both in same commit | One commit swaps custom span wrapping for middleware. Cleanest review (reviewer sees the swap). Bigger commit. Harder to bisect. | |
| Delete custom spans first, middleware second | Commit N: delete custom wrapping. Commit N+1: add middleware. Brief gap where capture.trace_id is missing on framework spans for Investigation on local main. Strictly worse than A or B. | |

**User's choice:** Middleware first, then delete custom spans (Recommended)

**Notes:** Pattern propagates to 23.2 (admin_handoff.py custom spans) and 23.3 (streaming/adapter.py custom spans for capture_text/capture_voice/capture_follow_up).

---

## Final round-up

| Question | Answer |
|----------|--------|
| Want to discuss 5 deferred gray areas (push guard, forced_tool_failure emission, routing-context injection, RBAC + auth_probe timing, env-var sequencing) or revisit decided areas? | Ready for context |

---

## Claude's Discretion

The following decisions are recorded in CONTEXT.md `<decisions>` § "Claude's Discretion" — for the planner / executor to set:

- Push guard mechanism (Task 0): planner uses Option A (pre-push hook + sentinel) by default; falls back to Option B (rename remote) only if hook installation fails on this machine.
- `forced_tool_failure` SSE emission point: adapter / agent / middleware level. Planner picks based on cleanest exception context.
- Routing-context injection for Admin: keep `get_routing_context` as a tool (current pattern, lowest-risk) vs move to `FunctionMiddleware`. Planner can elevate to design-time decision in 23.2.
- RBAC verification timing: verify Container App managed identity has `Azure AI User` BEFORE env-var update. If missing, assign via `az role assignment create` as part of 23.3 deploy preparation.
- `auth_probe` re-run policy: re-run from laptop one final time as part of 23.3 pre-push gate.
- Plan count per task group: planner decides. ~5-7 plans per task group target.

## Deferred Ideas

- `forced_tool_failure` SSE sub-code emission point (mechanical, planner picks)
- Routing-context injection for Admin — keep as tool (recommended) vs FunctionMiddleware
- Per-destination precision/recall metric expansion (separate follow-up; eval/metrics.py change)
- `'mode'` dict schema for `tool_choice` provider-dict pinning (could enable zero-retry admin if schema discovered; not pursued)
- Deletion of `backend/scripts/foundry_probe.py` after 7 days post-deploy stability
- Foundry-native eval cutover (Phase 21.1) — separate phase per D-04
- Self-monitoring loop (Phase 22) — independent
