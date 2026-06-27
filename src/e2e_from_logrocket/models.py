from __future__ import annotations

from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_default_openai_client, set_tracing_disabled

from .config import Settings


def configure_local_llm(settings: Settings) -> OpenAIChatCompletionsModel:
    """Point the Agents SDK at a local OpenAI-compatible server (Ollama/vLLM)."""
    client = AsyncOpenAI(
        base_url=settings.ollama_base_url,
        api_key="ollama",  # required by SDK; ignored by Ollama
    )
    set_default_openai_client(client)
    set_tracing_disabled(True)

    return OpenAIChatCompletionsModel(
        model=settings.ollama_model,
        openai_client=client,
    )
