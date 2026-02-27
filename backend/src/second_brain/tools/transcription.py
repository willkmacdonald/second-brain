"""Transcription tool for the Classifier agent.

TranscriptionTools wraps gpt-4o-transcribe via AsyncAzureOpenAI to convert
voice recordings into text. The Classifier agent calls transcribe_audio
first, reads the transcript, then calls file_capture to classify and file it.
"""

import logging
from typing import Annotated

from agent_framework import tool
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobClient
from openai import AsyncAzureOpenAI
from pydantic import Field

from second_brain.db.blob_storage import BlobStorageManager

logger = logging.getLogger(__name__)


class TranscriptionTools:
    """Transcription tools bound to an AsyncAzureOpenAI client.

    Uses gpt-4o-transcribe for audio-to-text conversion. Audio is downloaded
    from Azure Blob Storage before being sent to the transcription API.

    Usage:
        tools = TranscriptionTools(
            openai_client, blob_manager, credential, "gpt-4o-transcribe"
        )
        agent = client.create_agent(
            tools=[tools.transcribe_audio],
        )
    """

    def __init__(
        self,
        openai_client: AsyncAzureOpenAI,
        blob_manager: BlobStorageManager,
        credential: DefaultAzureCredential,
        deployment_name: str,
    ) -> None:
        """Store the OpenAI client, blob manager, credential, and deployment name."""
        self._openai = openai_client
        self._blob_manager = blob_manager
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

    @tool(approval_mode="never_require")
    async def transcribe_audio(
        self,
        blob_url: Annotated[
            str,
            Field(
                description=(
                    "Azure Blob Storage URL of the voice "
                    "recording to transcribe"
                )
            ),
        ],
    ) -> str:
        """Transcribe a voice recording to text using gpt-4o-transcribe.

        Downloads audio from Blob Storage, sends to Azure OpenAI Audio API,
        and returns the transcript text. The Classifier agent should read the
        returned transcript, then call file_capture to classify and file it.
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
            return f"Transcription error: {exc}"
