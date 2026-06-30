import json
import subprocess
from unittest.mock import patch

import pytest

from agent.adapters.runtime.docker_adapter import DockerRuntimeAdapter
from agent.adapters.runtime.factory import create_runtime_adapter
from agent.adapters.runtime.podman_adapter import PodmanRuntimeAdapter
from agent.app.config import Settings


def completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def inspect_payload() -> str:
    return json.dumps(
        [
            {
                "Id": "abc123",
                "Name": "/incidentpilot-demo-backend",
                "Image": "sha256:image",
                "Created": "2026-06-29T10:00:00Z",
                "Config": {
                    "Image": "incidentpilot-demo-backend:local",
                    "Labels": {"devops-agent.monitor": "true"},
                },
                "State": {
                    "Status": "running",
                    "Running": True,
                    "Health": {
                        "Status": "healthy",
                        "FailingStreak": 0,
                        "Log": [{"Output": "ok"}],
                    },
                },
                "NetworkSettings": {"Ports": {"8000/tcp": [{"HostPort": "8001"}]}},
            }
        ]
    )


def test_docker_adapter_parses_status_logs_health_and_metadata() -> None:
    adapter = DockerRuntimeAdapter()
    responses = [
        completed(inspect_payload()),
        completed("first line\nsecond line\n"),
        completed(inspect_payload()),
        completed(inspect_payload()),
    ]

    with patch("subprocess.run", side_effect=responses) as run:
        status = adapter.get_container_status("incidentpilot-demo-backend")
        logs = adapter.get_recent_logs(
            "incidentpilot-demo-backend", since_seconds=900, max_bytes=12
        )
        health = adapter.inspect_healthcheck("incidentpilot-demo-backend")
        metadata = adapter.get_container_metadata("incidentpilot-demo-backend")

    assert status.running is True
    assert status.health == "healthy"
    assert logs.truncated is True
    assert logs.logs.endswith("second line\n")
    assert health.recent_output == "ok"
    assert metadata.image_name == "incidentpilot-demo-backend:local"
    assert run.call_args_list[1].args[0] == [
        "docker",
        "logs",
        "--since",
        "900s",
        "incidentpilot-demo-backend",
    ]
    assert run.call_args_list[1].kwargs["shell"] is False


def test_docker_adapter_parses_json_lines_container_list() -> None:
    output = "\n".join(
        [
            json.dumps(
                {
                    "ID": "one",
                    "Names": "backend",
                    "Image": "backend:local",
                    "State": "running",
                    "Status": "Up",
                    "Labels": "devops-agent.monitor=true",
                }
            ),
            json.dumps(
                {
                    "ID": "two",
                    "Names": "db",
                    "Image": "postgres:17",
                    "State": "exited",
                    "Status": "Exited",
                    "Labels": "",
                }
            ),
        ]
    )
    with patch("subprocess.run", return_value=completed(output)):
        result = DockerRuntimeAdapter().list_containers()

    assert result.error is None
    assert [container.name for container in result.containers] == ["backend", "db"]
    assert result.containers[0].labels == {"devops-agent.monitor": "true"}


def test_podman_adapter_parses_json_array_and_uses_podman_binary() -> None:
    output = json.dumps(
        [
            {
                "Id": "one",
                "Names": ["backend"],
                "Image": "localhost/backend:local",
                "State": "running",
                "Status": "Up",
                "Labels": {"devops-agent.monitor": "true"},
            }
        ]
    )
    with patch("subprocess.run", return_value=completed(output)) as run:
        result = PodmanRuntimeAdapter().list_containers()

    assert result.error is None
    assert result.containers[0].name == "backend"
    assert run.call_args.args[0][0] == "podman"


def test_runtime_failure_and_timeout_are_structured() -> None:
    failure = completed(stderr="daemon unavailable", returncode=1)
    with patch("subprocess.run", return_value=failure):
        failed = DockerRuntimeAdapter().get_container_status("backend")
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(["podman", "ps"], 1),
    ):
        timed_out = PodmanRuntimeAdapter(timeout_seconds=1).list_containers()

    assert failed.error is not None
    assert failed.error.code == "command_failed"
    assert timed_out.error is not None
    assert timed_out.error.code == "timeout"


def test_container_name_cannot_be_treated_as_cli_option() -> None:
    with patch("subprocess.run") as run:
        result = DockerRuntimeAdapter().get_container_status("--format")

    assert result.error is not None
    assert result.error.code == "invalid_container_name"
    run.assert_not_called()


def test_factory_uses_default_and_per_service_override() -> None:
    settings = Settings.model_validate(
        {
            "runtime": {
                "default": "docker",
                "command_timeout_seconds": 7,
            }
        }
    )

    default = create_runtime_adapter(settings)
    override = create_runtime_adapter(settings, service_runtime="podman")

    assert isinstance(default, DockerRuntimeAdapter)
    assert isinstance(override, PodmanRuntimeAdapter)
    assert default.timeout_seconds == 7


def test_factory_rejects_unsupported_runtime() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        create_runtime_adapter(
            Settings(), service_runtime="arbitrary-runtime"
        )
