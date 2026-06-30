"""Versioned database upgrade helpers."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine

BASELINE_REVISION = "0001_mvp_baseline"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade_database(engine: Engine) -> None:
    """Upgrade fresh databases and safely adopt unversioned MVP databases."""

    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        if "services" in tables and "alembic_version" not in tables:
            command.stamp(alembic_config(connection), BASELINE_REVISION)
        command.upgrade(alembic_config(connection), "head")
