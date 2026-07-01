from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from agent.app.config import Settings
from agent.app.database import (
    create_session_factory,
    initialise_database,
)
from agent.app.services.persistence import (
    add_evidence,
    add_hypotheses,
    add_recommendations,
    create_incident,
    create_service,
    get_incident_detail,
    get_service,
    get_service_by_name,
    list_incidents,
    list_services,
    save_report,
)


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{tmp_path / 'test.db'}"}}
    )
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def test_database_initializes_all_core_tables(tmp_path: Path) -> None:
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{tmp_path / 'schema.db'}"}}
    )
    engine = initialise_database(settings)

    assert set(inspect(engine).get_table_names()) == {
        "agent_runs",
        "alembic_version",
        "deployment_events",
        "eval_check_results",
        "eval_runs",
            "health_check_results",
            "healthy_snapshots",
        "hypotheses",
        "incident_evidence",
        "incident_reports",
        "incidents",
        "recommendations",
        "services",
    }
    engine.dispose()


def test_service_can_be_created_and_queried(session: Session) -> None:
    created = create_service(
        session,
        name="backend",
        container_name="incidentpilot-backend",
        runtime="podman",
        dependencies=["postgres"],
    )

    assert get_service(session, created.id) == created
    assert get_service_by_name(session, "backend") == created
    assert list_services(session) == [created]
    assert created.dependencies == ["postgres"]


def test_incident_and_analysis_artifacts_can_be_attached(
    session: Session,
) -> None:
    service = create_service(
        session,
        name="backend",
        container_name="incidentpilot-backend",
    )
    incident = create_incident(
        session,
        service_id=service.id,
        trigger_type="manual",
        severity="high",
        summary="Backend unavailable",
    )
    evidence = add_evidence(
        session,
        incident_id=incident.id,
        type="container_status",
        source="docker",
        summary="Container is stopped",
        raw_payload={"running": False},
    )
    hypotheses = add_hypotheses(
        session,
        incident_id=incident.id,
        hypotheses=[
            {
                "rank": 1,
                "cause": "Backend container stopped",
                "confidence": 0.99,
                "evidence_refs": [f"evidence:{evidence.id}"],
                "reasoning": "Runtime reports the target as stopped.",
            }
        ],
    )
    recommendations = add_recommendations(
        session,
        incident_id=incident.id,
        recommendations=[
            {
                "action_key": "restart_container",
                "title": "Restore backend manually",
                "rationale": "The service cannot respond while stopped.",
                "requires_approval": True,
                "allowed_by_policy": False,
                # The service must override unsafe caller-supplied values.
                "execution_enabled_in_mvp": True,
                "executed": True,
            }
        ],
    )
    report = save_report(
        session,
        incident_id=incident.id,
        markdown="# Incident report",
        json_payload={"incident_id": incident.id},
    )

    detail = get_incident_detail(session, incident.id)

    assert detail is not None
    assert list_incidents(session) == [detail]
    assert detail.evidence == [evidence]
    assert detail.hypotheses == hypotheses
    assert detail.recommendations == recommendations
    assert detail.reports == [report]
    assert recommendations[0].execution_enabled_in_mvp is False
    assert recommendations[0].executed is False
