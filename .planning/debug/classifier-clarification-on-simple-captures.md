---
status: diagnosed
trigger: "Investigate why the Classifier agent asks for clarification on a simple single-intent capture like 'I need to buy dog food' instead of filing it directly to Admin with high confidence."
created: 2026-03-02T06:00:00Z
updated: 2026-03-02T06:30:00Z
---

## Current Focus

hypothesis: The multi-intent detection instructions added to the Classifier Foundry agent in Phase 11.1 made the Classifier over-analyze single-intent captures, causing it to call file_capture with status="misunderstood" instead of status="classified" for conversational phrasing like "I need to buy dog food"
test: Compare Classifier behavior on conversational ("I need to buy dog food") vs imperative ("Buy dog food") phrasing; examine adapter code for any code-level cause
expecting: Code paths are correct; the Classifier LLM is the only decision-maker for status
next_action: Document root cause and suggested instruction fix

## Symptoms

expected: "I need to buy dog food" -> immediate filing to Admin with high confidence (single file_capture call, status="classified", bucket="Admin")
actual: Classifier asked for clarification twice. Only succeeded when user rephrased to "Buy Dog food" (imperative style)
errors: No code errors. The Classifier agent itself chose to set status="misunderstood" instead of status="classified"
reproduction: Send "I need to buy dog food" as a text capture via the mobile app
started: After Phase 11.1 multi-intent detection instructions were added to the Classifier Foundry agent. Before 11.1, this exact phrasing would have been filed immediately.

## Eliminated

- hypothesis: "Adapter code change in Phase 11.1 introduced a bug that causes misunderstood events for single-intent captures"
  evidence: "The adapter multi-result refactoring (file_capture_results list) is functionally equivalent to the old single-variable pattern for single file_capture calls. The adapter does NOT decide status -- it reads status from the Classifier's file_capture call arguments. The code path for a single file_capture result with status='classified' produces the exact same CLASSIFIED SSE event as pre-11.1. Verified by reading adapter.py lines 233-296: single result uses classified_event with 3 args (no buckets/itemIds), identical to old behavior."
  timestamp: 2026-03-02T06:10:00Z

- hypothesis: "The mobile SSE client incorrectly routes CLASSIFIED events to the MISUNDERSTOOD handler"
  evidence: "The ag-ui-client.ts switch statement has separate cases for CLASSIFIED (line 69) and MISUNDERSTOOD (line 87). The switch cases are distinct and correct. If the mobile showed a clarification prompt, it received a MISUNDERSTOOD event from the backend, which means the Classifier agent chose status='misunderstood' in its file_capture call."
  timestamp: 2026-03-02T06:12:00Z

- hypothesis: "The text capture endpoint or message construction changed in a way that corrupts the user message before the Classifier sees it"
  evidence: "capture.py line 174: messages = [Message(role='user', text=user_text)] -- the user_text is passed directly from body.text (line 152/168). No transformation, no prefix, no wrapper. The Classifier receives the exact text the user typed. The stream_text_capture signature and message construction are unchanged from pre-11.1."
  timestamp: 2026-03-02T06:14:00Z

- hypothesis: "Voice captures bypass the multi-intent analysis instructions somehow"
  evidence: "Voice and text captures both use the same Classifier agent (same agent_id, same Foundry instructions). The only difference is voice captures first call transcribe_audio to get text, then the Classifier files that text. The Classifier instructions apply equally to both paths. Voice working fine is likely because transcription produces cleaner, more direct phrasing that the Classifier handles better."
  timestamp: 2026-03-02T06:16:00Z

## Evidence

- timestamp: 2026-03-02T06:05:00Z
  checked: adapter.py stream_text_capture -- how status flows from Classifier to SSE event
  found: "The Classifier agent decides the status value when calling file_capture. The adapter reads status from the file_capture call args (merged with result). If status is 'misunderstood', the adapter emits a MISUNDERSTOOD event (line 255-264). If status is 'classified', it emits CLASSIFIED (line 278-296). The adapter has ZERO decision logic about whether a capture is misunderstood -- it is purely a relay."
  implication: "The Classifier's Foundry instructions are the sole decision-maker. Any change in behavior MUST come from instruction changes."

- timestamp: 2026-03-02T06:08:00Z
  checked: Phase 11.1 Plan 02 Task 2 -- what Classifier instruction text was prescribed
  found: "The instruction text includes: 'Before classifying, check if the capture contains MULTIPLE distinct intents that belong to DIFFERENT buckets.' and Rule 5: 'When in doubt about whether to split (ambiguous boundary), keep as a single item in the best-fit bucket rather than splitting incorrectly.' The instruction was added AFTER existing classification rules."
  implication: "The 'Before classifying, check if the capture contains MULTIPLE distinct intents' preamble may cause the Classifier to engage in more analysis before making any classification decision. Combined with its existing misunderstood pathway, the Classifier may now interpret 'I need to...' phrasing as needing clarification rather than filing directly. The instruction inadvertently raised the Classifier's threshold for what it considers unambiguous."

- timestamp: 2026-03-02T06:12:00Z
  checked: User report -- "I need to buy dog food" vs "Buy Dog food"
  found: "Conversational phrasing ('I need to buy dog food') failed twice, imperative phrasing ('Buy Dog food') succeeded immediately. Both mean the same thing. The only difference is linguistic style."
  implication: "The Classifier's new multi-intent analysis causes it to second-guess conversational phrasing. 'I need to buy dog food' could theoretically be parsed as a meta-statement about a need rather than a direct action item, while 'Buy Dog food' is unambiguously an action. The Classifier's multi-intent analysis may be causing it to look for hidden intents in conversational phrasing."

- timestamp: 2026-03-02T06:15:00Z
  checked: Voice capture results from UAT
  found: "Test 4 (single-intent voice 'pick up prescription') passed. Test 5 (multi-intent voice) passed. Voice captures use the same Classifier agent and instructions but went through transcription first, which typically produces more direct phrasing."
  implication: "Voice transcription by gpt-4o-transcribe tends to produce clean, imperative-style text (e.g., 'Pick up prescription' not 'I need to pick up my prescription'). This explains why voice captures were unaffected -- the transcribed text matches the style the Classifier handles well."

- timestamp: 2026-03-02T06:18:00Z
  checked: file_capture tool definition (classification.py)
  found: "The file_capture tool accepts status as a string parameter with description: 'Status: classified (confidence >= 0.6), pending (confidence < 0.6), or misunderstood'. The Classifier decides this value. When status='misunderstood', file_capture writes to Inbox only (no bucket container), and the adapter emits MISUNDERSTOOD with a clarification question."
  implication: "The tool definition correctly describes status options but relies on the LLM's judgment. The multi-intent instructions may have introduced enough uncertainty that the Classifier downgrades clear single-intent captures to 'misunderstood' when phrased conversationally."

- timestamp: 2026-03-02T06:22:00Z
  checked: "Same-bucket multi-item test from UAT (test 3: 'buy cake, candles, and a card for the party')"
  found: "This test PASSED -- filed as a single Admin item. This is a more complex input than 'I need to buy dog food' but was handled correctly."
  implication: "The multi-intent instructions work correctly for clearly shopping-related multi-item text. The problem is specifically with conversational single-intent phrasing like 'I need to...'. The Classifier may be over-analyzing the 'I need to' prefix as potentially indicating a different type of intent."

## Resolution

root_cause: |
  The Classifier Foundry agent's multi-intent detection instructions (added in Phase 11.1) cause the Classifier to over-analyze simple single-intent captures with conversational phrasing.

  The instruction "Before classifying, check if the capture contains MULTIPLE distinct intents that belong to DIFFERENT buckets" creates an analysis step that did not exist before. For conversational phrasing like "I need to buy dog food," the Classifier now engages in deeper intent analysis before classifying, and its uncertainty about whether the phrasing contains hidden intents causes it to call file_capture with status="misunderstood" instead of status="classified".

  Key evidence:
  - "I need to buy dog food" (conversational) -> misunderstood twice
  - "Buy Dog food" (imperative) -> classified immediately as Admin
  - "buy cake, candles, and a card for the party" (imperative, multi-item) -> classified correctly
  - Voice captures (transcribed to clean imperative text) -> all passed

  This is NOT a code bug. The adapter, SSE events, mobile client, and file_capture tool all work correctly. The root cause is purely in the Classifier's Foundry portal instructions, which is where the multi-intent analysis rules were added.

  The multi-intent instructions need to be revised to explicitly state that:
  1. Simple action phrases like "I need to [verb]" are single-intent captures and should be filed directly
  2. Multi-intent analysis should only trigger when there are clear conjunction markers ("and also", "plus", "oh and") connecting genuinely different intents
  3. The pre-existing classification behavior should be preserved for all single-intent captures regardless of linguistic style

fix: |
  NOT A CODE FIX. The Classifier Foundry agent instructions need to be revised in the AI Foundry portal.

  Suggested instruction revision -- replace the current multi-intent detection section with:

  ```
  ## Multi-Intent Detection

  After determining the primary bucket for the capture, check if it also contains
  a SECOND distinct intent targeting a DIFFERENT bucket.

  Rules:
  1. MOST captures are single-intent. A capture like "I need to buy dog food" or
     "pick up milk" or "remind me about the dentist" is a single intent -- classify
     it immediately. Do NOT ask for clarification on simple captures.

  2. Multi-intent captures contain explicit conjunction markers connecting different
     types of tasks. Look for: "and also", "plus", "oh and", "and remind me",
     "also need to", or similar bridging phrases.
     Example: "need milk AND ALSO remind me to call the vet"

  3. If all items belong to the SAME bucket, call file_capture ONCE with the full
     text. Do NOT split within a single bucket.
     Example: "buy milk, eggs, and bread" -> single file_capture, bucket="Admin"

  4. If intents span DIFFERENT buckets (identified by conjunction markers), call
     file_capture ONCE PER BUCKET with only the text segment for that intent.
     Preserve the user's exact words. Each segment gets its own title.

  5. When in doubt, classify as a single item. Never ask for clarification just
     because a capture uses conversational phrasing like "I need to" or "I want to".

  6. Conversational phrasing ("I need to buy dog food", "I should call the vet",
     "thinking about a garden shed") is NORMAL for captures. Treat these the same
     as imperative phrasing ("buy dog food", "call the vet", "garden shed idea").
  ```

  Key changes from the current instructions:
  - "After determining the primary bucket" instead of "Before classifying" -- the analysis happens after initial classification, not before it
  - Explicit statement that most captures are single-intent
  - Explicit examples of conversational phrasing that should be filed directly
  - Conjunction markers are explicitly listed as the trigger for multi-intent splitting
  - Rule 5 explicitly says never ask for clarification due to conversational phrasing

verification: |
  After updating the Classifier Foundry instructions:
  1. Send "I need to buy dog food" -> should file directly to Admin with high confidence
  2. Send "pick up milk" -> should file directly to Admin (regression check)
  3. Send "I need milk and also remind me to call the vet" -> should split to Admin + People (multi-intent still works)
  4. Send "buy cake, candles, and a card for the party" -> should file as single Admin item (same-bucket check)
  5. Voice capture with single intent -> should still work

files_changed: []
