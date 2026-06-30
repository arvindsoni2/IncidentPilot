from pathlib import Path

from alembic import command
from sqlalchemy import inspect, text

from agent.app.config import Settings
from agent.app.database import create_database_engine, initialise_database
from agent.app.migrations import (
    BASELINE_REVISION,
    alembic_config,
    upgrade_database,
)


def test_database_initialises(tmp_path: Path) -> None:
    database_path = tmp_path / "incidentpilot.db"
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{database_path}"}}
    )

    engine = initialise_database(settings)

    assert database_path.exists()
    assert {
        "alembic_version",
        "eval_runs",
        "eval_check_results",
    }.issubset(inspect(engine).get_table_names())
    engine.dispose()


def test_migrations_upgrade_and_downgrade(tmp_path: Path) -> None:
    engine = create_database_engine(
        f"sqlite:///{tmp_path / 'migration.db'}"
    )
    upgrade_database(engine)

    with engine.begin() as connection:
        command.downgrade(
            alembic_config(connection), BASELINE_REVISION
        )
        assert "eval_runs" not in inspect(connection).get_table_names()
        command.upgrade(alembic_config(connection), "head")
        assert "eval_runs" in inspect(connection).get_table_names()
    engine.dispose()


def test_unversioned_mvp_database_upgrades_without_data_loss(
    tmp_path: Path,
) -> None:
    engine = create_database_engine(
        f"sqlite:///{tmp_path / 'legacy.db'}"
    )
    with engine.begin() as connection:
        command.upgrade(
            alembic_config(connection), BASELINE_REVISION
        )
        connection.execute(
            text(
                """
                INSERT INTO services (
                    name, runtime, container_name, polling_interval_seconds,
                    criticality, dependencies, enabled, created_at, updated_at
                ) VALUES (
                    'backend', 'docker', 'legacy-backend', 30,
                    'high', '[]', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.exec_driver_sql("DROP TABLE alembic_version")

    upgrade_database(engine)

    with engine.connect() as connection:
        assert connection.scalar(
            text("SELECT container_name FROM services")
        ) == "legacy-backend"
        assert "eval_runs" in inspect(connection).get_table_names()
    engine.dispose()
