from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.adapters.metrics import MetricsSnapshot
from agent.adapters.runtime import (
    ContainerStatus,
    LogEvidence,
    RuntimeErrorDetail,
)
from agent.app.schemas import RecommendationItem
from agent.app.services.evidence_collector import (
    CollectedEvidence,
    HealthEndpointEvidence,
    IncidentContext,
)
from agent.app.services.rule_diagnosis import RuleDiagnosisEngine


def context(
    *,
    target_running: bool = True,
    health_healthy: bool = True,
    dependency_running: bool = True,
    metrics_available: bool = True,
    criticality: str = "high",
) -> IncidentContext:
    target_state = "running" if target_running else "exited"
    dependency_state = "running" if dependency_running else "exited"
    return IncidentContext(
        incident_id=1,
        service_id=1,
        service_name="backend",
        runtime="docker",
        criticality=criticality,
        target_status=ContainerStatus(
            container_name="incidentpilot-demo-backend",
            state=target_state,
            running=target_running,
        ),
        logs=LogEvidence(
            container_name="incidentpilot-demo-backend",
            logs="demo log",
        ),
        health=HealthEndpointEvidence(
            url="http://backend/health",
            available=True,
            healthy=health_healthy,
            status_code=200 if health_healthy else 503,
            latency_ms=1.0,
        ),
        dependencies={
            "postgres": ContainerStatus(
                container_name="incidentpilot-demo-postgres",
                state=dependency_state,
                running=dependency_running,
            )
        },
        metrics=MetricsSnapshot(
            available=metrics_available,
            error=None if metrics_available else "connection refused",
        ),
        evidence_refs=[1, 2, 3, 4],
        evidence_items=[
            CollectedEvidence(1, "container_status", "docker", target_state),
            CollectedEvidence(2, "health_endpoint", "http", "health result"),
            CollectedEvidence(3, "dependency_status", "docker", dependency_state),
            CollectedEvidence(4, "runtime_logs", "docker", "logs collected"),
        ],
    )


def test_fs001_rank_one_is_backend_container_stopped() -> None:
    analysis = RuleDiagnosisEngine().diagnose(
        context(target_running=False, dependency_running=True)
    )

    assert analysis.severity == "high"
    assert analysis.hypotheses[0].rank == 1
    assert analysis.hypotheses[0].cause == "backend_container_stopped"
    assert analysis.hypotheses[0].evidence_refs == ["evidence:1"]
    assert analysis.recommendations[0].action_key == "restart_container"
    assert analysis.recommendations[0].executed is False
    assert analysis.recommendations[0].execution_enabled_in_mvp is False


def test_fs002_rank_one_is_dependency_unavailable() -> None:
    analysis = RuleDiagnosisEngine().diagnose(
        context(
            target_running=True,
            health_healthy=False,
            dependency_running=False,
        )
    )

    assert analysis.severity == "high"
    assert analysis.hypotheses[0].cause == "dependency_unavailable"
    assert {"evidence:2", "evidence:3"} <= set(
        analysis.hypotheses[0].evidence_refs
    )
    assert (
        analysis.recommendations[0].action_key
        == "restore_dependency_service"
    )


def test_running_target_with_healthy_dependencies_is_application_failure() -> None:
    analysis = RuleDiagnosisEngine().diagnose(
        context(
            target_running=True,
            health_healthy=False,
            dependency_running=True,
        )
    )

    assert analysis.hypotheses[0].cause == "application_level_failure"
    assert "evidence:4" in analysis.hypotheses[0].evidence_refs


def test_single_critical_service_outage_is_conservatively_high() -> None:
    analysis = RuleDiagnosisEngine().diagnose(
        context(target_running=False, criticality="critical")
    )

    assert analysis.severity == "high"


def test_prometheus_and_llm_unavailable_add_gaps_without_failing() -> None:
    incident_context = context(metrics_available=False)
    incident_context.logs = LogEvidence(
        container_name="incidentpilot-demo-backend",
        error=RuntimeErrorDetail(
            code="command_failed", message="logs blocked"
        ),
    )

    analysis = RuleDiagnosisEngine().diagnose(
        incident_context, llm_available=False
    )

    assert analysis.llm_status == "unavailable"
    assert len(analysis.evidence_gaps) == 3
    assert any("Prometheus" in gap for gap in analysis.evidence_gaps)
    assert any("rules-only" in gap for gap in analysis.evidence_gaps)


def test_recommendation_schema_rejects_executed_or_enabled() -> None:
    for unsafe_field in (
        "executed",
        "execution_enabled_in_mvp",
    ):
        values = {
            "action_key": "restart_container",
            "title": "Unsafe",
            "rationale": "Test",
            unsafe_field: True,
        }
        with pytest.raises(ValidationError):
            RecommendationItem.model_validate(values)
