"""Configuration loading from YAML and environment variables."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8083


class DatabaseConfig(BaseModel):
    url: str = "sqlite:///./incidentpilot.db"


class RuntimeConfig(BaseModel):
    default: str = "docker"
    command_timeout_seconds: int = 10


class PollingConfig(BaseModel):
    default_interval_seconds: int = 30


class EvidenceConfig(BaseModel):
    logs_since_seconds: int = 900
    logs_max_bytes: int = 50_000
    health_timeout_seconds: float = 5.0


class MetricsConfig(BaseModel):
    enabled: bool = True
    base_url: str = "http://127.0.0.1:9090"
    timeout_seconds: float = 5.0
    queries: dict[str, str] = Field(
        default_factory=lambda: {
            "target_up": 'up{job="demo-backend"}',
            "request_rate": "sum(rate(demo_backend_http_requests_total[5m]))",
        }
    )


class EvalsConfig(BaseModel):
    output_directory: str = "data/evals"


class SafetyConfig(BaseModel):
    read_only: Literal[True] = True
    allow_remediation: Literal[False] = False
    allow_arbitrary_shell: Literal[False] = False


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "qwen3:8b"
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: int = 120
    max_retries: int = 1


class Settings(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    evidence: EvidenceConfig = Field(default_factory=EvidenceConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    evals: EvalsConfig = Field(default_factory=EvalsConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    services: list[dict[str, Any]] = Field(default_factory=list)


def _environment_overrides() -> dict[str, Any]:
    values: dict[str, Any] = {}
    mappings = {
        "INCIDENTPILOT_DATABASE_URL": ("database", "url"),
        "INCIDENTPILOT_HOST": ("app", "host"),
        "INCIDENTPILOT_PORT": ("app", "port"),
        "INCIDENTPILOT_DEFAULT_RUNTIME": ("runtime", "default"),
        "LLM_PROVIDER": ("llm", "provider"),
        "LLM_MODEL": ("llm", "model"),
        "LLM_BASE_URL": ("llm", "base_url"),
        "LLM_TIMEOUT_SECONDS": ("llm", "timeout_seconds"),
        "LLM_MAX_RETRIES": ("llm", "max_retries"),
    }
    for variable, (section, key) in mappings.items():
        if variable in os.environ:
            values.setdefault(section, {})[key] = os.environ[variable]
    return values


def _merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(
    config_path: str | Path | None = None,
    env_path: str | Path | None = None,
) -> Settings:
    """Load YAML configuration, then apply environment overrides."""

    load_dotenv(dotenv_path=env_path, override=False)
    selected_path = Path(config_path or os.getenv("INCIDENTPILOT_CONFIG_FILE", "config.yaml"))
    yaml_values: dict[str, Any] = {}
    if selected_path.is_file():
        loaded = yaml.safe_load(selected_path.read_text(encoding="utf-8"))
        if loaded is not None and not isinstance(loaded, dict):
            raise ValueError("Configuration root must be a mapping")
        yaml_values = loaded or {}
    return Settings.model_validate(_merge(yaml_values, _environment_overrides()))
