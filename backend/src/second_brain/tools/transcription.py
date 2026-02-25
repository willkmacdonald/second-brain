"""Whisper transcription tool for voice capture.

Wraps Azure OpenAI Whisper API with Azure AD authentication.
This function is SYNC — callers should wrap in asyncio.to_thread()
since the OpenAI sync client blocks.
"""

import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    deployment_name: str,
    endpoint: str,
) -> str:
    """Transcribe audio bytes using Azure OpenAI Whisper.

    Args:
        audio_bytes: Raw audio file bytes.
        filename: Original filename (e.g., "voice-capture.m4a").
        deployment_name: Azure OpenAI Whisper deployment name.
        endpoint: Azure OpenAI endpoint URL.

    Returns:
        Transcribed text string.

    Raises:
        Exception: If transcription fails (caller handles).
    """
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-06-01",
    )

    try:
        result = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=deployment_name,
        )
        logger.info(
            "Transcription complete: %d bytes -> %d chars",
            len(audio_bytes),
            len(result.text),
        )
        return result.text
    except Exception:
        logger.exception("Whisper transcription failed")
        raise
