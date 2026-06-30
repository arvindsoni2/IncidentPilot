"""Persistence operations for services and incident analysis artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from agent.app.config import Settings
from agent.app.models import (
    AgentRun,
    EvalCheckResult,
    EvalRun,
    Hypothesis,
    Incident,
    IncidentEvidence,
    IncidentReport,
    Recommendation,
    Service,
)


def create_service(
    session: Session,
    *,
    name: str,
    container_name: str,
    runtime: str = "docker",
    health_url: str | None = None,
    polling_interval_seconds: int = 30,
    criticality: str = "medium",
    dependencies: list[str] | None = None,
    enabled: bool = True,
) -> Service:
    service = Service(
        name=name,
        container_name=container_name,
        runtime=runtime,
        health_url=health_url,
        polling_interval_seconds=polling_interval_seconds,
        criticality=criticality,
        dependencies=dependencies or [],
        enabled=enabled,
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


def get_service(session: Session, service_id: int) -> Service | None:
    return session.get(Service, service_id)


def get_service_by_name(session: Session, name: str) -> Service | None:
    return session.scalar(select(Service).where(Service.name == name))


def resolve_configured_service(
    session: Session,
    settings: Settings,
    name: str,
) -> Service:
    service = get_service_by_name(session, name)
    configured = next(
        (item for item in settings.services if item.get("name") == name),
        None,
    )
    if service is not None:
        if configured is not None:
            service.container_name = configured.get(
                "container_name", service.container_name
            )
            service.runtime = (
                configured.get("runtime") or settings.runtime.default
            )
            service.health_url = configured.get(
                "health_url", service.health_url
            )
            service.polling_interval_seconds = configured.get(
                "polling_interval_seconds",
                settings.polling.default_interval_seconds,
            )
            service.criticality = configured.get(
                "criticality", service.criticality
            )
            service.dependencies = configured.get(
                "dependencies", service.dependencies
            )
            service.enabled = configured.get("enabled", service.enabled)
            session.commit()
            session.refresh(service)
        return service
    if configured is None:
        raise ValueError(f"Unknown service: {name}")
    return create_service(
        session,
        name=name,
        container_name=configured["container_name"],
        runtime=configured.get("runtime") or settings.runtime.default,
        health_url=configured.get("health_url"),
        polling_interval_seconds=configured.get(
            "polling_interval_seconds",
            settings.polling.default_interval_seconds,
        ),
        criticality=configured.get("criticality", "medium"),
        dependencies=configured.get("dependencies", []),
        enabled=configured.get("enabled", True),
    )


def list_services(
    session: Session, *, enabled_only: bool = False
) -> list[Service]:
    query = select(Service).order_by(Service.name)
    if enabled_only:
        query = query.where(Service.enabled.is_(True))
    return list(session.scalars(query))


def create_incident(
    session: Session,
    *,
    service_id: int,
    trigger_type: str,
    severity: str = "medium",
    status: str = "new",
    summary: str | None = None,
    llm_status: str | None = None,
) -> Incident:
    incident = Incident(
        service_id=service_id,
        trigger_type=trigger_type,
        severity=severity,
        status=status,
        summary=summary,
        llm_status=llm_status,
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident


def add_evidence(
    session: Session,
    *,
    incident_id: int,
    type: str,
    source: str,
    summary: str,
    raw_payload: dict[str, Any] | list[Any] | None = None,
) -> IncidentEvidence:
    evidence = IncidentEvidence(
        incident_id=incident_id,
        type=type,
        source=source,
        summary=summary,
        raw_payload=raw_payload,
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    return evidence


def add_hypotheses(
    session: Session,
    *,
    incident_id: int,
    hypotheses: Iterable[dict[str, Any]],
) -> list[Hypothesis]:
    records = [
        Hypothesis(incident_id=incident_id, **hypothesis)
        for hypothesis in hypotheses
    ]
    session.add_all(records)
    session.commit()
    for record in records:
        session.refresh(record)
    return records


def add_recommendations(
    session: Session,
    *,
    incident_id: int,
    recommendations: Iterable[dict[str, Any]],
) -> list[Recommendation]:
    records: list[Recommendation] = []
    for recommendation in recommendations:
        safe_values = dict(recommendation)
        safe_values["execution_enabled_in_mvp"] = False
        safe_values["executed"] = False
        records.append(
            Recommendation(incident_id=incident_id, **safe_values)
        )
    session.add_all(records)
    session.commit()
    for record in records:
        session.refresh(record)
    return records


def save_report(
    session: Session,
    *,
    incident_id: int,
    markdown: str,
    json_payload: dict[str, Any],
) -> IncidentReport:
    report = IncidentReport(
        incident_id=incident_id,
        markdown=markdown,
        json_payload=json_payload,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def create_agent_run(
    session: Session,
    *,
    incident_id: int,
    workflow_version: str,
    prompt_versions: dict[str, str],
    model: str | None,
) -> AgentRun:
    run = AgentRun(
        incident_id=incident_id,
        workflow_version=workflow_version,
        prompt_versions=prompt_versions,
        model=model,
        status="running",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def finish_agent_run(
    session: Session,
    run: AgentRun,
    *,
    status: str,
    error: str | None = None,
) -> AgentRun:
    run.status = status
    run.error = error
    run.ended_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(run)
    return run


def save_eval_run(
    session: Session,
    *,
    scenario_id: str,
    passed: bool,
    model: str,
    prompt_versions: dict[str, str],
    checks: Iterable[dict[str, Any]],
    output_path: str | None,
) -> EvalRun:
    run = EvalRun(
        scenario_id=scenario_id,
        passed=passed,
        model=model,
        prompt_versions=prompt_versions,
        output_path=output_path,
    )
    run.checks = [EvalCheckResult(**check) for check in checks]
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def list_eval_runs(
    session: Session, *, limit: int = 100
) -> list[EvalRun]:
    query = (
        select(EvalRun)
        .options(selectinload(EvalRun.checks))
        .order_by(EvalRun.started_at.desc())
        .limit(limit)
    )
    return list(session.scalars(query))


def delete_eval_runs_before(
    session: Session, *, cutoff: datetime
) -> int:
    runs = list(
        session.scalars(
            select(EvalRun)
            .options(selectinload(EvalRun.checks))
            .where(EvalRun.completed_at < cutoff)
        )
    )
    for run in runs:
        session.delete(run)
    session.commit()
    return len(runs)


def list_incidents(
    session: Session,
    *,
    status: str | None = None,
) -> list[Incident]:
    query = (
        select(Incident)
        .options(selectinload(Incident.service))
        .order_by(Incident.detected_at.desc())
    )
    if status is not None:
        query = query.where(Incident.status == status)
    return list(session.scalars(query))


def get_incident_detail(
    session: Session, incident_id: int
) -> Incident | None:
    query = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.service),
            selectinload(Incident.evidence),
            selectinload(Incident.hypotheses),
            selectinload(Incident.recommendations),
            selectinload(Incident.reports),
            selectinload(Incident.agent_runs),
        )
    )
    return session.scalar(query)
