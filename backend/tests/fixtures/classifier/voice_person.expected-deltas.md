# Expected deltas: classifier/voice_person

Captured: 2026-05-09 18:20 UTC
Trace ID: 7fe92c3b-ca3f-4681-baf2-443bca26eef7
Deployed system: brain.willmacdonald.com (RC, agent-framework-azure-ai==1.0.0rc2)

## Same (RC == GA contract)

- SSE event types and ORDER must match: STEP_START (Processing), STEP_END (Processing), CLASSIFIED, COMPLETE
- SSE CLASSIFIED bucket: "People" (confidence 0.9)
- Span attributes: capture.trace_id present on all spans

## Allowed-different (RC != GA, not a regression)

- Timestamps, server IDs, span Names per SPAN-NAME-MAPPING.md
- Transcription text (model-dependent)
- Confidence value may vary

## D-07b notes (classifier-specific)

Voice path split per D-07b: in GA, transcription becomes a non-agent operation (or a single-tool sub-agent). The classifier agent then sees plain text. The SSE wire contract from the mobile client's perspective stays the same. Allow span shape to differ around transcription -- the transcribe_audio tool may move out of the classifier's tool list entirely.

## Notes

Voice capture from macOS TTS audio "Birthday dinner with mom on Saturday at 7pm" classified as People. Audio uploaded as m4a format with explicit content type audio/m4a.
