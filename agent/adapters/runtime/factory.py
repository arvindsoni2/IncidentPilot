"""Runtime adapter selection."""

from agent.adapters.runtime.base import ContainerRuntimeAdapter
from agent.adapters.runtime.docker_adapter import DockerRuntimeAdapter
from agent.adapters.runtime.podman_adapter import PodmanRuntimeAdapter
from agent.app.config import Settings


def create_runtime_adapter(
    settings: Settings,
    *,
    service_runtime: str | None = None,
) -> ContainerRuntimeAdapter:
    runtime = (service_runtime or settings.runtime.default).lower()
    timeout = settings.runtime.command_timeout_seconds
    if runtime == "docker":
        return DockerRuntimeAdapter(timeout_seconds=timeout)
    if runtime == "podman":
        return PodmanRuntimeAdapter(timeout_seconds=timeout)
    raise ValueError(f"Unsupported container runtime: {runtime}")
