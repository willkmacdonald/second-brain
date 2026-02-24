---
status: investigating
trigger: "HITL clarification not triggering on capture screen - ambiguous captures filed with high confidence instead of triggering clarification flow"
created: 2026-02-23T00:00:00Z
updated: 2026-02-23T00:01:00Z
---

## Current Focus

hypothesis: Autonomous mode re-runs the Classifier after request_clarification, and the autonomous prompt "Classify this text and file it." causes the LLM to call classify_and_file on the second turn, overriding the HITL flow
test: Trace the HandoffAgentExecutor._run_agent_and_emit flow for Classifier with no handoff targets in autonomous mode
expecting: After request_clarification, no handoff is found, autonomous mode injects prompt and re-runs, LLM calls classify_and_file
next_action: confirm Classifier has no handoff targets and autonomous mode re-run behavior

## Symptoms

expected: Ambiguous captures like "Had coffee with Mike, he mentioned a new project idea" should trigger HITL clarification flow (low confidence -> clarifying question)
actual: Capture is filed with high confidence, no clarification triggered
errors: none reported
reproduction: submit ambiguous capture on capture screen
started: after Phase 04 implementation

## Eliminated

## Evidence

- timestamp: 2026-02-23T00:00:30Z
  checked: Classifier agent instructions (classifier.py)
  found: Instructions correctly tell Classifier to call request_clarification when confidence < 0.6 (Rule 2), and NOT to call classify_and_file. Examples include low-confidence cases (e.g., 0.55).
  implication: Classifier prompt/instructions are correct -- the LLM should call request_clarification for ambiguous inputs on the FIRST turn.

- timestamp: 2026-02-23T00:00:35Z
  checked: ClassificationTools.request_clarification (classification.py)
  found: Tool correctly creates pending Inbox document (status="pending", filedRecordId=None) and returns "Clarification -> {uuid} | {text}" format. Tool implementation is correct.
  implication: The tool itself works correctly. If called, it would create the right state.

- timestamp: 2026-02-23T00:00:40Z
  checked: Workflow builder in AGUIWorkflowAdapter._create_workflow (workflow.py lines 90-105)
  found: Only add_handoff(orchestrator, [classifier]) is configured. NO handoff FROM Classifier to any agent. Both agents are in autonomous mode. Classifier's autonomous prompt is "Classify this text and file it."
  implication: Classifier has no handoff targets, so after ANY tool call, _is_handoff_requested returns None, and autonomous mode kicks in.

- timestamp: 2026-02-23T00:00:45Z
  checked: HandoffAgentExecutor._run_agent_and_emit (framework _handoff.py lines 362-434)
  found: After agent run completes, checks for handoff. If no handoff and autonomous_mode=True and turns < limit, it injects Message(role="user", text=autonomous_prompt) and recursively calls _run_agent_and_emit. The autonomous prompt for Classifier is "Classify this text and file it."
  implication: CRITICAL -- After Classifier calls request_clarification (first turn), framework finds no handoff, injects "Classify this text and file it." as user message, and re-runs. On the second turn, the LLM sees the autonomous prompt telling it to "classify and file", and will likely call classify_and_file, overriding the HITL flow.

- timestamp: 2026-02-23T00:00:50Z
  checked: HandoffBuilder._resolve_handoffs (framework _handoff.py)
  found: When explicit handoff_config exists (it does, for Orchestrator), only agents WITH entries get handoff configs. Classifier has no entry, so gets empty handoff list. Confirmed: Classifier executor has self._handoff_targets = set() (empty).
  implication: Classifier can never trigger a handoff. Every response triggers autonomous mode re-run.

- timestamp: 2026-02-23T00:00:55Z
  checked: Adapter HITL detection logic (workflow.py lines 232-266)
  found: Adapter scans text in stream for "Clarification -> ..." regex. If found, emits HITL_REQUIRED CustomEvent after stream ends. Detection logic is correct IF the text survives to the stream.
  implication: Even if request_clarification was called on first turn, the autonomous re-run calls classify_and_file. The adapter would see BOTH patterns in the stream. But because clarification detection is prioritized (line 233: "if update.text and detected_clarification is None"), it checks clarification first. However, the classify_and_file "Filed -> ..." output ALSO arrives, meaning the item gets filed to Cosmos DB regardless. The HITL_REQUIRED event might fire, but the item is already filed with a bucket document.

- timestamp: 2026-02-23T00:01:00Z
  checked: Mobile client config (mobile/.env)
  found: EXPO_PUBLIC_API_URL=https://brain.willmacdonald.com (deployed backend). Not localhost.
  implication: Mobile is pointing to the deployed backend, not local dev. Environment config is correct for deployed testing.

## Resolution

root_cause: The Classifier agent runs in autonomous mode with no handoff targets. When it calls request_clarification for a low-confidence input, the framework finds no handoff, so autonomous mode injects "Classify this text and file it." as a synthetic user message and re-runs the Classifier. On the second turn, the LLM sees this prompt and calls classify_and_file, overriding the HITL clarification flow. The item gets filed to Cosmos DB with a bucket document, and the user never sees the clarification question.

The fundamental problem is that autonomous mode and HITL are contradictory: autonomous mode prevents the workflow from stopping/pausing, which is exactly what HITL requires. The workflow was designed this way (per 04-01 decision: "Raw Workflow instead of WorkflowAgent for HITL resume") but the autonomous_mode configuration was never updated to account for HITL.

fix: The Classifier should NOT be in autonomous mode when it needs to support HITL. Two possible approaches:
  1. Remove the Classifier from the autonomous_mode agents list, so after request_clarification the workflow emits request_info (pauses) instead of re-running.
  2. Keep autonomous mode but give the Classifier a handoff back to itself or a sentinel that signals completion, so the workflow terminates after request_clarification.

The simplest fix is approach 1: only enable autonomous mode for the Orchestrator (which always hands off and never needs to pause), and leave the Classifier in default (human-in-loop) mode. After the Classifier calls request_clarification and produces its response, the framework will call ctx.request_info() which emits a request_info WorkflowEvent. The adapter already handles this (line 243-247) by logging a warning and skipping. But in this new design, when the Classifier's output includes the "Clarification -> ..." text, the adapter WILL detect it and emit HITL_REQUIRED because the stream completes after one Classifier turn.

However, approach 1 has a subtlety: if the Classifier is NOT in autonomous mode, then after calling classify_and_file (high confidence), the framework will also emit request_info, pausing for user input. The adapter currently skips request_info events and lets the stream end, which works. But we need to verify that the workflow still completes normally for high-confidence cases.

Actually, the cleaner fix is: keep both agents in autonomous mode, but change the Classifier's autonomous prompt so it does NOT instruct re-classification. Instead, the prompt should say something like "You have already classified or requested clarification. Do not take any further action." -- but this is fragile (LLM prompt compliance).

The most robust fix is to remove the Classifier from autonomous mode. After the Classifier calls a tool (classify_and_file or request_clarification), it produces a response. With autonomous mode off, the framework calls ctx.request_info() (asking for user input). Since this is the terminal agent in the pipeline, the workflow effectively pauses. The adapter's _stream_updates already handles this: the stream ends, it checks for detected_clarification or detected_confidence, and emits HITL_REQUIRED if appropriate. For high-confidence cases, the "Filed -> ..." text is detected, no HITL needed, stream ends normally with RUN_FINISHED.

verification:
files_changed: []
