# Deferred Items - Phase 12.5

## Pre-existing Test Failures (Out of Scope)

1. **test_admin_handoff.py::test_calls_admin_agent_with_enriched_text** - Test expects "AVAILABLE DESTINATIONS:" header but routing context format was changed to "DESTINATIONS:" in Phase 12.3.1. Test needs updating.

2. **test_transcription.py::test_transcribe_audio_success** - TypeError in transcription test mock. Pre-existing, unrelated to Phase 12.5.
