from pathlib import Path

from sqlalchemy import create_engine, inspect
from typer.testing import CliRunner

from agent.cli.main import app


def test_db_init_command_creates_database(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "cli.db"
    (tmp_path / "config.yaml").write_text(
        f"database:\n  url: sqlite:///{database_path}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INCIDENTPILOT_DATABASE_URL", raising=False)
    monkeypatch.delenv("INCIDENTPILOT_CONFIG_FILE", raising=False)

    result = CliRunner().invoke(app, ["db", "init"])

    assert result.exit_code == 0
    assert "Database initialized" in result.stdout
    assert database_path.exists()
    engine = create_engine(f"sqlite:///{database_path}")
    assert "incidents" in inspect(engine).get_table_names()
    engine.dispose()
