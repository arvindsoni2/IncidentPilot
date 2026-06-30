from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from agent.adapters.llm import LLMProvider, LLMProviderError
from agent.adapters.metrics import MetricsSnapshot
from agent.adapters.runtime import (
    ContainerMetadata,
    ContainerStatus,
    LogEvidence,
)
from agent.app.config import Settings
from agent.app.database import create_session_factory, initialise_database
from agent.app.services import (
    EvidenceCollector,
    LLMDiagnosisService,
    get_incident_detail,
    list_incidents,
)
from agent.workflows import PlainPythonIncidentWorkflow


class Runtime:
    def __init__(
        self,
        *,
        backend_running: bool,
        postgres_running: bool,
    ) -> None:
        self.statuses = {
            "incidentpilot-demo-backend": ContainerStatus(
                container_name="incidentpilot-demo-backend",
                state="running" if backend_running else "exited",
                running=backend_running,
            ),
            "incidentpilot-demo-postgres": ContainerStatus(
                container_name="incidentpilot-demo-postgres",
                state="running" if postgres_running else "exited",
                running=postgres_running,
            ),
        }

    def get_container_status(self, container_name: str) -> ContainerStatus:
        return self.statuses[container_name]

    def get_recent_logs(
        self, container_name: str, since_seconds: int, max_bytes: int
    ) -> LogEvidence:
        return LogEvidence(
            container_name=container_name,
            logs="runtime evidence",
            since_seconds=since_seconds,
            max_bytes=max_bytes,
        )

    def get_container_metadata(
        self, container_name: str
    ) -> ContainerMetadata:
        return ContainerMetadata(
            container_name=container_name,
            image_name="demo:local",
        )


class Metrics:
    def query_snapshot(self, queries):
        return MetricsSnapshot(available=True, samples={"up": []})


class Provider(LLMProvider):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def generate_json(self, prompt: str) -> dict[str, Any]:
        if self.fail:
            raise LLMProviderError(
                code="timeout", message="LLM unavailable", attempts=2
            )
        context = (
            "dependency_unavailable"
            if "dependency_unavailable" in prompt
            else "backend_container_stopped"
        )
        action = (
            "restore_dependency_service"
            if context == "dependency_unavailable"
            else "restart_container"
        )
        return {
            "summary": f"Validated diagnosis: {context}",
            "hypotheses": [
                {
                    "rank": 1,
                    "cause": context,
                    "confidence": 0.98,
                    "evidence_refs": (
                        ["evidence:3", "evidence:4"]
                        if context == "dependency_unavailable"
                        else ["evidence:1"]
                    ),
                    "reasoning": "Grounded in collected runtime evidence.",
                }
            ],
            "recommendations": [
                {
                    "action_key": action,
                    "title": "Manual recovery",
                    "rationale": "A human should restore the failed service.",
                    "requires_approval": True,
                    "allowed_by_policy": False,
                    "execution_enabled_in_mvp": False,
                    "executed": False,
                }
            ],
            "verification_plan": ["Re-check health manually."],
            "follow_up_actions": ["Document the confirmed cause."],
        }


class FixedHTTP:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def get(self, url: str, timeout: float):
        request = httpx.Request("GET", url)
        return httpx.Response(self.status_code, request=request)


@pytest.fixture()
def session(tmp_path: Path) -> Iterator[Session]:
    settings = Settings.model_validate(
        {"database": {"url": f"sqlite:///{tmp_path / 'workflow.db'}"}}
    )
    engine = initialise_database(settings)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def workflow_settings() -> Settings:
    return Settings.model_validate(
        {
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
                    "criticality": "high",
                    "dependencies": [],
                },
            ]
        }
    )


def build_workflow(
    session: Session,
    *,
    backend_running: bool,
    postgres_running: bool,
    health_status: int,
    llm_fails: bool = False,
) -> PlainPythonIncidentWorkflow:
    settings = workflow_settings()
    runtime = Runtime(
        backend_running=backend_running,
        postgres_running=postgres_running,
    )
    collector = EvidenceCollector(
        settings=settings,
        session=session,
        runtime_factory=lambda *args, **kwargs: runtime,
        metrics_adapter=Metrics(),
        http_client=FixedHTTP(health_status),
    )
    return PlainPythonIncidentWorkflow(
        settings=settings,
        session=session,
        evidence_collector=collector,
        llm_service=LLMDiagnosisService(
            provider=Provider(fail=llm_fails)
        ),
    )


@pytest.mark.parametrize(
    (
        "backend_running",
        "postgres_running",
        "health_status",
        "expected_cause",
    ),
    [
        (False, True, 503, "backend_container_stopped"),
        (True, False, 503, "dependency_unavailable"),
    ],
)
def test_fs_scenarios_end_to_end(
    session: Session,
    backend_running: bool,
    postgres_running: bool,
    health_status: int,
    expected_cause: str,
) -> None:
    result = build_workflow(
        session,
        backend_running=backend_running,
        postgres_running=postgres_running,
        health_status=health_status,
    ).analyze_service("backend", "scenario")

    incident = get_incident_detail(session, result.incident_id)

    assert incident is not None
    assert incident.status == "diagnosed"
    assert incident.hypotheses[0].cause == expected_cause
    assert incident.recommendations[0].executed is False
    assert len(incident.reports) == 1
    assert incident.reports[0].json_payload["service"] == "backend"
    assert incident.reports[0].json_payload["llm_status"] == "available"
    assert incident.agent_runs[0].status == "completed"


def test_rules_only_fallback_end_to_end(session: Session) -> None:
    result = build_workflow(
        session,
        backend_running=False,
        postgres_running=True,
        health_status=503,
        llm_fails=True,
    ).analyze_service("backend")

    incident = get_incident_detail(session, result.incident_id)

    assert result.llm_status == "unavailable"
    assert incident is not None
    assert incident.status == "diagnosed"
    assert incident.llm_status == "unavailable"
    assert incident.reports[0].json_payload["rules_only"] is True


def test_failed_analysis_has_explicit_lifecycle_state(
    session: Session,
) -> None:
    workflow = build_workflow(
        session,
        backend_running=False,
        postgres_running=True,
        health_status=503,
    )

    def fail_collection(**_kwargs):
        raise RuntimeError("runtime disappeared")

    workflow.evidence_collector.collect = fail_collection

    with pytest.raises(RuntimeError, match="runtime disappeared"):
        workflow.analyze_service("backend")

    incidents = list_incidents(session, status="failed")
    assert len(incidents) == 1
    assert incidents[0].summary == "Analysis failed: runtime disappeared"
    detail = get_incident_detail(session, incidents[0].id)
    assert detail is not None
    assert detail.agent_runs[0].status == "failed"
