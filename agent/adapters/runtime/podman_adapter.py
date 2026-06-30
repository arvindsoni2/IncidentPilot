"""Read-only Podman CLI adapter."""

from agent.adapters.runtime.base import CliContainerRuntimeAdapter


class PodmanRuntimeAdapter(CliContainerRuntimeAdapter):
    binary = "podman"
