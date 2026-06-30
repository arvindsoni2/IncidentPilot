"""SQLAlchemy engine and session setup."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from agent.app.config import Settings


class Base(DeclarativeBase):
    """Base class for IncidentPilot ORM models."""


def create_database_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialise_database(settings: Settings) -> Engine:
    """Create configured tables and return the initialized engine."""

    # Import model registrations before asking SQLAlchemy to create metadata.
    import agent.app.models  # noqa: F401

    engine = create_database_engine(settings.database.url)
    Base.metadata.create_all(engine)
    return engine
