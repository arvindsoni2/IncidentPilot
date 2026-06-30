# IncidentPilot System Design and Architecture

## 1. Architecture Principles

- Local-first, server/cloud portable.
- Safe by default.
- Read-only MVP.
- Runtime adapters isolate Docker/Podman differences.
- Rules establish operational truth; LLM explains and ranks.
- No unrestricted shell access.
- Structured outputs for testing and UI rendering.
- Degraded mode if LLM or Prometheus is unavailable.
- Markdown docs for Codex, HTML guide for human review.

## 2. High-Level Architecture

```text
+-------------------+       +-----------------------+
| Web Dashboard     |       | CLI                   |
| FastAPI/Jinja/HTMX|       | Typer                 |
+---------+---------+       +----------+------------+
          |                            |
          +-------------+--------------+
                        |
                +-------v--------+
                | FastAPI API    |
                | App Service    |
                +-------+--------+
                        |
        +---------------+------------------+
        |                                  |
+-------v--------+                +--------v---------+
| Incident       |                | Health Poller    |
| Workflow       |                | Service          |
+-------+--------+                +--------+---------+
        |                                  |
        +-------------+--------------------+
                      |
        +-------------v------------------------------+
        | Evidence Collection Layer                   |
        | runtime status, logs, health, metrics, deps |
        +----+--------------+---------------+---------+
             |              |               |
+------------v--+   +-------v--------+   +--v--------------+
| Docker Adapter|   | Podman Adapter |   | Prometheus      |
+---------------+   +----------------+   | Metrics Adapter |
                                          +-----------------+

        +---------------------------------------------+
        | Diagnosis Layer                             |
        | deterministic rules + LLM reasoning          |
        +----------------+----------------------------+
                         |
        +----------------v----------------------------+
        | SQLAlchemy Storage                           |
        | SQLite first, PostgreSQL compatible          |
        +----------------+----------------------------+
                         |
        +----------------v----------------------------+
        | Reports, JSON output, incident history       |
        +---------------------------------------------+
```

## 3. Component Responsibilities

### Web Dashboard

Technology: FastAPI + Jinja + HTMX.

Responsibilities:

- Show service health.
- Trigger manual analysis.
- Show incident list and detail.
- Show reports.
- Show read-only settings.
- Use HTMX partial refresh.

### CLI

Technology: Typer.

Responsibilities:

- Trigger analysis.
- List/show incidents.
- Show/export reports.
- Record deployment events.
- Trigger/reset demo scenarios.

### Runtime Adapter Layer

Common interface:

```python
class ContainerRuntimeAdapter:
    def list_containers(self) -> list[ContainerSummary]: ...
    def get_container_status(self, container_name: str) -> ContainerStatus: ...
    def get_recent_logs(self, container_name: str, since_seconds: int, max_bytes: int) -> LogEvidence: ...
    def inspect_healthcheck(self, container_name: str) -> HealthCheckEvidence: ...
    def get_container_metadata(self, container_name: str) -> ContainerMetadata: ...
```

Implementations:

- `DockerRuntimeAdapter`
- `PodmanRuntimeAdapter`

### Evidence Collector

Collects:

- runtime status
- recent logs
- health endpoint result
- dependency statuses
- Prometheus metrics snapshot
- deployment metadata
- image/container metadata

### Rule Diagnosis Engine

Initial rules:

- container stopped
- health endpoint failing
- dependency stopped/unhealthy
- missing evidence
- LLM unavailable
- Prometheus unavailable

### LLM Reasoning Adapter

First provider:

- Ollama-compatible local model.

Config:

```env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=1
```

Future providers:

- OpenAI-compatible API
- Anthropic
- OpenRouter
- local llama.cpp-compatible server

### Incident Workflow

MVP:

```text
observe -> collect evidence -> apply rules -> call LLM -> rank hypotheses -> recommend -> report -> persist
```

Interface:

```python
class IncidentWorkflow:
    def analyze_service(self, service_name: str, trigger: str) -> IncidentAnalysisResult: ...
```

Implementations:

- `PlainPythonIncidentWorkflow` for MVP
- `LangGraphIncidentWorkflow` later

### Storage

SQLAlchemy models with SQLite first and PostgreSQL compatibility.

Entities:

- Service
- HealthCheckResult
- DeploymentEvent
- Incident
- IncidentEvidence
- Hypothesis
- Recommendation
- IncidentReport
- AgentRun
- EvalRun

## 4. Data Model Outline

### Service

- id
- name
- runtime
- container_name
- health_url
- polling_interval_seconds
- criticality
- labels
- enabled
- created_at
- updated_at

### Incident

- id
- service_id
- status
- severity
- trigger_type
- summary
- started_at
- detected_at
- diagnosed_at
- resolved_at
- closed_at
- llm_status

### IncidentEvidence

- id
- incident_id
- type
- source
- summary
- raw_ref
- collected_at

### Hypothesis

- id
- incident_id
- rank
- cause
- confidence
- evidence_refs
- reasoning

### Recommendation

- id
- incident_id
- action_key
- title
- rationale
- requires_approval
- allowed_by_policy
- execution_enabled_in_mvp
- executed

### IncidentReport

- id
- incident_id
- markdown
- json_payload
- created_at

### DeploymentEvent

- id
- service_id
- version
- notes
- image_name
- image_tag
- recorded_at

### AgentRun

- id
- incident_id
- workflow_version
- prompt_versions
- model
- started_at
- ended_at
- status
- error

## 5. Configuration

### `.env`

```env
DATABASE_URL=sqlite:///./data/incidentpilot.db
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=1
HOST=127.0.0.1
PORT=8083
AUTH_ENABLED=false
LOG_LEVEL=INFO
```

### `config.yaml`

```yaml
runtime:
  default: docker
  docker:
    enabled: true
  podman:
    enabled: true

polling:
  default_interval_seconds: 30

evidence:
  logs_since_seconds: 900
  logs_max_bytes: 50000

services:
  backend:
    runtime: docker
    container_name: incidentpilot-backend
    health_url: http://localhost:8000/health
    polling_interval_seconds: 30
    criticality: high
    dependencies:
      - postgres

  postgres:
    runtime: docker
    container_name: incidentpilot-postgres
    health_url: null
    polling_interval_seconds: 30
    criticality: high

safety_policy:
  execution_enabled: false
  actions:
    restart_container:
      allowed: true
      execution_enabled_in_mvp: false
      requires_approval: false
      maximum_attempts: 1
    rollback_last_deployment:
      allowed: true
      execution_enabled_in_mvp: false
      requires_approval: true
    delete_volume:
      allowed: false
      execution_enabled_in_mvp: false
    run_arbitrary_shell:
      allowed: false
      execution_enabled_in_mvp: false
```

## 6. Deployment Architecture

### Local MVP

- FastAPI app runs on localhost.
- SQLite database stored under `./data`.
- Demo app, Prometheus, Grafana run through Compose.
- Ollama runs locally on host or as configured.

### Future Single Server / Cloud VM

- FastAPI app behind reverse proxy.
- Auth enabled.
- PostgreSQL instead of SQLite.
- Prometheus/Grafana persisted volumes.
- Optional Loki and OpenTelemetry Collector.
- Strict runtime socket proxy.

## 7. Safety Architecture

MVP safety rule:

```text
Agent can recommend actions but cannot execute actions.
```

The action catalogue is modelled now to make the future self-healing boundary explicit.

Blocked forever unless explicitly redesigned:

- arbitrary shell
- delete volume
- destructive data operations

Future allowed with limits:

- restart container, max once
- rollback deployment, approval required

## 8. UI/UX Architecture

Pages:

- Dashboard
- Services
- Incidents
- Reports
- Settings
- Evals later

Refresh:

- HTMX partial refresh for health and incidents.
- WebSockets/SSE later.

## 9. Observability

MVP:

- Runtime logs from Docker/Podman.
- Prometheus metrics.
- Grafana dashboards.

Later:

- Loki logs.
- OpenTelemetry Collector.
- GenAI/agent telemetry conventions.
