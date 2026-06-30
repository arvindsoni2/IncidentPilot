from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.adapters.metrics import MetricsSnapshot
from agent.adapters.runtime import (
    ContainerMetadata,
    ContainerStatus,
    LogEvidence,
    RuntimeErrorDetail,
)
from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.models import IncidentEvidence
from agent.app.services.evidence_collector import EvidenceCollector
from agent.app.services.persistence import create_incident, create_service


class FakeRuntimeAdapter:
    def __init__(
        self,
        *,
        statuses: dict[str, ContainerStatus],
        logs: LogEvidence | None = None,
    ) -> None:
        self.statuses = statuses
        self.logs = logs
        self.log_call: tuple[str, int, int] | None = None

    def get_container_status(self, container_name: str) -> ContainerStatus:
        return self.statuses[container_name]

    def get_recent_logs(
        self, container_name: str, since_seconds: int, max_bytes: int
    ) -> LogEvidence:
        self.log_call = (container_name, since_seconds, max_bytes)
        if self.logs:
            return replace(
                self.logs,
                since_seconds=since_seconds,
                max_bytes=max_bytes,
            )
        return LogEvidence(
            container_name=container_name,
            logs="demo logs",
            since_seconds=since_seconds,
            max_bytes=max_bytes,
        )

    def get_container_metadata(
        self, container_name: str
    ) -> ContainerMetadata:
        return ContainerMetadata(
            container_name=container_name,
            container_id="abc",
            image_name="demo:local",
        )


class FakeMetricsAdapter:
    def __init__(self, snapshot: MetricsSnapshot) -> None:
        self.snapshot = snapshot

    def query_snapshot(self, queries):
        return self.snapshot


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{tmp_path / 'evidence.db'}"}}
    )
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def settings() -> Settings:
    return Settings.model_validate(
        {
            "evidence": {
                "logs_since_seconds": 900,
                "logs_max_bytes": 12,
            },
            "metrics": {"enabled": True},
            "services": [
                {
                    "name": "backend",
                    "runtime": "docker",
                    "container_name": "incidentpilot-demo-backend",
                    "health_url": "http://backend/health",
                    "criticality": "high",
                    "dependencies": ["postgres"],
                },
                {
                    "name": "postgres",
                    "runtime": "docker",
                    "container_name": "incidentpilot-demo-postgres",
                    "dependencies": [],
                },
            ],
        }
    )


def build_incident(session: Session) -> int:
    service = create_service(
        session,
        name="backend",
        container_name="incidentpilot-demo-backend",
        runtime="docker",
        health_url="http://backend/health",
        criticality="high",
        dependencies=["postgres"],
    )
    return create_incident(
        session, service_id=service.id, trigger_type="manual"
    ).id


def http_client(status_code: int = 200) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, request=request)
        )
    )


def test_collects_stopped_target_and_limits_logs(session: Session) -> None:
    incident_id = build_incident(session)
    adapter = FakeRuntimeAdapter(
        statuses={
            "incidentpilot-demo-backend": ContainerStatus(
                container_name="incidentpilot-demo-backend",
                state="exited",
                running=False,
            ),
            "incidentpilot-demo-postgres": ContainerStatus(
                container_name="incidentpilot-demo-postgres",
                state="running",
                running=True,
            ),
        },
        logs=LogEvidence(
            container_name="incidentpilot-demo-backend",
            logs="last 12 bytes",
            truncated=True,
        ),
    )
    collector = EvidenceCollector(
        settings=settings(),
        session=session,
        runtime_factory=lambda *args, **kwargs: adapter,
        metrics_adapter=FakeMetricsAdapter(
            MetricsSnapshot(available=True, samples={"up": []})
        ),
        http_client=http_client(),
    )

    context = collector.collect(
        service_name="backend", incident_id=incident_id
    )

    assert context.target_status.running is False
    assert adapter.log_call == (
        "incidentpilot-demo-backend",
        900,
        12,
    )
    assert context.logs.truncated is True
    stored_logs = session.scalar(
        select(IncidentEvidence).where(
            IncidentEvidence.incident_id == incident_id,
            IncidentEvidence.type == "runtime_logs",
        )
    )
    assert stored_logs is not None
    assert len(stored_logs.raw_payload["logs"].encode("utf-8")) <= 12


def test_collects_stopped_dependency(session: Session) -> None:
    incident_id = build_incident(session)
    adapter = FakeRuntimeAdapter(
        statuses={
            "incidentpilot-demo-backend": ContainerStatus(
                container_name="incidentpilot-demo-backend",
                state="running",
                running=True,
            ),
            "incidentpilot-demo-postgres": ContainerStatus(
                container_name="incidentpilot-demo-postgres",
                state="exited",
                running=False,
            ),
        }
    )
    collector = EvidenceCollector(
        settings=settings(),
        session=session,
        runtime_factory=lambda *args, **kwargs: adapter,
        metrics_adapter=FakeMetricsAdapter(
            MetricsSnapshot(available=True)
        ),
        http_client=http_client(503),
    )

    context = collector.collect(
        service_name="backend", incident_id=incident_id
    )

    assert context.health is not None
    assert context.health.healthy is False
    assert context.dependencies["postgres"].running is False
    types = set(
        session.scalars(
            select(IncidentEvidence.type).where(
                IncidentEvidence.incident_id == incident_id
            )
        )
    )
    assert "dependency_status" in types


def test_prometheus_and_logs_unavailable_are_persisted(
    session: Session,
) -> None:
    incident_id = build_incident(session)
    log_error = RuntimeErrorDetail(
        code="command_failed", message="logs unavailable"
    )
    adapter = FakeRuntimeAdapter(
        statuses={
            "incidentpilot-demo-backend": ContainerStatus(
                container_name="incidentpilot-demo-backend",
                state="running",
                running=True,
            ),
            "incidentpilot-demo-postgres": ContainerStatus(
                container_name="incidentpilot-demo-postgres",
                state="running",
                running=True,
            ),
        },
        logs=LogEvidence(
            container_name="incidentpilot-demo-backend",
            error=log_error,
        ),
    )
    collector = EvidenceCollector(
        settings=settings(),
        session=session,
        runtime_factory=lambda *args, **kwargs: adapter,
        metrics_adapter=FakeMetricsAdapter(
            MetricsSnapshot(
                available=False, error="connection refused"
            )
        ),
        http_client=http_client(),
    )

    context = collector.collect(
        service_name="backend", incident_id=incident_id
    )

    assert context.metrics is not None
    assert context.metrics.available is False
    assert context.logs.error == log_error
    records = list(
        session.scalars(
            select(IncidentEvidence).where(
                IncidentEvidence.incident_id == incident_id
            )
        )
    )
    summaries = {record.type: record.summary for record in records}
    assert "connection refused" in summaries["metrics_snapshot"]
    assert "logs unavailable" in summaries["runtime_logs"]
