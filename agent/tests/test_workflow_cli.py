from pathlib import Path

from typer.testing import CliRunner

from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.services import (
    add_hypotheses,
    add_recommendations,
    create_incident,
    create_service,
    save_report,
)
from agent.cli.main import app


def seed_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "cli-workflow.db"
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{database_path}"}}
    )
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as session:
        service = create_service(
            session, name="backend", container_name="backend"
        )
        incident = create_incident(
            session,
            service_id=service.id,
            trigger_type="manual",
            status="diagnosed",
            severity="high",
            summary="Backend stopped",
        )
        add_hypotheses(
            session,
            incident_id=incident.id,
            hypotheses=[
                {
                    "rank": 1,
                    "cause": "backend_container_stopped",
                    "confidence": 0.99,
                    "evidence_refs": ["evidence:1"],
                    "reasoning": "Runtime evidence.",
                }
            ],
        )
        add_recommendations(
            session,
            incident_id=incident.id,
            recommendations=[
                {
                    "action_key": "restart_container",
                    "title": "Restore manually",
                    "rationale": "Human recovery.",
                }
            ],
        )
        save_report(
            session,
            incident_id=incident.id,
            markdown="# Incident Report\n\nRead-only.",
            json_payload={"incident_id": 1, "executed": False},
        )
    engine.dispose()
    return database_path


def configure_cli(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = seed_database(tmp_path)
    (tmp_path / "config.yaml").write_text(
        f"database:\n  url: sqlite:///{database_path}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INCIDENTPILOT_CONFIG_FILE", raising=False)
    monkeypatch.delenv("INCIDENTPILOT_DATABASE_URL", raising=False)


def test_incident_list_and_show_commands(tmp_path: Path, monkeypatch) -> None:
    configure_cli(tmp_path, monkeypatch)
    runner = CliRunner()

    listed = runner.invoke(app, ["incidents", "list"])
    shown = runner.invoke(app, ["incidents", "show", "INC-001"])

    assert listed.exit_code == 0
    assert "INC-001\tbackend\thigh\tdiagnosed" in listed.stdout
    assert shown.exit_code == 0
    assert '"cause": "backend_container_stopped"' in shown.stdout
    assert '"executed": false' in shown.stdout


def test_report_show_export_and_download_commands(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure_cli(tmp_path, monkeypatch)
    runner = CliRunner()
    destination = tmp_path / "report.md"

    shown = runner.invoke(app, ["reports", "show", "INC-001"])
    exported = runner.invoke(
        app, ["reports", "export-json", "INC-001"]
    )
    downloaded = runner.invoke(
        app,
        [
            "reports",
            "download-markdown",
            "INC-001",
            "--output",
            str(destination),
        ],
    )

    assert shown.exit_code == 0
    assert "# Incident Report" in shown.stdout
    assert exported.exit_code == 0
    assert '"executed": false' in exported.stdout
    assert downloaded.exit_code == 0
    assert destination.read_text(encoding="utf-8").startswith(
        "# Incident Report"
    )
