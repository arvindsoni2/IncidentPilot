"""Read-only evidence collection for incident diagnosis."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from time import perf_counter
from typing import Any, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.adapters.metrics import MetricsSnapshot, PrometheusMetricsAdapter
from agent.adapters.runtime import (
    ContainerMetadata,
    ContainerRuntimeAdapter,
    ContainerStatus,
    LogEvidence,
    create_runtime_adapter,
)
from agent.app.config import Settings
from agent.app.models import DeploymentEvent, Incident, IncidentEvidence, Service
from agent.app.services.persistence import (
    add_evidence,
    resolve_configured_service,
)

RuntimeFactory = Callable[..., ContainerRuntimeAdapter]


@dataclass(frozen=True)
class HealthEndpointEvidence:
    url: str
    available: bool
    healthy: bool
    status_code: int | None
    latency_ms: float
    error: str | None = None


@dataclass(frozen=True)
class CollectedEvidence:
    id: int
    type: str
    source: str
    summary: str
    collected_at: datetime | None = None

    @property
    def ref(self) -> str:
        return f"evidence:{self.id}"


@dataclass
class IncidentContext:
    incident_id: int
    service_id: int
    service_name: str
    runtime: str
    criticality: str
    target_status: ContainerStatus
    logs: LogEvidence
    health: HealthEndpointEvidence | None
    dependencies: dict[str, ContainerStatus] = field(default_factory=dict)
    metadata: ContainerMetadata | None = None
    metrics: MetricsSnapshot | None = None
    deployments: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[int] = field(default_factory=list)
    evidence_items: list[CollectedEvidence] = field(default_factory=list)


class EvidenceCollector:
    def __init__(
        self,
        *,
        settings: Settings,
        session: Session,
        runtime_factory: RuntimeFactory = create_runtime_adapter,
        metrics_adapter: PrometheusMetricsAdapter | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.session = session
        self.runtime_factory = runtime_factory
        self.metrics_adapter = metrics_adapter
        self.http_client = http_client

    def collect(
        self,
        *,
        service_name: str,
        incident_id: int,
    ) -> IncidentContext:
        service = self._resolve_service(service_name)
        incident = self.session.get(Incident, incident_id)
        if incident is None:
            raise ValueError(f"Unknown incident ID: {incident_id}")
        if incident.service_id != service.id:
            raise ValueError("Incident does not belong to the requested service")

        adapter = self.runtime_factory(
            self.settings, service_runtime=service.runtime
        )
        evidence_records: list[IncidentEvidence] = []

        target_status = adapter.get_container_status(service.container_name)
        evidence_records.append(
            self._store(
                incident_id,
                type="container_status",
                source=service.runtime,
                summary=self._status_summary(service.name, target_status),
                payload=asdict(target_status),
            )
        )

        logs = adapter.get_recent_logs(
            service.container_name,
            since_seconds=self.settings.evidence.logs_since_seconds,
            max_bytes=self.settings.evidence.logs_max_bytes,
        )
        logs = self._enforce_log_limit(logs)
        evidence_records.append(
            self._store(
                incident_id,
                type="runtime_logs",
                source=service.runtime,
                summary=(
                    f"Recent logs unavailable: {logs.error.message}"
                    if logs.error
                    else (
                        f"Collected {len(logs.logs.encode('utf-8'))} bytes "
                        f"of recent logs; truncated={logs.truncated}"
                    )
                ),
                payload=asdict(logs),
            )
        )

        health = self._check_health(service.health_url)
        if health is not None:
            evidence_records.append(
                self._store(
                    incident_id,
                    type="health_endpoint",
                    source=health.url,
                    summary=(
                        f"Health endpoint returned HTTP {health.status_code}"
                        if health.available
                        else f"Health endpoint unavailable: {health.error}"
                    ),
                    payload=asdict(health),
                )
            )

        dependencies: dict[str, ContainerStatus] = {}
        for dependency_name in service.dependencies:
            dependency = self._resolve_service(dependency_name)
            dependency_adapter = self.runtime_factory(
                self.settings, service_runtime=dependency.runtime
            )
            dependency_status = dependency_adapter.get_container_status(
                dependency.container_name
            )
            dependencies[dependency_name] = dependency_status
            evidence_records.append(
                self._store(
                    incident_id,
                    type="dependency_status",
                    source=dependency.runtime,
                    summary=self._status_summary(
                        dependency_name, dependency_status
                    ),
                    payload={
                        "dependency": dependency_name,
                        **asdict(dependency_status),
                    },
                )
            )

        metadata = adapter.get_container_metadata(service.container_name)
        evidence_records.append(
            self._store(
                incident_id,
                type="container_metadata",
                source=service.runtime,
                summary=(
                    f"Container metadata unavailable: {metadata.error.message}"
                    if metadata.error
                    else f"Container image is {metadata.image_name or 'unknown'}"
                ),
                payload=asdict(metadata),
            )
        )

        metrics = self._collect_metrics()
        evidence_records.append(
            self._store(
                incident_id,
                type="metrics_snapshot",
                source="prometheus",
                summary=(
                    f"Prometheus metrics unavailable: {metrics.error}"
                    if not metrics.available
                    else f"Collected {len(metrics.samples)} Prometheus queries"
                ),
                payload=asdict(metrics),
            )
        )

        deployments = self._recent_deployments(service.id)
        evidence_records.append(
            self._store(
                incident_id,
                type="deployment_events",
                source="database",
                summary=f"Found {len(deployments)} recent deployment events",
                payload=deployments,
            )
        )

        return IncidentContext(
            incident_id=incident.id,
            service_id=service.id,
            service_name=service.name,
            runtime=service.runtime,
            criticality=service.criticality,
            target_status=target_status,
            logs=logs,
            health=health,
            dependencies=dependencies,
            metadata=metadata,
            metrics=metrics,
            deployments=deployments,
            evidence_refs=[record.id for record in evidence_records],
            evidence_items=[
                CollectedEvidence(
                    id=record.id,
                    type=record.type,
                    source=record.source,
                    summary=record.summary,
                    collected_at=record.collected_at,
                )
                for record in evidence_records
            ],
        )

    def _resolve_service(self, name: str) -> Service:
        return resolve_configured_service(self.session, self.settings, name)

    def _store(
        self,
        incident_id: int,
        *,
        type: str,
        source: str,
        summary: str,
        payload: dict[str, Any] | list[Any],
    ) -> IncidentEvidence:
        return add_evidence(
            self.session,
            incident_id=incident_id,
            type=type,
            source=source,
            summary=summary,
            raw_payload=payload,
        )

    def _check_health(
        self, url: str | None
    ) -> HealthEndpointEvidence | None:
        if not url:
            return None
        client = self.http_client or httpx.Client(
            timeout=self.settings.evidence.health_timeout_seconds
        )
        should_close = self.http_client is None
        started = perf_counter()
        try:
            response = client.get(
                url, timeout=self.settings.evidence.health_timeout_seconds
            )
            latency = round((perf_counter() - started) * 1000, 2)
            return HealthEndpointEvidence(
                url=url,
                available=True,
                healthy=200 <= response.status_code < 400,
                status_code=response.status_code,
                latency_ms=latency,
            )
        except httpx.HTTPError as error:
            return HealthEndpointEvidence(
                url=url,
                available=False,
                healthy=False,
                status_code=None,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                error=str(error),
            )
        finally:
            if should_close:
                client.close()

    def _collect_metrics(self) -> MetricsSnapshot:
        if not self.settings.metrics.enabled:
            return MetricsSnapshot(
                available=False, error="Prometheus collection is disabled"
            )
        adapter = self.metrics_adapter or PrometheusMetricsAdapter(
            base_url=self.settings.metrics.base_url,
            timeout_seconds=self.settings.metrics.timeout_seconds,
        )
        return adapter.query_snapshot(self.settings.metrics.queries)

    def _recent_deployments(
        self, service_id: int, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        records = self.session.scalars(
            select(DeploymentEvent)
            .where(DeploymentEvent.service_id == service_id)
            .order_by(DeploymentEvent.recorded_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": event.id,
                "version": event.version,
                "notes": event.notes,
                "image_name": event.image_name,
                "image_tag": event.image_tag,
                "recorded_at": self._isoformat(event.recorded_at),
            }
            for event in records
        ]

    def _enforce_log_limit(self, logs: LogEvidence) -> LogEvidence:
        """Defensively cap adapter output before persistence or reasoning."""

        if logs.error:
            return logs
        max_bytes = self.settings.evidence.logs_max_bytes
        encoded = logs.logs.encode("utf-8")
        if len(encoded) <= max_bytes:
            return logs
        return replace(
            logs,
            logs=encoded[-max_bytes:].decode("utf-8", errors="ignore"),
            max_bytes=max_bytes,
            truncated=True,
        )

    @staticmethod
    def _isoformat(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _status_summary(name: str, status: ContainerStatus) -> str:
        if status.error:
            return f"{name} status unavailable: {status.error.message}"
        return f"{name} container is {status.state}"
