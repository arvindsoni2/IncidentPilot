import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from agent.app.config import Settings
from agent.app.services.scenario_runner import (
    ScenarioDefinition,
    ScenarioRunner,
    ScenarioRunnerError,
)
from agent.cli.main import app


def settings(runtime: str = "docker") -> Settings:
    return Settings.model_validate({"runtime": {"default": runtime}})


def completed() -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="done",
        stderr="",
    )


def test_trigger_builds_exact_fixed_docker_command(
    tmp_path: Path,
) -> None:
    compose_file = tmp_path / "compose.yaml"
    compose_file.touch()
    runner = ScenarioRunner(
        settings=settings(),
        compose_file=compose_file,
    )

    with patch("subprocess.run", return_value=completed()) as run:
        result = runner.trigger("FS-001")

    assert result.command == (
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "stop",
        "backend",
    )
    assert run.call_args.args[0] == list(result.command)
    assert run.call_args.kwargs["shell"] is False


def test_podman_reset_builds_fixed_up_command(tmp_path: Path) -> None:
    compose_file = tmp_path / "compose.yaml"
    compose_file.touch()
    runner = ScenarioRunner(
        settings=settings("podman"),
        compose_file=compose_file,
    )

    with patch("subprocess.run", return_value=completed()):
        result = runner.reset()

    assert result.command == (
        "podman",
        "compose",
        "-f",
        str(compose_file),
        "up",
        "-d",
        "postgres",
        "backend",
        "frontend",
    )


def test_unknown_scenario_is_rejected_without_subprocess() -> None:
    runner = ScenarioRunner(settings=settings())

    with patch("subprocess.run") as run:
        with pytest.raises(
            ScenarioRunnerError, match="Unknown scenario"
        ):
            runner.trigger("FS-999")

    run.assert_not_called()


@pytest.mark.parametrize(
    ("service", "container_name"),
    [
        ("backend", "production-backend"),
        ("backend", "incidentpilot-demo-postgres"),
        ("production", "incidentpilot-demo-production"),
    ],
)
def test_unsafe_container_mapping_is_rejected(
    service: str,
    container_name: str,
) -> None:
    unsafe = ScenarioDefinition(
        id="FS-UNSAFE",
        description="unsafe",
        operation="stop",
        services=(service,),
        container_names=(container_name,),
    )
    runner = ScenarioRunner(
        settings=settings(), scenarios={"FS-UNSAFE": unsafe}
    )

    with patch("subprocess.run") as run:
        with pytest.raises(ScenarioRunnerError, match="Unsafe|allowlisted"):
            runner.trigger("FS-UNSAFE")

    run.assert_not_called()


def test_cli_lists_scenarios_and_reset_is_available() -> None:
    runner = CliRunner()

    listed = runner.invoke(app, ["scenarios", "list"])
    help_result = runner.invoke(app, ["scenarios", "--help"])

    assert listed.exit_code == 0
    assert "FS-001" in listed.stdout
    assert "FS-002" in listed.stdout
    assert help_result.exit_code == 0
    assert "reset" in help_result.stdout
