from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.services import (
    HealthPoller,
    close_incident,
    get_incident_detail,
    list_incidents,
    mark_incident_resolved,
)


class SequenceHTTPClient:
    def __init__(self, status_codes: list[int]) -> None:
        self.status_codes = iter(status_codes)

    def get(self, url: str, timeout: float) -> httpx.Response:
        request = httpx.Request("GET", url)
        return httpx.Response(next(self.status_codes), request=request)


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    database_url = f"sqlite:///{tmp_path / 'poller.db'}"
    engine = initialise_database(
        Settings.model_validate({"database": {"url": database_url}})
    )
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def settings(*, interval: int | None = None) -> Settings:
    service: dict[str, object] = {
        "name": "backend",
        "container_name": "incidentpilot-demo-backend",
        "health_url": "http://backend/health",
        "criticality": "high",
    }
    if interval is not None:
        service["polling_interval_seconds"] = interval
    return Settings.model_validate({"services": [service]})


def test_default_and_per_service_polling_intervals(
    session: Session,
) -> None:
    default_poller = HealthPoller(
        settings=settings(),
        session=session,
        http_client=SequenceHTTPClient([200]),
    )
    default_service = default_poller.configured_services()[0]

    assert default_service.polling_interval_seconds == 30

    second_engine = initialise_database(
        Settings.model_validate({"database": {"url": "sqlite:///:memory:"}})
    )
    second_factory = create_session_factory(second_engine)
    with second_factory() as second_session:
        overridden = HealthPoller(
            settings=settings(interval=75),
            session=second_session,
            http_client=SequenceHTTPClient([200]),
        ).configured_services()[0]
        assert overridden.polling_interval_seconds == 75
    second_engine.dispose()


def test_updated_config_refreshes_existing_service_interval(
    session: Session,
) -> None:
    initial = HealthPoller(
        settings=settings(interval=30),
        session=session,
        http_client=SequenceHTTPClient([200]),
    )
    assert initial.configured_services()[0].polling_interval_seconds == 30

    refreshed = HealthPoller(
        settings=settings(interval=90),
        session=session,
        http_client=SequenceHTTPClient([200]),
    )

    assert refreshed.configured_services()[0].polling_interval_seconds == 90


def test_unhealthy_check_creates_one_candidate_and_suppresses_duplicates(
    session: Session,
) -> None:
    poller = HealthPoller(
        settings=settings(),
        session=session,
        http_client=SequenceHTTPClient([503, 503]),
    )

    first = poller.check_service("backend")
    second = poller.check_service("backend")
    incidents = list_incidents(session)

    assert first.health_check.status == "unhealthy"
    assert first.incident_id is not None
    assert second.incident_id == first.incident_id
    assert len(incidents) == 1
    assert incidents[0].trigger_type == "health_poll"


def test_three_consecutive_successes_auto_resolve(
    session: Session,
) -> None:
    poller = HealthPoller(
        settings=settings(),
        session=session,
        http_client=SequenceHTTPClient([503, 200, 200, 200]),
    )
    incident_id = poller.check_service("backend").incident_id
    assert incident_id is not None

    first_success = poller.check_service("backend")
    second_success = poller.check_service("backend")
    third_success = poller.check_service("backend")

    assert first_success.resolved_incident_ids == ()
    assert second_success.resolved_incident_ids == ()
    assert third_success.resolved_incident_ids == (incident_id,)
    incident = get_incident_detail(session, incident_id)
    assert incident is not None
    assert incident.status == "resolved"


def test_manual_resolve_and_close(session: Session) -> None:
    poller = HealthPoller(
        settings=settings(),
        session=session,
        http_client=SequenceHTTPClient([503]),
    )
    incident_id = poller.check_service("backend").incident_id
    assert incident_id is not None

    resolved = mark_incident_resolved(session, incident_id)
    closed = close_incident(session, incident_id)

    assert resolved.resolved_at is not None
    assert closed.status == "closed"
