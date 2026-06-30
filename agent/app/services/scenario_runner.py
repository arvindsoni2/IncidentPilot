"""Controlled failure scenarios scoped to the IncidentPilot demo stack."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from agent.app.config import Settings

DEFAULT_COMPOSE_FILE = (
    Path(__file__).resolve().parents[3] / "infra" / "compose.yaml"
)
DEMO_CONTAINER_PREFIX = "incidentpilot-demo-"
ALLOWED_DEMO_TARGETS = {
    "backend": "incidentpilot-demo-backend",
    "postgres": "incidentpilot-demo-postgres",
    "frontend": "incidentpilot-demo-frontend",
}


@dataclass(frozen=True)
class ScenarioDefinition:
    id: str
    description: str
    operation: str
    services: tuple[str, ...]
    container_names: tuple[str, ...]


SCENARIOS: dict[str, ScenarioDefinition] = {
    "FS-001": ScenarioDefinition(
        id="FS-001",
        description="Stop only the demo backend container.",
        operation="stop",
        services=("backend",),
        container_names=("incidentpilot-demo-backend",),
    ),
    "FS-002": ScenarioDefinition(
        id="FS-002",
        description="Stop only the demo PostgreSQL container.",
        operation="stop",
        services=("postgres",),
        container_names=("incidentpilot-demo-postgres",),
    ),
}

RESET_SCENARIO = ScenarioDefinition(
    id="reset",
    description="Restore the demo app to its healthy baseline.",
    operation="up",
    services=("postgres", "backend", "frontend"),
    container_names=(
        "incidentpilot-demo-postgres",
        "incidentpilot-demo-backend",
        "incidentpilot-demo-frontend",
    ),
)


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    command: tuple[str, ...]
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ScenarioRunnerError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class ScenarioRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        compose_file: Path = DEFAULT_COMPOSE_FILE,
        scenarios: Mapping[str, ScenarioDefinition] = SCENARIOS,
        timeout_seconds: int = 120,
    ) -> None:
        self.settings = settings
        self.compose_file = compose_file.resolve()
        self.scenarios = dict(scenarios)
        self.timeout_seconds = timeout_seconds

    def list_scenarios(self) -> list[ScenarioDefinition]:
        return [self.scenarios[key] for key in sorted(self.scenarios)]

    def trigger(self, scenario_id: str) -> ScenarioResult:
        normalized = scenario_id.upper()
        definition = self.scenarios.get(normalized)
        if definition is None:
            raise ScenarioRunnerError(
                code="unknown_scenario",
                message=f"Unknown scenario: {scenario_id}",
            )
        return self._execute(definition)

    def reset(self) -> ScenarioResult:
        return self._execute(RESET_SCENARIO)

    def build_command(
        self, definition: ScenarioDefinition
    ) -> tuple[str, ...]:
        self._validate_definition(definition)
        runtime = self.settings.runtime.default.lower()
        if runtime == "docker":
            prefix = ("docker", "compose")
        elif runtime == "podman":
            prefix = ("podman", "compose")
        else:
            raise ScenarioRunnerError(
                code="unsupported_runtime",
                message=f"Unsupported scenario runtime: {runtime}",
            )
        common = (*prefix, "-f", str(self.compose_file))
        if definition.operation == "stop":
            return (*common, "stop", *definition.services)
        if definition.operation == "up":
            return (*common, "up", "-d", *definition.services)
        raise ScenarioRunnerError(
            code="unsafe_operation",
            message=f"Scenario operation is not allowlisted: {definition.operation}",
        )

    def _execute(self, definition: ScenarioDefinition) -> ScenarioResult:
        command = self.build_command(definition)
        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as error:
            raise ScenarioRunnerError(
                code="timeout",
                message=(
                    f"Scenario {definition.id} exceeded "
                    f"{self.timeout_seconds} seconds"
                ),
            ) from error
        except OSError as error:
            raise ScenarioRunnerError(
                code="runtime_unavailable", message=str(error)
            ) from error
        if completed.returncode != 0:
            raise ScenarioRunnerError(
                code="command_failed",
                message=(
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or f"Scenario {definition.id} failed"
                ),
            )
        return ScenarioResult(
            scenario_id=definition.id,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    @staticmethod
    def _validate_definition(definition: ScenarioDefinition) -> None:
        if len(definition.services) != len(definition.container_names):
            raise ScenarioRunnerError(
                code="unsafe_target",
                message="Scenario service/container mapping is incomplete",
            )
        for service, container_name in zip(
            definition.services,
            definition.container_names,
            strict=True,
        ):
            if not container_name.startswith(DEMO_CONTAINER_PREFIX):
                raise ScenarioRunnerError(
                    code="unsafe_target",
                    message=f"Unsafe container name: {container_name}",
                )
            expected = ALLOWED_DEMO_TARGETS.get(service)
            if expected != container_name:
                raise ScenarioRunnerError(
                    code="unsafe_target",
                    message=(
                        f"Service {service} is not mapped to an allowlisted "
                        "demo container"
                    ),
                )
