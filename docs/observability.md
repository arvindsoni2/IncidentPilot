# IncidentPilot Observability

IncidentPilot uses container runtime evidence as its primary operational source.
Prometheus metrics supplement that evidence; they are not required for an
incident analysis to complete.

## Start the stack

Docker:

```bash
docker compose -f infra/compose.yaml up -d --build
```

Podman:

```bash
podman compose -f infra/compose.yaml up -d --build
```

## Prometheus

Open <http://127.0.0.1:9090>.

Prometheus scrapes the demo backend at `backend:8000/metrics`. Useful queries:

```promql
up{job="demo-backend"}
sum by (status) (rate(demo_backend_http_requests_total[5m]))
sum(rate(demo_backend_http_requests_total{status=~"5.."}[5m]))
```

## Grafana

Open <http://127.0.0.1:3001> and sign in with the demo-only credentials:

- Username: `admin`
- Password: `incidentpilot-demo-only`

The provisioned **IncidentPilot Demo** dashboard shows:

- whether Prometheus can scrape the backend;
- request rate grouped by HTTP status;
- backend 5xx error rate.

The Prometheus datasource and dashboard are provisioned automatically from
`infra/grafana/`.

## Degraded operation

Prometheus is deliberately optional. If it cannot be reached, the evidence
collector records a `metrics_snapshot` item with `available: false` and
continues using:

- Docker or Podman container status;
- runtime logs;
- HTTP health checks;
- dependency status;
- container/image metadata;
- recent deployment events.

The rules engine adds the missing metrics to `evidence_gaps`; it does not fail
or weaken the read-only safety policy.
