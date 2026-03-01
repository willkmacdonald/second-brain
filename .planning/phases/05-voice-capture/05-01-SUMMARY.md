---
phase: 05-voice-capture
plan: 01
status: complete
started: 2026-02-25
completed: 2026-02-25
duration: 5 min
---

## What was built

Backend infrastructure for voice capture: Azure Blob Storage manager, Whisper transcription tool, and Perception Agent module.

## Key files

### Created
- `backend/src/second_brain/db/blob_storage.py` — BlobStorageManager with async upload/delete for audio blobs
- `backend/src/second_brain/tools/transcription.py` — `transcribe_audio` wrapping Azure OpenAI Whisper API with Azure AD auth
- `backend/src/second_brain/agents/perception.py` — Perception Agent for chain visibility

### Modified
- `backend/src/second_brain/config.py` — Added `blob_storage_url` and `azure_openai_whisper_deployment_name` settings
- `backend/pyproject.toml` — Added `azure-storage-blob` and `python-multipart` dependencies

## Decisions

- [05-01]: BlobStorageManager follows same singleton pattern as CosmosManager (init in lifespan, store on app.state)
- [05-01]: transcribe_audio is SYNC — callers wrap in asyncio.to_thread() since OpenAI sync client blocks
- [05-01]: Whisper uses cognitiveservices.azure.com scope (not ai.azure.com) for token auth
- [05-01]: Perception Agent is a thin module — actual transcription happens in endpoint with synthetic step events
- [05-01]: Non-fatal blob delete — orphaned blobs are harmless

## Self-Check: PASSED

- [x] BlobStorageManager can upload and delete audio files
- [x] transcribe_audio function wraps Whisper API with proper auth
- [x] Perception Agent exists as a named agent
- [x] Settings includes blob_storage_url and azure_openai_whisper_deployment_name
- [x] Dependencies added to pyproject.toml
- [x] All 43 existing tests pass (no regressions)
- [x] Ruff lint + format clean
