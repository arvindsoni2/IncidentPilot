"""Ollama-compatible JSON generation provider."""

from __future__ import annotations

import json
from typing import Any

import httpx

from agent.adapters.llm.base import LLMProvider, LLMProviderError


class OllamaLLMProvider(LLMProvider):
    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        timeout_seconds: float = 120,
        max_retries: int = 1,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.client = client

    def generate_json(self, prompt: str) -> dict[str, Any]:
        attempts = self.max_retries + 1
        last_error: Exception | None = None
        client = self.client or httpx.Client(timeout=self.timeout_seconds)
        should_close = self.client is None
        try:
            for attempt in range(1, attempts + 1):
                try:
                    response = client.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": prompt,
                            "stream": False,
                            "format": "json",
                        },
                        timeout=self.timeout_seconds,
                    )
                    response.raise_for_status()
                    envelope = response.json()
                    generated = envelope.get("response")
                    if isinstance(generated, dict):
                        return generated
                    if not isinstance(generated, str):
                        raise ValueError(
                            "Ollama response field is not JSON text"
                        )
                    decoded = json.loads(generated)
                    if not isinstance(decoded, dict):
                        raise ValueError("Generated JSON is not an object")
                    return decoded
                except (
                    httpx.HTTPError,
                    json.JSONDecodeError,
                    ValueError,
                    TypeError,
                ) as error:
                    last_error = error
                    if attempt == attempts:
                        code = (
                            "timeout"
                            if isinstance(error, httpx.TimeoutException)
                            else "invalid_response"
                            if isinstance(
                                error,
                                (json.JSONDecodeError, ValueError, TypeError),
                            )
                            else "provider_unavailable"
                        )
                        raise LLMProviderError(
                            code=code,
                            message=str(error),
                            attempts=attempt,
                        ) from error
        finally:
            if should_close:
                client.close()
        raise LLMProviderError(
            code="provider_unavailable",
            message=str(last_error or "Unknown provider failure"),
            attempts=attempts,
        )
