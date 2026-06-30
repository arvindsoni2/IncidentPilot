from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.app.config import Settings, load_settings


def test_loads_yaml_and_environment_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "app:\n  port: 9000\nruntime:\n  default: podman\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("INCIDENTPILOT_PORT", "8088")

    settings = load_settings(config_path=config_file)

    assert settings.app.port == 8088
    assert settings.runtime.default == "podman"
    assert settings.safety.read_only is True
    assert settings.safety.allow_remediation is False


@pytest.mark.parametrize(
    "unsafe_override",
    [
        {"read_only": False},
        {"allow_remediation": True},
        {"allow_arbitrary_shell": True},
    ],
)
def test_mvp_safety_invariants_cannot_be_disabled(
    unsafe_override: dict[str, bool],
) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"safety": unsafe_override})
