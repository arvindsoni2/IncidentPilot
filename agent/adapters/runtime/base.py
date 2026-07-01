"""Safe, read-only container runtime contracts and CLI implementation."""

from __future__ import annotations

import json
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

CONTAINER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")


@dataclass(frozen=True)
class RuntimeErrorDetail:
    code: str
    message: str
    command: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContainerSummary:
    id: str
    name: str
    image: str
    state: str
    status: str
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ContainerListResult:
    containers: list[ContainerSummary] = field(default_factory=list)
    error: RuntimeErrorDetail | None = None


@dataclass(frozen=True)
class ContainerStatus:
    container_name: str
    state: str = "unknown"
    running: bool = False
    health: str | None = None
    latency_ms: float | None = None
    error: RuntimeErrorDetail | None = None


@dataclass(frozen=True)
class LogEvidence:
    container_name: str
    logs: str = ""
    since_seconds: int = 0
    max_bytes: int = 0
    truncated: bool = False
    error: RuntimeErrorDetail | None = None


@dataclass(frozen=True)
class HealthCheckEvidence:
    container_name: str
    status: str = "not_configured"
    failing_streak: int = 0
    recent_output: str | None = None
    error: RuntimeErrorDetail | None = None


@dataclass(frozen=True)
class ContainerMetadata:
    container_name: str
    container_id: str | None = None
    image_name: str | None = None
    image_id: str | None = None
    created_at: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    ports: dict[str, Any] = field(default_factory=dict)
    restart_count: int = 0
    error: RuntimeErrorDetail | None = None


@dataclass(frozen=True)
class CommandResult:
    stdout: str = ""
    stderr: str = ""
    error: RuntimeErrorDetail | None = None


class ContainerRuntimeAdapter(ABC):
    """Read-only interface used by the rest of IncidentPilot."""

    @abstractmethod
    def list_containers(self) -> ContainerListResult: ...

    @abstractmethod
    def get_container_status(self, container_name: str) -> ContainerStatus: ...

    @abstractmethod
    def get_recent_logs(
        self,
        container_name: str,
        since_seconds: int,
        max_bytes: int,
    ) -> LogEvidence: ...

    @abstractmethod
    def inspect_healthcheck(self, container_name: str) -> HealthCheckEvidence: ...

    @abstractmethod
    def get_container_metadata(self, container_name: str) -> ContainerMetadata: ...


class CliContainerRuntimeAdapter(ContainerRuntimeAdapter):
    """Shared implementation using fixed, argument-list subprocess calls."""

    binary: str

    def __init__(self, *, timeout_seconds: int = 10) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def _run(self, arguments: list[str]) -> CommandResult:
        command = [self.binary, *arguments]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                error=RuntimeErrorDetail(
                    code="timeout",
                    message=(
                        f"{self.binary} did not respond within {self.timeout_seconds} seconds"
                    ),
                    command=tuple(command),
                )
            )
        except OSError as error:
            return CommandResult(
                error=RuntimeErrorDetail(
                    code="runtime_unavailable",
                    message=str(error),
                    command=tuple(command),
                )
            )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            return CommandResult(
                stdout=completed.stdout,
                stderr=completed.stderr,
                error=RuntimeErrorDetail(
                    code="command_failed",
                    message=message or f"{self.binary} exited non-zero",
                    command=tuple(command),
                ),
            )
        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @staticmethod
    def _validate_container_name(container_name: str) -> None:
        if not CONTAINER_NAME_PATTERN.fullmatch(container_name):
            raise ValueError(
                "Container name must contain only letters, numbers, '.', "
                "'_', or '-', and cannot begin with punctuation"
            )

    def _inspect(
        self, container_name: str
    ) -> tuple[dict[str, Any] | None, RuntimeErrorDetail | None]:
        try:
            self._validate_container_name(container_name)
        except ValueError as error:
            return None, RuntimeErrorDetail(code="invalid_container_name", message=str(error))
        result = self._run(["inspect", container_name])
        if result.error:
            return None, result.error
        try:
            payload = json.loads(result.stdout)
            record = payload[0] if isinstance(payload, list) else payload
            if not isinstance(record, dict):
                raise ValueError("inspect output is not an object")
            return record, None
        except (json.JSONDecodeError, IndexError, ValueError) as error:
            return None, RuntimeErrorDetail(
                code="invalid_runtime_output",
                message=f"Could not parse {self.binary} inspect output: {error}",
            )

    def list_containers(self) -> ContainerListResult:
        result = self._run(["ps", "-a", "--format", "json"])
        if result.error:
            return ContainerListResult(error=result.error)
        try:
            records = self._parse_container_list(result.stdout)
            return ContainerListResult(
                containers=[self._container_summary(record) for record in records]
            )
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            return ContainerListResult(
                error=RuntimeErrorDetail(
                    code="invalid_runtime_output",
                    message=f"Could not parse {self.binary} container list: {error}",
                )
            )

    def _parse_container_list(self, output: str) -> list[dict[str, Any]]:
        stripped = output.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            payload = json.loads(stripped)
            if not isinstance(payload, list):
                raise ValueError("container list is not an array")
            return payload
        return [json.loads(line) for line in stripped.splitlines() if line.strip()]

    @staticmethod
    def _normalise_labels(labels: Any) -> dict[str, str]:
        if isinstance(labels, dict):
            return {str(key): str(value) for key, value in labels.items()}
        if not isinstance(labels, str) or not labels:
            return {}
        parsed: dict[str, str] = {}
        for item in labels.split(","):
            key, separator, value = item.partition("=")
            if key:
                parsed[key] = value if separator else ""
        return parsed

    def _container_summary(self, record: dict[str, Any]) -> ContainerSummary:
        names = record.get("Names") or record.get("Name") or ""
        if isinstance(names, list):
            name = str(names[0]) if names else ""
        else:
            name = str(names).lstrip("/")
        return ContainerSummary(
            id=str(record.get("ID") or record.get("Id") or ""),
            name=name,
            image=str(record.get("Image") or ""),
            state=str(record.get("State") or "").lower(),
            status=str(record.get("Status") or ""),
            labels=self._normalise_labels(record.get("Labels")),
        )

    def get_container_status(self, container_name: str) -> ContainerStatus:
        record, error = self._inspect(container_name)
        if error or record is None:
            return ContainerStatus(container_name=container_name, error=error)
        state = record.get("State") or {}
        health = state.get("Health") or {}
        state_name = str(state.get("Status") or "unknown").lower()
        return ContainerStatus(
            container_name=container_name,
            state=state_name,
            running=bool(state.get("Running", state_name == "running")),
            health=health.get("Status"),
        )

    def get_recent_logs(
        self,
        container_name: str,
        since_seconds: int,
        max_bytes: int,
    ) -> LogEvidence:
        if since_seconds < 0 or max_bytes <= 0:
            return LogEvidence(
                container_name=container_name,
                since_seconds=since_seconds,
                max_bytes=max_bytes,
                error=RuntimeErrorDetail(
                    code="invalid_log_limits",
                    message="since_seconds must be non-negative and max_bytes positive",
                ),
            )
        try:
            self._validate_container_name(container_name)
        except ValueError as error:
            return LogEvidence(
                container_name=container_name,
                since_seconds=since_seconds,
                max_bytes=max_bytes,
                error=RuntimeErrorDetail(code="invalid_container_name", message=str(error)),
            )
        result = self._run(["logs", "--since", f"{since_seconds}s", container_name])
        if result.error:
            return LogEvidence(
                container_name=container_name,
                since_seconds=since_seconds,
                max_bytes=max_bytes,
                error=result.error,
            )
        encoded = result.stdout.encode("utf-8")
        truncated = len(encoded) > max_bytes
        if truncated:
            encoded = encoded[-max_bytes:]
        return LogEvidence(
            container_name=container_name,
            logs=encoded.decode("utf-8", errors="replace"),
            since_seconds=since_seconds,
            max_bytes=max_bytes,
            truncated=truncated,
        )

    def inspect_healthcheck(self, container_name: str) -> HealthCheckEvidence:
        record, error = self._inspect(container_name)
        if error or record is None:
            return HealthCheckEvidence(container_name=container_name, error=error)
        health = (record.get("State") or {}).get("Health")
        if not health:
            return HealthCheckEvidence(container_name=container_name)
        log_entries = health.get("Log") or []
        recent_output = None
        if log_entries and isinstance(log_entries[-1], dict):
            recent_output = log_entries[-1].get("Output")
        return HealthCheckEvidence(
            container_name=container_name,
            status=str(health.get("Status") or "unknown"),
            failing_streak=int(health.get("FailingStreak") or 0),
            recent_output=recent_output,
        )

    def get_container_metadata(self, container_name: str) -> ContainerMetadata:
        record, error = self._inspect(container_name)
        if error or record is None:
            return ContainerMetadata(container_name=container_name, error=error)
        config = record.get("Config") or {}
        network = record.get("NetworkSettings") or {}
        return ContainerMetadata(
            container_name=container_name,
            container_id=record.get("Id") or record.get("ID"),
            image_name=config.get("Image"),
            image_id=record.get("Image"),
            created_at=record.get("Created"),
            labels=self._normalise_labels(config.get("Labels")),
            ports=network.get("Ports") or {},
            restart_count=int(record.get("RestartCount") or 0),
        )
