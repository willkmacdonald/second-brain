"""Perception Agent for voice capture transcription.

The Perception Agent exists for agent chain visibility and architectural
consistency. In practice, transcription happens directly in the voice-capture
endpoint (Whisper needs raw audio bytes, not text), and the endpoint emits
synthetic StepStarted/StepFinished events for "Perception". This agent module
is created for future use and pipeline documentation.
"""

from agent_framework import Agent
from agent_framework.azure import AzureOpenAIChatClient


def create_perception_agent(chat_client: AzureOpenAIChatClient) -> Agent:
    """Create the Perception Agent for audio transcription.

    The Perception Agent is a thin agent that receives transcribed text
    and passes it to the Orchestrator. Its primary purpose is agent chain
    visibility (step dots in UI) and architectural consistency.
    """
    return chat_client.as_agent(
        name="Perception",
        instructions=(
            "You are the Perception Agent. When given audio input, use the "
            "transcribe_audio tool to convert speech to text. Return ONLY "
            "the transcribed text, with no commentary or modification."
        ),
        description="Transcribes audio input to text via Whisper",
    )
