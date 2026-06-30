"""Configured LLM provider selection."""

from agent.adapters.llm.base import LLMProvider
from agent.adapters.llm.ollama_adapter import OllamaLLMProvider
from agent.app.config import Settings


class LLMProviderFactory:
    @staticmethod
    def create(settings: Settings) -> LLMProvider:
        provider = settings.llm.provider.lower()
        if provider == "ollama":
            return OllamaLLMProvider(
                model=settings.llm.model,
                base_url=settings.llm.base_url,
                timeout_seconds=settings.llm.timeout_seconds,
                max_retries=settings.llm.max_retries,
            )
        raise ValueError(f"Unsupported LLM provider: {provider}")


def create_llm_provider(settings: Settings) -> LLMProvider:
    return LLMProviderFactory.create(settings)
