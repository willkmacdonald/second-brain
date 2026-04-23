# Phase 21: Eval Framework - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 21-eval-framework
**Areas discussed:** Eval execution model, Trigger & results UX, Admin Agent eval scope, Dataset seeding strategy

---

## Eval execution model

| Option | Description | Selected |
|--------|-------------|----------|
| Backend API endpoint | Dedicated /api/eval/run endpoint, background task, returns run ID | ✓ |
| Standalone CLI script | Script in backend/scripts/, duplicates Foundry client setup | |
| GitHub Actions workflow | CI job, doesn't solve mobile/Claude Code triggering | |

**User's choice:** Backend API endpoint
**Notes:** Reuses existing Foundry client, Cosmos connections, and tools already wired in the backend

| Option | Description | Selected |
|--------|-------------|----------|
| Real Foundry agent run | Full thread + agent run, tests actual pipeline | ✓ |
| Direct GPT-4o API call | Bypasses Foundry, risks eval/prod divergence | |

**User's choice:** Real Foundry agent run
**Notes:** Full fidelity — tests the actual agent configuration and tool schema

| Option | Description | Selected |
|--------|-------------|----------|
| Sequential | One at a time, 3-5 min for 50 cases | ✓ |
| Bounded concurrency | 5 at a time, ~1 min but more complex | |
| You decide | Claude picks | |

**User's choice:** Sequential
**Notes:** Simple and reliable, acceptable duration for on-demand eval

---

## Trigger & results UX

| Option | Description | Selected |
|--------|-------------|----------|
| Investigation agent command | Ask agent "run classifier eval", calls @tool, no new UI | ✓ |
| Button on Status screen | Dedicated button, requires new mobile UI | |
| Quick action chip | Chip on investigation chat, combines discoverability with conversational | |

**User's choice:** Investigation agent command
**Notes:** No new mobile UI needed, reuses existing investigation chat screen

| Option | Description | Selected |
|--------|-------------|----------|
| MCP tool | New run_eval MCP tool on second-brain-telemetry server | |
| Investigation /investigate skill | Routes through investigation agent via deployed API | ✓ |
| You decide | Claude picks | |

**User's choice:** Investigation /investigate skill
**Notes:** No new MCP tool needed, keeps triggering unified through investigation agent

| Option | Description | Selected |
|--------|-------------|----------|
| Investigation agent chat response | Formatted markdown with accuracy, precision/recall table | ✓ |
| Eval scores on Status dashboard cards | Dashboard card with latest scores | |
| Both | Chat response + dashboard card | |

**User's choice:** Investigation agent chat response
**Notes:** Dashboard cards deferred — can add later if needed

---

## Admin Agent eval scope

| Option | Description | Selected |
|--------|-------------|----------|
| Routing accuracy only | Check destination correctness, skip tool call verification | ✓ |
| Routing + tool usage correctness | Check outcome AND tool call sequences, harder to curate | |
| Minimal — defer to Phase 22 | Only build classifier eval in Phase 21 | |

**User's choice:** Routing accuracy only
**Notes:** Keeps golden dataset simple, evaluator straightforward

| Option | Description | Selected |
|--------|-------------|----------|
| Real agent run | Same pattern as classifier, with dry-run tool handlers | ✓ |
| Historical comparison | Query existing data, doesn't test current behavior | |
| You decide | Claude picks | |

**User's choice:** Real agent run
**Notes:** Dry-run tool handlers intercept tool calls without side effects

---

## Dataset seeding strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Export real captures + manual curation | Export Inbox items, manually label, import as GoldenDatasetDocuments | ✓ |
| Synthetic generation | GPT-4o generates test texts, may not match real patterns | |
| Mix — real + synthetic | 30-40 real + 10-20 synthetic edge cases | |
| You decide | Claude picks | |

**User's choice:** Export real captures + manual curation
**Notes:** Real data = realistic eval, most trustworthy approach

| Option | Description | Selected |
|--------|-------------|----------|
| Part of Phase 21 | Export/curation/import script is a Phase 21 deliverable | ✓ |
| Pre-work before Phase 21 | Manual seeding before phase starts | |

**User's choice:** Part of Phase 21
**Notes:** Eval framework can't be tested without data — seeding is a prerequisite

| Option | Description | Selected |
|--------|-------------|----------|
| Input text + expected destination | Routing accuracy only, simpler to curate | ✓ |
| Input text + destination + items | Also verify item extraction, harder to match exactly | |
| You decide | Claude picks | |

**User's choice:** Input text + expected destination
**Notes:** Focused on routing accuracy, requires known affinity rules as test fixtures

---

## Claude's Discretion

- Eval status polling mechanism
- Classifier eval result formatting
- Dry-run tool handler implementation approach
- GoldenDatasetDocument model extension vs separate model for admin test cases
- Export script output format
- Multi-bucket split handling in classifier golden dataset
- Confidence calibration metric calculation

## Deferred Ideas

- Eval scores dashboard card on Status screen (deferred from Phase 18)
- Eval results quick action chip (deferred from Phase 18)
- Tool call sequence verification for Admin Agent eval
- Synthetic edge case generation
- GitHub Actions eval workflow (Phase 22)
