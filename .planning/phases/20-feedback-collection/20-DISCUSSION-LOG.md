# Phase 20: Feedback Collection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 20-feedback-collection
**Areas discussed:** Signal capture points, Golden dataset promotion

---

## Signal Capture Points

### Q1: When should implicit signals be written?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in handler (Recommended) | Write FeedbackDocument directly inside existing handlers. Fire-and-forget with logging. | ✓ |
| Background post-action | Async task writes signal after primary action completes. More decoupled. | |
| Change Feed listener | Cosmos Change Feed detects mutations and derives signals. Most decoupled but complex. | |

**User's choice:** Inline in handler
**Notes:** None

### Q2: Should a failed signal write block the primary action?

| Option | Description | Selected |
|--------|-------------|----------|
| Never block (Recommended) | Signal write wrapped in try/except with logger.warning. User action always succeeds. | ✓ |
| Fail the request | Whole action fails if signal can't be written. Guarantees completeness. | |

**User's choice:** Never block
**Notes:** None

---

## Golden Dataset Promotion

### Q1: How should a feedback signal become a golden dataset entry?

| Option | Description | Selected |
|--------|-------------|----------|
| Promote button on signal (Recommended) | View signals via investigation agent, promote individual items, confirm label. | ✓ |
| Auto-promote after N consistent signals | Auto-promote if 3+ signals agree on same mapping. Builds dataset faster but risks systematic errors. | |
| Batch review screen | Dedicated mobile screen for reviewing signals. Swipe to promote/discard. | |

**User's choice:** Promote button on signal (via investigation agent)
**Notes:** None

### Q2: Where do you review and promote signals?

| Option | Description | Selected |
|--------|-------------|----------|
| Investigation agent only (Recommended) | Ask agent to show misclassifications, promote via natural language. No new mobile screen. | ✓ |
| Dedicated mobile screen | New screen with promote/discard actions. Significant mobile UI work. | |
| Claude Code MCP only | Review from dev terminal. Fast but not accessible from mobile. | |

**User's choice:** Investigation agent only
**Notes:** None

### Q3: What confirmation is needed when promoting?

| Option | Description | Selected |
|--------|-------------|----------|
| Agent confirms label before writing (Recommended) | Agent shows capture text + label, user confirms, then writes GoldenDatasetDocument. | ✓ |
| Auto-promote on command | No confirmation — immediate write. Faster but no safety net. | |

**User's choice:** Agent confirms label before writing
**Notes:** None

---

## Claude's Discretion

- Thumbs up/down UI placement and interaction pattern
- Investigation tool parameter design
- FEED-04 response formatting
- MCP tool equivalents for signal querying
- Signal deduplication strategy

## Deferred Ideas

None — discussion stayed within phase scope
