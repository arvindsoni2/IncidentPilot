from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent.app.config import Settings
from agent.app.services import EvalRunner
from agent.cli.main import app


@pytest.mark.parametrize(
    ("scenario_id", "expected_cause"),
    [
        ("FS-001", "backend_container_stopped"),
        ("FS-002", "dependency_unavailable"),
    ],
)
def test_golden_scenario_passes_all_key_fact_checks(
    tmp_path: Path,
    scenario_id: str,
    expected_cause: str,
) -> None:
    result = EvalRunner(
        settings=Settings(),
        output_directory=tmp_path,
    ).run(scenario_id)[0]

    assert result.passed is True
    checks = {check.name: check for check in result.checks}
    assert checks["schema_valid"].passed is True
    assert checks["rank1_cause_correct"].actual == expected_cause
    assert checks["report_sections_present"].passed is True
    assert checks["no_action_executed"].passed is True
    assert checks["llm_status_recorded"].actual == "unavailable"
    outputs = list(tmp_path.glob(f"{scenario_id.lower()}-*.json"))
    assert len(outputs) == 1
    assert '"passed": true' in outputs[0].read_text(encoding="utf-8")


def test_runner_rejects_unknown_scenario(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported eval scenario"):
        EvalRunner(
            settings=Settings(), output_directory=tmp_path
        ).run("FS-999")


def test_eval_cli_outputs_required_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        app, ["evals", "run", "--scenario", "FS-001"]
    )

    assert result.exit_code == 0
    assert '"scenario_id": "FS-001"' in result.stdout
    assert '"passed": true' in result.stdout
    assert '"checks": [' in result.stdout
    assert '"model":' in result.stdout
    assert '"prompt_versions":' in result.stdout
