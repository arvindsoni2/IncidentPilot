from __future__ import annotations

import json

import httpx
import pytest

from agent.adapters.llm import (
    LLMProviderError,
    LLMProviderFactory,
    OllamaLLMProvider,
)
from agent.app.config import Settings


def test_ollama_provider_parses_json_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["format"] == "json"
        return httpx.Response(
            200,
            request=request,
            json={"response": json.dumps({"summary": "valid"})},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        model="test-model",
        base_url="http://ollama",
        client=client,
    )

    assert provider.generate_json("prompt") == {"summary": "valid"}
    client.close()


def test_ollama_provider_retries_once_on_timeout() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaLLMProvider(
        model="test-model",
        base_url="http://ollama",
        max_retries=1,
        client=client,
    )

    with pytest.raises(LLMProviderError) as captured:
        provider.generate_json("prompt")

    assert captured.value.code == "timeout"
    assert captured.value.attempts == 2
    assert calls == 2
    client.close()


def test_ollama_invalid_json_is_structured_failure() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, request=request, json={"response": "not-json"}
            )
        )
    )
    provider = OllamaLLMProvider(
        model="test-model",
        base_url="http://ollama",
        max_retries=0,
        client=client,
    )

    with pytest.raises(LLMProviderError) as captured:
        provider.generate_json("prompt")

    assert captured.value.code == "invalid_response"
    client.close()


def test_provider_factory_uses_configured_ollama_settings() -> None:
    settings = Settings.model_validate(
        {
            "llm": {
                "provider": "ollama",
                "model": "qwen-test",
                "base_url": "http://ollama:11434",
                "timeout_seconds": 45,
                "max_retries": 1,
            }
        }
    )

    provider = LLMProviderFactory.create(settings)

    assert isinstance(provider, OllamaLLMProvider)
    assert provider.model == "qwen-test"
    assert provider.timeout_seconds == 45
