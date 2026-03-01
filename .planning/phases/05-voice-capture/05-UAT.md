---
status: testing
phase: 05-voice-capture
source: 05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-PLAN.md
started: 2026-02-25T18:00:00Z
updated: 2026-02-25T18:00:00Z
---

## Current Test

[paused — resuming after Phase 05.1 migration research]

## Tests

### 1. Voice button switches to recording mode in-place
expected: On the main capture screen, tapping the Voice button switches to voice recording mode in-place (no navigation). Text input is hidden, replaced by a large record button.
result: pass

### 2. Recording starts and shows visual feedback
expected: Tapping the record button starts recording. The button turns red with a pulsing animation, and an elapsed timer (MM:SS) appears above the button.
result: pass

### 3. Recording stops and uploads to backend
expected: Tapping the record button again stops recording. The app uploads the audio and shows step progression dots: Perception -> Orchestrator -> Classifier.
result: issue
reported: "Transcription failed — blob upload crashed with AttributeError: dict has no cache_control. Fixed ContentSettings bug and created voice-recordings container. Redeployed. Awaiting retest."
severity: blocker

### 4. Classification result shown after voice capture
expected: After the agent chain completes, a classification result appears (e.g., "Filed -> Projects (0.85)") as a toast or inline text.
result: [pending]

### 5. Stays in voice mode after filing
expected: After a successful voice capture and classification, the screen stays in voice mode (ready to record again), NOT reset to text mode.
result: [pending]

### 6. Short recordings discarded silently
expected: Tapping record then immediately stopping (< 1 second) discards the recording silently — no upload, no error, no toast.
result: [pending]

### 7. Blob Storage not configured shows graceful error
expected: When Blob Storage is not configured on the backend, tapping Voice and attempting to record shows an error message like "Voice capture not available (Blob Storage not configured)" — the app does not crash.
result: [pending]

## Summary

total: 7
passed: 2
issues: 1
pending: 4
skipped: 0

## Gaps

[none yet]
