# Phase 5: Voice Capture - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Voice recording in the Expo app, transcribed via Azure OpenAI Whisper, then routed through the existing Orchestrator -> Classifier pipeline. User can speak a thought and have it classified and filed automatically. Photo/video capture, transcript editing, and voice playback are separate concerns.

</domain>

<decisions>
## Implementation Decisions

### Recording interaction
- Tap-to-start, tap-to-stop (toggle pattern, not hold-to-record)
- Visual feedback: elapsed timer + pulsing red indicator while recording
- No max recording duration — user decides when to stop
- Send immediately on stop — no preview/playback step before sending

### Transcription feedback
- Reuse existing step-dot pattern: Recording -> Transcribing -> Classifying -> Filed
- Show only the classification result (e.g., "Filed -> Projects (0.85)"), NOT the transcribed text
- No transcript editing — accept Whisper output as-is for MVP
- Voice captures go through the same HITL flow as text (low-confidence, misunderstood, pending — all identical)

### Capture screen integration
- Voice recording happens on the same capture screen — Voice button switches to recording mode in-place
- Hide text input area during recording — replace with timer/pulsing indicator for focused single-mode capture
- After filing, stay in voice mode (don't reset to text) — supports rapid-fire voice captures
- Inbox shows transcribed text as item content — voice and text captures look identical in the inbox list (no voice badge)

### Failure states
- Mic permission denied: toast notification only ("Mic permission required")
- Very short recordings (< 1 second): discard silently, treat as accidental tap
- Transcription failure (Whisper error, network): toast error + stay in voice mode for immediate retry
- Delete voice recordings after successful transcription — only keep the transcript text, no permanent audio storage

### Claude's Discretion
- Exact pulsing animation style and timer typography
- Minimum recording threshold (exact seconds for "too short")
- Upload progress indication (if any)
- Audio format and quality settings (research recommends AAC/m4a via expo-audio HIGH_QUALITY preset)
- How the Perception Agent integrates into the existing HandoffBuilder/Workflow pattern

</decisions>

<specifics>
## Specific Ideas

- Voice and text captures should be indistinguishable in the inbox — the transcript IS the content, no "voice note" labeling
- The recording experience should feel instant: tap -> speak -> tap -> done. No confirmation dialogs, no previews, no extra steps
- Rapid-fire voice: after one voice capture files, immediately ready to record another (stay in voice mode)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-voice-capture*
*Context gathered: 2026-02-25*
