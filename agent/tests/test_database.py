from pathlib import Path

from agent.app.config import Settings
from agent.app.database import initialise_database


def test_database_initialises(tmp_path: Path) -> None:
    database_path = tmp_path / "incidentpilot.db"
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{database_path}"}}
    )

    engine = initialise_database(settings)

    assert database_path.exists()
    engine.dispose()
