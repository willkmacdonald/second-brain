"""Unit tests for TranscriptionTools (transcribe_audio).

Tests use mocked AsyncAzureOpenAI and BlobClient. No real Azure calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from second_brain.tools.transcription import TranscriptionTools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transcription_tools() -> (
    tuple[TranscriptionTools, MagicMock, MagicMock, MagicMock]
):
    """Create a TranscriptionTools instance with all mocks.

    Returns:
        Tuple of (tools, openai_client, blob_manager, credential).
    """
    openai_client = MagicMock()
    openai_client.audio = MagicMock()
    openai_client.audio.transcriptions = MagicMock()
    openai_client.audio.transcriptions.create = AsyncMock()

    blob_manager = MagicMock()
    credential = MagicMock()

    tools = TranscriptionTools(
        openai_client=openai_client,
        blob_manager=blob_manager,
        credential=credential,
        deployment_name="gpt-4o-transcribe",
    )
    return tools, openai_client, blob_manager, credential


# ---------------------------------------------------------------------------
# Tests: transcribe_audio
# ---------------------------------------------------------------------------


@patch("second_brain.tools.transcription.BlobClient")
async def test_transcribe_audio_success(
    mock_blob_client_cls: MagicMock,
) -> None:
    """Successful transcription returns transcript text string."""
    tools, openai_client, _, _ = _make_transcription_tools()

    # Mock blob download
    mock_blob_client = MagicMock()
    mock_downloader = MagicMock()
    mock_downloader.readall = AsyncMock(return_value=b"fake-audio-bytes")
    mock_blob_client.download_blob = AsyncMock(
        return_value=mock_downloader
    )
    mock_blob_client.close = AsyncMock()
    mock_blob_client_cls.from_blob_url.return_value = mock_blob_client

    # Mock transcription result
    mock_result = MagicMock()
    mock_result.text = "Pick up prescription at Walgreens"
    openai_client.audio.transcriptions.create = AsyncMock(
        return_value=mock_result
    )

    result = await tools.transcribe_audio(
        blob_url=(
            "https://storage.blob.core.windows.net"
            "/voice/recording.m4a"
        ),
    )

    assert result == "Pick up prescription at Walgreens"

    # Verify the transcription was called with the correct model
    openai_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = (
        openai_client.audio.transcriptions.create.call_args
    )
    assert call_kwargs[1]["model"] == "gpt-4o-transcribe"


@patch("second_brain.tools.transcription.BlobClient")
async def test_transcribe_audio_blob_download_failure(
    mock_blob_client_cls: MagicMock,
) -> None:
    """Blob download failure returns error string (no exception raised)."""
    tools, _, _, _ = _make_transcription_tools()

    # Mock blob download to fail
    mock_blob_client_cls.from_blob_url.side_effect = Exception(
        "Blob not found"
    )

    result = await tools.transcribe_audio(
        blob_url=(
            "https://storage.blob.core.windows.net"
            "/voice/missing.m4a"
        ),
    )

    assert "Transcription error" in result
    assert "Blob not found" in result


@patch("second_brain.tools.transcription.BlobClient")
async def test_transcribe_audio_openai_api_failure(
    mock_blob_client_cls: MagicMock,
) -> None:
    """OpenAI API failure returns error string (no exception raised)."""
    tools, openai_client, _, _ = _make_transcription_tools()

    # Mock blob download succeeds
    mock_blob_client = MagicMock()
    mock_downloader = MagicMock()
    mock_downloader.readall = AsyncMock(return_value=b"fake-audio-bytes")
    mock_blob_client.download_blob = AsyncMock(
        return_value=mock_downloader
    )
    mock_blob_client.close = AsyncMock()
    mock_blob_client_cls.from_blob_url.return_value = mock_blob_client

    # Mock transcription to fail
    openai_client.audio.transcriptions.create = AsyncMock(
        side_effect=Exception("API rate limit")
    )

    result = await tools.transcribe_audio(
        blob_url=(
            "https://storage.blob.core.windows.net"
            "/voice/recording.m4a"
        ),
    )

    assert "Transcription error" in result
    assert "API rate limit" in result
