from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.services import (
    auto_resolve_after_health_successes,
    close_incident,
    create_incident,
    create_service,
    mark_incident_resolved,
)


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{tmp_path / 'lifecycle.db'}"}}
    )
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def incident_id(session: Session) -> int:
    service = create_service(
        session, name="backend", container_name="backend"
    )
    return create_incident(
        session,
        service_id=service.id,
        trigger_type="manual",
        status="diagnosed",
    ).id


def test_manual_resolve(session: Session) -> None:
    incident = mark_incident_resolved(session, incident_id(session))

    assert incident.status == "resolved"
    assert incident.resolved_at is not None


def test_auto_resolve_requires_three_successes(session: Session) -> None:
    target_id = incident_id(session)

    unchanged = auto_resolve_after_health_successes(
        session, target_id, consecutive_successes=2
    )
    assert unchanged.status == "diagnosed"

    resolved = auto_resolve_after_health_successes(
        session, target_id, consecutive_successes=3
    )

    assert resolved.status == "resolved"


def test_close_requires_resolved_incident(session: Session) -> None:
    target_id = incident_id(session)

    with pytest.raises(ValueError, match="resolved"):
        close_incident(session, target_id)

    mark_incident_resolved(session, target_id)
    closed = close_incident(session, target_id)

    assert closed.status == "closed"
    assert closed.closed_at is not None
