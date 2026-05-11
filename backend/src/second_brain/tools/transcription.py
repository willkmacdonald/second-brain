"""Transcription helper for the voice capture path.

TranscriptionTools wraps gpt-4o-transcribe via AsyncAzureOpenAI to convert
voice recordings into text.

Phase 24 GA migration (D-01..D-04 + F-11): ``transcribe_audio`` is NO LONGER
registered as a Classifier Agent tool. The on-device SFSpeechRecognizer
(shipped Phase 12.5) is the primary voice path; the backend transcription
helper is a rare cloud fallback only. The voice path now splits at the API
layer: ``api/capture.py`` direct-calls ``transcribe_audio`` to produce text,
then routes the transcribed text through the text-only classifier path. The
Classifier Agent registers only ``file_capture``; ``tool_choice='required'``
is unambiguous because exactly one tool is registered.
"""

import logging

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobClient
from openai import AsyncAzureOpenAI

logger = logging.getLogger(__name__)


class TranscriptionTools:
    """Audio-to-text helper bound to an AsyncAzureOpenAI client.

    Uses gpt-4o-transcribe for audio-to-text conversion. Audio is downloaded
    from Azure Blob Storage before being sent to the transcription API.

    Direct helper called from api/capture.py voice handler. NOT registered as
    an agent tool (see Phase 24 D-04 voice path split). The Classifier Agent
    sees only the resulting transcript text.

    Usage:
        transcription_tools = TranscriptionTools(
            openai_client, credential, "gpt-4o-transcribe"
        )
        transcript = await transcription_tools.transcribe_audio(blob_url)
    """

    def __init__(
        self,
        openai_client: AsyncAzureOpenAI,
        credential: DefaultAzureCredential,
        deployment_name: str,
    ) -> None:
        """Store the OpenAI client, credential, and deployment name."""
        self._openai = openai_client
        self._credential = credential
        self._deployment_name = deployment_name

    async def _download_blob(self, blob_url: str) -> bytes:
        """Download audio bytes from Azure Blob Storage.

        Uses the app's DefaultAzureCredential for authentication.
        """
        blob_client = BlobClient.from_blob_url(blob_url, credential=self._credential)
        try:
            downloader = await blob_client.download_blob()
            return await downloader.readall()
        finally:
            await blob_client.close()

    async def transcribe_audio(self, blob_url: str) -> str:
        """Transcribe a voice recording to text using gpt-4o-transcribe.

        Direct helper called from api/capture.py voice handler. NOT registered
        as an agent tool (see Phase 24 D-04 voice path split). Downloads audio
        from Blob Storage, sends to Azure OpenAI Audio API, and returns the
        transcript text. The voice handler then routes the transcript through
        the text-only classifier path.
        """
        try:
            audio_bytes = await self._download_blob(blob_url)

            result = await self._openai.audio.transcriptions.create(
                model=self._deployment_name,
                file=("recording.m4a", audio_bytes, "audio/m4a"),
            )
            return result.text
        except Exception as exc:
            logger.warning("transcribe_audio failed: %s", exc)
            return "Transcription failed. Please try again."
