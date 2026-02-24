# Phase 5: Voice Capture - Research

**Researched:** 2026-02-24
**Domain:** Audio recording (Expo), transcription (Azure OpenAI Whisper), blob storage, agent wiring
**Confidence:** HIGH

## Summary

Voice capture requires four coordinated capabilities: (1) recording audio on the mobile device, (2) uploading the audio file to the backend, (3) transcribing the audio via Azure OpenAI Whisper, and (4) routing the transcribed text through the existing classification pipeline via a new Perception Agent.

The Expo ecosystem has recently undergone a significant shift: `expo-av` is **deprecated** and will be removed in SDK 55. The replacement is `expo-audio`, which provides a hooks-based API (`useAudioRecorder`, `useAudioRecorderState`) and is the correct library for this project (currently on Expo SDK 54). The recording produces `.m4a` files (AAC codec) by default with `RecordingPresets.HIGH_QUALITY`, which is directly compatible with Whisper's accepted formats.

The architecture decision is: **upload audio through the backend** (not directly to Blob Storage). Voice notes for a personal capture app are small (<25 MB, typically <2 MB for a 1-2 minute voice memo at 128kbps). Uploading through the backend avoids SAS token complexity, keeps the mobile client simple, and lets the Perception Agent handle transcription + blob storage in a single server-side flow. The existing `openai` Python package's `client.audio.transcriptions.create()` handles Whisper transcription with the same `AzureOpenAI` client pattern already used in the project.

**Primary recommendation:** Use `expo-audio` with `useAudioRecorder` on mobile, upload the recorded `.m4a` file as multipart form data to a new backend endpoint, have the Perception Agent transcribe via Whisper and store in Blob Storage, then feed the transcribed text into the existing Orchestrator -> Classifier pipeline.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-03 | Azure Blob Storage configured for media file uploads (voice recordings) | `azure-storage-blob` Python SDK with `DefaultAzureCredential`; container "voice-recordings" partitioned by userId |
| CAPT-03 | User can record a voice note in the Expo app which is transcribed by the Perception Agent via Whisper | `expo-audio` `useAudioRecorder` with `RecordingPresets.HIGH_QUALITY` produces `.m4a` compatible with Whisper; upload as multipart to backend |
| CAPT-04 | User sees transcribed text and classification result after voice capture | Backend streams AG-UI events: transcription step + classification steps; reuse existing SSE/callback pattern |
| ORCH-03 | Orchestrator routes audio input to Perception Agent first, then Classifier Agent | Extend `AGUIWorkflowAdapter` to detect audio input type; add Perception Agent to `HandoffBuilder` participants; Orchestrator instructions updated for audio routing |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `expo-audio` | ~1.1.1 (SDK 54) | Audio recording on mobile | Official Expo library, replaces deprecated `expo-av`; hooks-based API; included in Expo Go |
| `openai` (Python) | >=1.0 | Whisper transcription via Azure OpenAI | Already in project; `client.audio.transcriptions.create()` is the standard Whisper API |
| `azure-storage-blob` | latest | Store voice recordings in Azure Blob Storage | Official Azure SDK; async support; `DefaultAzureCredential` compatible |
| `python-multipart` | latest | Parse multipart file uploads in FastAPI | Required by FastAPI for `UploadFile` parameter support |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `expo-file-system` | ~19.0 | Read recorded file URI for upload | May be needed if `fetch()` from `file://` URI doesn't work on all platforms |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `expo-audio` | `expo-av` | `expo-av` is deprecated, removed in SDK 55 -- do not use |
| Upload through backend | Direct-to-blob with SAS tokens | SAS tokens add complexity; voice notes are small (<2 MB); backend-mediated upload is simpler |
| Azure OpenAI Whisper | Azure Speech batch transcription | Batch transcription is for large files (>25 MB) and batches; overkill for single voice memos |
| `expo-audio` | `@react-native-community/audio` | Not an official Expo package; `expo-audio` is the blessed replacement |

**Installation:**
```bash
# Mobile
npx expo install expo-audio

# Backend
uv pip install azure-storage-blob python-multipart
```

## Architecture Patterns

### Recommended Project Structure

New files for Phase 5:
```
backend/src/second_brain/
├── agents/
│   ├── orchestrator.py      # MODIFY: add audio routing instructions
│   ├── perception.py        # NEW: Perception Agent (Whisper transcription)
│   └── workflow.py          # MODIFY: add Perception to workflow, audio detection
├── tools/
│   └── transcription.py     # NEW: transcribe_audio tool (Whisper + Blob)
├── db/
│   └── blob_storage.py      # NEW: BlobStorageManager singleton
├── config.py                # MODIFY: add blob storage settings + whisper deployment
└── main.py                  # MODIFY: add /api/voice-capture endpoint

mobile/
├── app/
│   └── capture/
│       └── voice.tsx        # NEW: Voice recording screen
├── lib/
│   └── ag-ui-client.ts      # MODIFY: add sendVoiceCapture function
└── app.json                 # MODIFY: add expo-audio plugin for mic permissions
```

### Pattern 1: Upload Through Backend (not direct-to-blob)

**What:** Mobile records audio, uploads as multipart form data to a dedicated backend endpoint, backend handles transcription + blob storage + classification pipeline.

**When to use:** When audio files are small (< 25 MB), single-user system, and you want to keep the mobile client simple.

**Why this pattern:**
1. Voice memos for quick thoughts are typically 10-60 seconds (~200KB-2MB at 128kbps AAC)
2. Whisper's limit is 25 MB -- a 1-minute voice note at HIGH_QUALITY is ~1 MB, nowhere near the limit
3. Direct-to-blob requires SAS token endpoint, CORS configuration, and blob trigger/notification -- significant complexity for no benefit at this scale
4. Backend already has `DefaultAzureCredential` and can handle both Whisper API and Blob Storage calls

**Example flow:**
```
Mobile (expo-audio) -> POST /api/voice-capture (multipart) -> Backend:
  1. Save audio to Blob Storage (archival)
  2. Transcribe via Whisper API
  3. Feed transcribed text through Orchestrator -> Classifier pipeline
  4. Stream AG-UI events back to client (transcription step + classification steps)
```

### Pattern 2: Perception Agent as Tool-Based Agent (not autonomous)

**What:** The Perception Agent is a simple agent with a `transcribe_audio` tool. It receives the audio blob URL, calls Whisper, and returns the transcribed text. The Orchestrator then hands off to the Classifier with the text.

**When to use:** When you want the agent chain to be observable and each step visible in the AG-UI stream.

**Why this pattern:**
1. Consistent with existing architecture (Orchestrator -> Specialist handoff)
2. AG-UI step events fire for Perception ("Transcribing...") and Classifier ("Classifying...")
3. The Perception Agent is lightweight -- it just wraps a Whisper API call

**Alternative considered:** Skip the Perception Agent entirely and transcribe directly in the endpoint before feeding to the pipeline. This is simpler but loses the agent chain visibility (no "Perception" step dot in the UI) and doesn't match the PROJECT.md agent team design.

**Recommendation:** Use the Perception Agent for consistency with the architecture, but keep it minimal. The transcription tool is a single function call, not a complex agent interaction.

### Pattern 3: Audio Upload Endpoint (separate from AG-UI endpoint)

**What:** Create a dedicated `POST /api/voice-capture` endpoint that accepts multipart form data, not JSON. This endpoint handles the audio-specific flow (upload + transcribe) and then feeds into the existing SSE streaming pipeline.

**When to use:** Always for voice capture. The existing `/api/ag-ui` endpoint expects JSON with text messages -- audio requires multipart file upload, which is fundamentally different.

**Example:**
```python
# Source: FastAPI docs + Azure OpenAI Whisper quickstart
@app.post("/api/voice-capture", tags=["Capture"])
async def voice_capture(
    request: Request,
    file: UploadFile = File(...),
) -> StreamingResponse:
    """Handle voice capture: upload, transcribe, classify."""
    # 1. Read audio bytes
    audio_bytes = await file.read()

    # 2. Upload to Blob Storage (archival)
    blob_url = await blob_manager.upload_audio(audio_bytes, file.filename)

    # 3. Transcribe via Whisper
    transcription = await transcribe_audio(audio_bytes, file.filename)

    # 4. Run classification pipeline with transcribed text
    # (reuse existing workflow adapter)
    ...
```

### Anti-Patterns to Avoid

- **Do NOT use `expo-av`:** It is deprecated in SDK 54 and removed in SDK 55. The `expo-audio` library is the replacement.
- **Do NOT stream audio to Whisper:** Azure OpenAI Whisper does NOT support streaming/real-time transcription. It accepts a complete audio file and returns the full transcription. Do not try to stream chunks.
- **Do NOT upload directly to Blob Storage from mobile:** Adds SAS token complexity, CORS configuration, and a notification mechanism to tell the backend the upload is complete. Not worth it for small files.
- **Do NOT create a new OpenAI client for Whisper:** The existing `AzureOpenAI` client (or a similar sync `openai.AzureOpenAI` instance) can call `client.audio.transcriptions.create()`. Reuse the client pattern.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Audio recording | Native audio APIs | `expo-audio` `useAudioRecorder` | Handles iOS/Android differences, permissions, codec selection |
| Audio format conversion | FFmpeg/custom encoder | Record in Whisper-compatible format (`.m4a` AAC) | `RecordingPresets.HIGH_QUALITY` produces `.m4a` which Whisper accepts directly |
| Microphone permissions | Manual native permission code | `expo-audio` config plugin + `AudioModule.requestRecordingPermissionsAsync()` | Config plugin handles `NSMicrophoneUsageDescription` (iOS) and `RECORD_AUDIO` (Android) |
| Speech-to-text | Custom ML model | Azure OpenAI Whisper via `openai` Python SDK | Production-quality, multi-language, maintained |
| Blob storage upload | HTTP PUT to blob URL | `azure-storage-blob` `BlobClient.upload_blob()` | Handles auth, retries, chunking |
| Multipart file parsing | Custom request body parser | FastAPI `UploadFile` + `python-multipart` | FastAPI's built-in file upload support |

**Key insight:** The entire voice capture pipeline is "glue code" connecting well-established libraries. No component requires custom implementation. The engineering challenge is wiring them together correctly, not building any individual piece.

## Common Pitfalls

### Pitfall 1: Recording in Wrong Audio Format
**What goes wrong:** Recording in a format Whisper doesn't support (e.g., `.3gp` on Android with `LOW_QUALITY` preset) and getting transcription errors.
**Why it happens:** `RecordingPresets.LOW_QUALITY` uses `.3gp` format with `amr_nb` codec on Android, which is NOT in Whisper's supported format list.
**How to avoid:** Always use `RecordingPresets.HIGH_QUALITY` which produces `.m4a` (AAC) on both iOS and Android -- directly compatible with Whisper's supported formats (m4a is listed).
**Warning signs:** Whisper API returns "File format errors" or empty transcription.

### Pitfall 2: Missing Audio Mode Configuration
**What goes wrong:** Recording silently fails or doesn't capture audio on iOS because `allowsRecording` is not set.
**Why it happens:** iOS requires `setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true })` before recording. Without this, the recorder may prepare but not capture audio.
**How to avoid:** Call `setAudioModeAsync` in a `useEffect` before any recording attempt. The expo-audio docs show this pattern explicitly.
**Warning signs:** Recording duration shows 0ms, or `.uri` is null after stopping.

### Pitfall 3: Forgetting `prepareToRecordAsync()` Before `record()`
**What goes wrong:** Calling `recorder.record()` without first calling `await recorder.prepareToRecordAsync()` results in no recording or a crash.
**Why it happens:** The recorder must be prepared (setting up codecs, file path) before recording can start. This is a two-step process.
**How to avoid:** Always `await recorder.prepareToRecordAsync()` before `recorder.record()`. The expo-audio docs show this sequence.
**Warning signs:** `isRecording` stays `false` after calling `record()`.

### Pitfall 4: Not Requesting Permissions Before Recording
**What goes wrong:** Recording fails silently or crashes because microphone permission was not requested.
**Why it happens:** Both iOS and Android require runtime permission for microphone access.
**How to avoid:** Check and request permissions in `useEffect` on component mount using `AudioModule.requestRecordingPermissionsAsync()`. Gate the record button on permission status.
**Warning signs:** Permission denied alerts, empty recordings, app crashes on record.

### Pitfall 5: Whisper File Size Limit (25 MB)
**What goes wrong:** Transcription fails for long recordings that exceed 25 MB.
**Why it happens:** Azure OpenAI Whisper has a hard 25 MB file size limit. At 128kbps AAC, 25 MB is roughly 26 minutes of audio.
**How to avoid:** For a quick-capture app, this is unlikely to be hit (typical captures are 10-60 seconds). But add a recording duration limit (e.g., 5 minutes) as a safety guard. Show remaining time in the UI.
**Warning signs:** Whisper API returns 413 or file size error.

### Pitfall 6: Using Synchronous OpenAI Client in FastAPI Route
**What goes wrong:** The Whisper transcription blocks the event loop, preventing concurrent request handling.
**Why it happens:** The `openai.AzureOpenAI` client is synchronous. Calling `client.audio.transcriptions.create()` in an `async def` route blocks the asyncio event loop.
**How to avoid:** Either use `openai.AsyncAzureOpenAI` for async transcription, or use `asyncio.to_thread()` to run the sync call in a thread pool. Given the existing project uses sync `DefaultAzureCredential` for the chat client, `asyncio.to_thread()` wrapping the sync call is the pragmatic approach.
**Warning signs:** Other requests hang while transcription is in progress.

### Pitfall 7: expo-audio Plugin Not in app.json
**What goes wrong:** App builds fail or permissions are not properly declared on iOS/Android.
**Why it happens:** `expo-audio` requires its config plugin in `app.json` to set `NSMicrophoneUsageDescription` (iOS) and `RECORD_AUDIO` (Android).
**How to avoid:** Add the plugin to `app.json` before building: `["expo-audio", { "microphonePermission": "Allow Second Brain to access your microphone for voice capture." }]`
**Warning signs:** Build errors mentioning missing permission descriptions.

## Code Examples

Verified patterns from official sources:

### Recording Audio with expo-audio
```typescript
// Source: https://docs.expo.dev/versions/latest/sdk/audio/ (Recording sounds example)
import { useState, useEffect } from 'react';
import { View, Button, Text, Alert } from 'react-native';
import {
  useAudioRecorder,
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorderState,
} from 'expo-audio';

export default function VoiceCaptureScreen() {
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(audioRecorder);

  useEffect(() => {
    (async () => {
      const status = await AudioModule.requestRecordingPermissionsAsync();
      if (!status.granted) {
        Alert.alert('Permission to access microphone was denied');
      }
      await setAudioModeAsync({
        playsInSilentMode: true,
        allowsRecording: true,
      });
    })();
  }, []);

  const startRecording = async () => {
    await audioRecorder.prepareToRecordAsync();
    audioRecorder.record();
  };

  const stopRecording = async () => {
    await audioRecorder.stop();
    // audioRecorder.uri now contains the file path
    const uri = audioRecorder.uri;
    if (uri) {
      // Upload to backend...
    }
  };

  return (
    <View>
      <Text>Duration: {Math.round(recorderState.durationMillis / 1000)}s</Text>
      <Button
        title={recorderState.isRecording ? 'Stop' : 'Record'}
        onPress={recorderState.isRecording ? stopRecording : startRecording}
      />
    </View>
  );
}
```

### Uploading Audio from React Native to FastAPI
```typescript
// Source: React Native fetch API + FastAPI UploadFile docs
async function uploadAudio(uri: string, apiKey: string): Promise<Response> {
  const formData = new FormData();
  formData.append('file', {
    uri: uri,
    type: 'audio/m4a',
    name: 'voice-capture.m4a',
  } as any);

  return fetch(`${API_BASE_URL}/api/voice-capture`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      // Do NOT set Content-Type -- fetch sets it with boundary automatically
    },
    body: formData,
  });
}
```

### Azure OpenAI Whisper Transcription (Python)
```python
# Source: https://learn.microsoft.com/azure/ai-foundry/openai/whisper-quickstart
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-01",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

result = client.audio.transcriptions.create(
    file=open("voice-capture.m4a", "rb"),
    model="whisper",  # deployment name
)
print(result.text)  # "The transcribed text..."
```

### Azure Blob Storage Upload (Python, async)
```python
# Source: https://learn.microsoft.com/azure/developer/python/sdk/examples/azure-sdk-example-storage-use
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobClient

credential = DefaultAzureCredential()

async with BlobClient(
    account_url="https://mystorageaccount.blob.core.windows.net",
    container_name="voice-recordings",
    blob_name=f"will/{uuid4()}.m4a",
    credential=credential,
) as blob_client:
    await blob_client.upload_blob(audio_bytes, overwrite=True)
```

### FastAPI Voice Capture Endpoint
```python
# Source: FastAPI docs (UploadFile) + project patterns
from fastapi import File, UploadFile

@app.post("/api/voice-capture", tags=["Capture"])
async def voice_capture(
    request: Request,
    file: UploadFile = File(...),
) -> StreamingResponse:
    audio_bytes = await file.read()
    filename = file.filename or "voice-capture.m4a"

    # 1. Upload to Blob Storage
    blob_url = await blob_manager.upload_audio(audio_bytes, filename)

    # 2. Transcribe via Whisper
    import asyncio
    transcription = await asyncio.to_thread(
        transcribe_sync, audio_bytes, filename
    )

    # 3. Run classification pipeline with transcribed text
    thread_id = f"thread-{uuid4()}"
    run_id = f"run-{uuid4()}"
    # ... (reuse existing workflow adapter with transcribed text)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `expo-av` Audio.Recording | `expo-audio` useAudioRecorder | Expo SDK 54 (2025) | expo-av deprecated, removed in SDK 55; must use expo-audio |
| OpenAI Python 0.28.x | OpenAI Python 1.x+ | 2024 | `openai.Audio.transcribe()` -> `client.audio.transcriptions.create()` |
| Connection string for Blob Storage | DefaultAzureCredential | Ongoing | Keyless auth is recommended; project already uses DefaultAzureCredential |

**Deprecated/outdated:**
- `expo-av`: Deprecated in SDK 54, removed in SDK 55. Use `expo-audio` instead.
- `openai` Python 0.28.x: Deprecated. Use 1.x+ with `AzureOpenAI` client class.
- Direct Blob Storage connection strings: Use `DefaultAzureCredential` for keyless auth (already project pattern).

## Open Questions

1. **Whisper deployment name**
   - What we know: Azure OpenAI requires a Whisper model deployment. The deployment name is configured separately from the chat model deployment.
   - What's unclear: Whether Will's Azure OpenAI resource already has a Whisper deployment, and what the deployment name is.
   - Recommendation: Add `azure_openai_whisper_deployment_name` to `Settings` (default: `"whisper"`). If no deployment exists, the planner should include a task to deploy the Whisper model via Azure portal.

2. **Blob Storage account**
   - What we know: INFRA-03 requires Azure Blob Storage configured for voice recordings.
   - What's unclear: Whether a storage account already exists in the Azure subscription.
   - Recommendation: Add `blob_storage_url` to `Settings`. Include Azure CLI commands in plan to create storage account and container if needed.

3. **Voice capture SSE streaming vs REST response**
   - What we know: The existing capture flow uses SSE for streaming step events. Voice capture has an additional "uploading" + "transcribing" phase before classification.
   - What's unclear: Whether to use SSE streaming for the entire voice flow or a two-phase approach (REST upload + SSE classification).
   - Recommendation: Use a single SSE-streamed endpoint for the entire flow. The endpoint receives the multipart upload, then streams step events (Uploading -> Transcribing -> Classifying) as SSE. This matches the existing UX pattern and gives the user real-time feedback during transcription. Use the existing `_stream_sse` helper pattern but add Perception step events.

4. **Multipart + SSE in single request**
   - What we know: The existing SSE endpoints accept JSON POST bodies. Voice capture needs multipart form data for the audio file.
   - What's unclear: Whether a single endpoint can accept multipart form data AND return SSE stream.
   - Recommendation: YES -- FastAPI `StreamingResponse` works regardless of request content type. The endpoint uses `UploadFile` for the request and `StreamingResponse` for the SSE output. This is standard FastAPI behavior.

## Sources

### Primary (HIGH confidence)
- Expo Audio official docs (SDK 54): https://docs.expo.dev/versions/v54.0.0/sdk/audio -- Recording API, permissions, RecordingPresets, hooks
- Expo AV deprecation notice: https://docs.expo.dev/versions/v54.0.0/sdk/audio-av -- "deprecated and replaced by expo-audio"
- Azure OpenAI Whisper quickstart: https://learn.microsoft.com/azure/ai-foundry/openai/whisper-quickstart -- Python code, file formats, size limits
- Azure OpenAI Whisper overview: https://learn.microsoft.com/azure/ai-services/speech-service/whisper-overview -- Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm; 25 MB limit
- Azure Blob Storage Python SDK: https://learn.microsoft.com/azure/developer/python/sdk/examples/azure-sdk-example-storage-use -- Upload patterns with DefaultAzureCredential

### Secondary (MEDIUM confidence)
- Expensify/App issue #80742 (2026-01-28): expo-av removed in Expo 55, confirming expo-audio is mandatory going forward
- expo/expo issue #38061: expo-audio vs expo-av feature parity discussion
- React Native Nerd video (2024-12): Practical expo-audio recording implementation with Supabase upload pattern
- DEV Community article (2026-02-22): Production audio recorder with expo-audio

### Tertiary (LOW confidence)
- expo-azure-blob-storage npm package: Small community package, only 10 stars. Not recommended over direct `fetch()` upload to backend.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - expo-audio is officially documented and verified as the replacement for expo-av; Azure OpenAI Whisper API is well-documented with Python examples; azure-storage-blob is the standard Azure SDK
- Architecture: HIGH - Backend-mediated upload is the simplest pattern for small files; existing codebase patterns (AGUIWorkflowAdapter, SSE streaming) are well-understood from reading the code
- Pitfalls: HIGH - All pitfalls verified from official documentation (format compatibility, permissions, audio mode, file size limits)
- Perception Agent wiring: MEDIUM - Based on understanding the existing HandoffBuilder/Workflow pattern, but the specific wiring of a third agent hasn't been tested

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (30 days -- Expo SDK stable, Azure APIs stable)
