"""Optional read-only Prometheus query adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class MetricsSnapshot:
    available: bool
    samples: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    error: str | None = None


class PrometheusMetricsAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client

    def query_target_up(
        self, job_name: str = "demo-backend"
    ) -> MetricsSnapshot:
        return self.query_snapshot(
            {"target_up": f'up{{job="{job_name}"}}'}
        )

    def query_request_metrics(
        self,
        metric_name: str = "demo_backend_http_requests_total",
    ) -> MetricsSnapshot:
        return self.query_snapshot(
            {
                "request_rate": f"sum(rate({metric_name}[5m]))",
                "error_rate": (
                    f'sum(rate({metric_name}{{status=~"5.."}}[5m]))'
                ),
            }
        )

    def query_service_snapshot(
        self,
        *,
        job_name: str = "demo-backend",
        metric_name: str = "demo_backend_http_requests_total",
    ) -> MetricsSnapshot:
        return self.query_snapshot(
            {
                "target_up": f'up{{job="{job_name}"}}',
                "request_rate": f"sum(rate({metric_name}[5m]))",
                "error_rate": (
                    f'sum(rate({metric_name}{{status=~"5.."}}[5m]))'
                ),
            }
        )

    def query_snapshot(self, queries: dict[str, str]) -> MetricsSnapshot:
        samples: dict[str, list[dict[str, Any]]] = {}
        client = self.client or httpx.Client(timeout=self.timeout_seconds)
        should_close = self.client is None
        try:
            for name, query in queries.items():
                response = client.get(
                    f"{self.base_url}/api/v1/query",
                    params={"query": query},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("status") != "success":
                    raise ValueError(
                        payload.get("error") or "Prometheus query failed"
                    )
                result = payload.get("data", {}).get("result", [])
                if not isinstance(result, list):
                    raise ValueError("Prometheus result is not a list")
                samples[name] = result
            return MetricsSnapshot(available=True, samples=samples)
        except (httpx.HTTPError, ValueError, TypeError) as error:
            return MetricsSnapshot(available=False, error=str(error))
        finally:
            if should_close:
                client.close()
