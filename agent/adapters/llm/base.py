"""Language-model provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMProviderError(Exception):
    code: str
    message: str
    attempts: int

    def __str__(self) -> str:
        return self.message


class LLMProvider(ABC):
    """Providers transform a text prompt into JSON; they receive no tools."""

    @abstractmethod
    def generate_json(self, prompt: str) -> dict[str, Any]:
        """Return decoded JSON or raise a structured provider error."""
