# Phase 3: Text Classification Pipeline - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Orchestrator and Classifier agents that route text input to the correct bucket (People, Projects, Ideas, Admin) in Cosmos DB with confidence scoring. Captures are logged to Inbox with full trace metadata. User sees a confirmation toast with bucket and confidence. HITL clarification for low-confidence captures is Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Bucket Definitions
- **People**: Relationships, interactions, social context ("talked to Sarah", "need to call Mom")
- **Projects**: Multi-step endeavors with a goal ("deck rebuild", "launch the newsletter")
- **Ideas**: Thoughts to revisit later, reflections, emotional processing, no immediate action ("feeling grateful", "what if we tried X")
- **Admin**: One-off tasks, errands, logistics, time-sensitive items ("buy milk", "renew passport", "dentist appointment")
- Multi-bucket captures (person + project): primary intent wins. LLM determines if the capture is ABOUT the person or ABOUT the project
- Cross-references between buckets come in Phase 7

### Classification Approach
- Classifier prompt includes 5-10 few-shot examples covering each bucket + edge cases
- Classifier extracts a short title from the capture (e.g., "need to fix the leaky faucet" → "Fix leaky faucet")
- Junk/nonsense input (gibberish, accidental submissions) is filed to Inbox only with status "unclassified" — not classified into a bucket

### Record Schema
- Minimal records when filing to bucket containers: id, userId, title, rawText, bucket, confidence, createdAt
- Other fields (nextAction, followUps, interactionHistory, etc.) added by later phases
- Bi-directional linking: Inbox record has filedRecordId, bucket record has inboxRecordId

### Confirmation Feedback
- Format: "Filed → Projects (0.85)" — bucket name and confidence, no title in toast
- Display: Toast notification (same pattern as Phase 2), auto-dismisses after 2-3 seconds
- Timing: Wait for full agent chain to complete before showing confirmation
- Error: Generic error toast "Couldn't file your capture. Try again." — no technical details
- After toast: Stay on text input screen (clear field, ready for next capture). This changes Phase 2's auto-navigate-back behavior
- Classification result replaces the generic "Thought captured" toast from Phase 2

### Inbox Logging
- Full trace metadata: rawText, title, bucket, confidence, ALL four classification scores, agentChain, LLM model, token counts, processing duration, timestamps
- Bi-directional links to bucket record
- Junk captures get minimal record only: rawText, status "unclassified", timestamps (no classification scores or agent chain)

### Confidence Threshold
- Threshold: 0.6 (from requirements, kept as-is)
- Configurable via environment variable: CLASSIFICATION_THRESHOLD=0.6
- Below 0.6: still file to best bucket, but mark Inbox record as "low_confidence". Phase 4 adds HITL conversation
- Confirmation format is the same regardless of confidence — the score itself communicates certainty

### Claude's Discretion
- Exact few-shot examples for the classifier prompt
- Classifier prompt wording and structure
- Agent chain error handling implementation details
- Inbox record field naming conventions (camelCase per Phase 1 decision)

</decisions>

<specifics>
## Specific Ideas

- Confirmation format explicitly matches the spec: "Filed → Projects (0.85)"
- Stay on text input after filing enables rapid-fire capture — this is the primary UX improvement over Phase 2
- All four classification scores stored in Inbox enables future analysis of classifier behavior and threshold tuning

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-text-classification-pipeline*
*Context gathered: 2026-02-21*
