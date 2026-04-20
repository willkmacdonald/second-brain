---
status: diagnosed
trigger: "Voice capture fallback error on Status screen navigation"
created: 2026-04-11T12:00:00Z
updated: 2026-04-11T12:00:00Z
---

## Current Focus

hypothesis: Two root causes combine -- (1) global useSpeechRecognitionEvent hooks in index.tsx pick up events from investigate.tsx's voice session, and (2) the fallback error handler sends WAV audio with wrong MIME type
test: Trace the event flow from investigate unmount -> capture screen error handler
expecting: Confirming that abortRecognition() on investigate unmount fires error event received by capture screen
next_action: Verify audioFileUri leak path and MIME type mismatch

## Symptoms

expected: No errors when navigating between tabs/screens
actual: Console error "Voice capture fallback error: {"detail":"Unsupported audio format: audio/vnd.wave"}" fires on navigation to Status screen or back from Investigate
errors: Voice capture fallback error: {"detail":"Unsupported audio format: audio/vnd.wave"} at index.tsx:208
reproduction: Navigate to Status screen after using voice in Investigate screen, or navigate back from Investigate
started: After Phase 18 added Investigation Chat screen with voice input

## Eliminated

(none yet)

## Evidence

- timestamp: 2026-04-11T12:00:00Z
  checked: Tab layout structure in _layout.tsx
  found: Tab-based navigation means Capture screen (index.tsx) is NOT unmounted when navigating to Status -- all hooks remain active
  implication: useSpeechRecognitionEvent hooks in index.tsx fire for ALL speech recognition events globally, including those from other screens

- timestamp: 2026-04-11T12:01:00Z
  checked: investigate.tsx cleanup on unmount (line 218-223)
  found: investigate.tsx calls abortRecognition() on unmount, which fires a global speech recognition "error" event
  implication: When user navigates back from investigate, the abort triggers an error event that the capture screen's handler receives

- timestamp: 2026-04-11T12:02:00Z
  checked: index.tsx "audiostart" handler (line 130-132) and "error" handler (line 135-222)
  found: "audiostart" sets audioFileUri globally. "error" handler checks `if (audioFileUri && API_KEY)` and calls sendVoiceCapture. Neither handler distinguishes whether the event came from index.tsx's own recording or investigate.tsx's recording.
  implication: audioFileUri set by investigate screen's voice recording leaks into capture screen's error handler

- timestamp: 2026-04-11T12:03:00Z
  checked: sendVoiceCapture in ag-ui-client.ts (line 308-351)
  found: Hardcodes `type: "audio/m4a"` and `name: "voice-capture.m4a"` in FormData, but expo-speech-recognition persist saves WAV format by default
  implication: RN FormData or server may detect actual file format as audio/vnd.wave, ignoring the hardcoded type

- timestamp: 2026-04-11T12:04:00Z
  checked: Backend ALLOWED_AUDIO_TYPES in capture.py (line 37-40)
  found: Allows audio/wav but NOT audio/vnd.wave
  implication: Even if the file reached the server correctly, audio/vnd.wave would be rejected

## Resolution

root_cause: Two compounding issues cause this error:

1. **Cross-screen event leak (primary):** The capture screen (index.tsx) registers global `useSpeechRecognitionEvent` hooks that receive events from ALL speech recognition sessions, including those initiated by the investigate screen (investigate.tsx). When the investigate screen unmounts after the user navigates back, it calls `abortRecognition()` which fires a global "error" event. The capture screen's error handler at line 135 checks `if (audioFileUri && API_KEY)` -- and `audioFileUri` is non-null because the "audiostart" event from the investigate screen's voice recording was captured by the capture screen's "audiostart" handler at line 130.

2. **MIME type mismatch (secondary):** The `sendVoiceCapture` function hardcodes `type: "audio/m4a"` but the actual file persisted by expo-speech-recognition is WAV format. The backend receives `audio/vnd.wave` as the content type (either from iOS's multipart handling overriding the hardcoded type, or from the server detecting the actual format) and rejects it because `audio/vnd.wave` is not in `ALLOWED_AUDIO_TYPES`.

fix: (pending)
verification: (pending)
files_changed: []
