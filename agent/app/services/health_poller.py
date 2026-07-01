"""Configurable health polling and incident candidate management."""

from __future__ import annotations

import time
from dataclasses import dataclass
from time import perf_counter

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.app.config import Settings
from agent.app.models import HealthCheckResult, Incident, Service
from agent.app.services.incident_lifecycle import mark_incident_resolved
from agent.app.services.persistence import (
    create_incident,
    list_services,
    resolve_configured_service,
)

ACTIVE_INCIDENT_STATUSES = ("new", "analyzing", "diagnosed")


@dataclass(frozen=True)
class PollResult:
    health_check: HealthCheckResult
    incident_id: int | None = None
    resolved_incident_ids: tuple[int, ...] = ()


class HealthPoller:
    def __init__(
        self,
        *,
        settings: Settings,
        session: Session,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.session = session
        self.http_client = http_client

    def configured_services(self) -> list[Service]:
        for configured in self.settings.services:
            if configured.get("enabled", True):
                resolve_configured_service(
                    self.session,
                    self.settings,
                    configured["name"],
                )
        return list_services(self.session, enabled_only=True)

    def check_service(self, service_name: str) -> PollResult:
        service = resolve_configured_service(self.session, self.settings, service_name)
        health_check = self._perform_check(service)
        self.session.add(health_check)
        self.session.commit()
        self.session.refresh(health_check)

        if health_check.status == "healthy":
            resolved = self._auto_resolve_if_recovered(service.id)
            return PollResult(
                health_check=health_check,
                resolved_incident_ids=tuple(resolved),
            )

        if health_check.status == "not_configured":
            return PollResult(health_check=health_check)

        active = self._active_incident(service.id)
        if active is not None:
            return PollResult(
                health_check=health_check,
                incident_id=active.id,
            )
        incident = create_incident(
            self.session,
            service_id=service.id,
            trigger_type="health_poll",
            status="new",
            severity=self._candidate_severity(service),
            summary=(f"Health polling detected {health_check.status} service {service.name}"),
            llm_status="not_requested",
        )
        return PollResult(
            health_check=health_check,
            incident_id=incident.id,
        )

    def run_once(self) -> list[PollResult]:
        return [
            self.check_service(service.name)
            for service in self.configured_services()
            if service.health_url
        ]

    def run_forever(self) -> None:
        services = [service for service in self.configured_services() if service.health_url]
        next_checks = {service.id: 0.0 for service in services}
        while True:
            now = time.monotonic()
            for service in services:
                if now >= next_checks[service.id]:
                    self.check_service(service.name)
                    next_checks[service.id] = now + service.polling_interval_seconds
            time.sleep(1)

    def list_health_checks(self, *, limit: int = 100) -> list[HealthCheckResult]:
        return list(
            self.session.scalars(
                select(HealthCheckResult)
                .order_by(
                    HealthCheckResult.checked_at.desc(),
                    HealthCheckResult.id.desc(),
                )
                .limit(limit)
            )
        )

    def _perform_check(self, service: Service) -> HealthCheckResult:
        if not service.health_url:
            return HealthCheckResult(
                service_id=service.id,
                status="not_configured",
                error="No health_url configured",
            )
        client = self.http_client or httpx.Client(
            timeout=self.settings.evidence.health_timeout_seconds
        )
        should_close = self.http_client is None
        started = perf_counter()
        try:
            response = client.get(
                service.health_url,
                timeout=self.settings.evidence.health_timeout_seconds,
            )
            latency_ms = round((perf_counter() - started) * 1000, 2)
            healthy = 200 <= response.status_code < 400
            return HealthCheckResult(
                service_id=service.id,
                status="healthy" if healthy else "unhealthy",
                http_status_code=response.status_code,
                latency_ms=latency_ms,
                error=None if healthy else f"HTTP {response.status_code}",
            )
        except httpx.HTTPError as error:
            return HealthCheckResult(
                service_id=service.id,
                status="unavailable",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                error=str(error),
            )
        finally:
            if should_close:
                client.close()

    def _active_incident(self, service_id: int) -> Incident | None:
        return self.session.scalar(
            select(Incident)
            .where(
                Incident.service_id == service_id,
                Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
            )
            .order_by(Incident.detected_at.desc(), Incident.id.desc())
            .limit(1)
        )

    def _auto_resolve_if_recovered(self, service_id: int) -> list[int]:
        latest = list(
            self.session.scalars(
                select(HealthCheckResult)
                .where(HealthCheckResult.service_id == service_id)
                .order_by(
                    HealthCheckResult.checked_at.desc(),
                    HealthCheckResult.id.desc(),
                )
                .limit(3)
            )
        )
        if len(latest) < 3 or any(check.status != "healthy" for check in latest):
            return []
        active_incidents = list(
            self.session.scalars(
                select(Incident).where(
                    Incident.service_id == service_id,
                    Incident.status.in_(ACTIVE_INCIDENT_STATUSES),
                )
            )
        )
        for incident in active_incidents:
            mark_incident_resolved(self.session, incident.id)
        return [incident.id for incident in active_incidents]

    @staticmethod
    def _candidate_severity(service: Service) -> str:
        if service.criticality in {"high", "critical"}:
            return "high"
        return "medium"
