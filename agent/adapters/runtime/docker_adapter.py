"""Read-only Docker CLI adapter."""

from agent.adapters.runtime.base import CliContainerRuntimeAdapter


class DockerRuntimeAdapter(CliContainerRuntimeAdapter):
    binary = "docker"
