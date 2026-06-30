# IncidentPilot Acceptance Criteria

## Global Acceptance Criteria

### AC-GEN-001: Local Startup

Given a fresh checkout, when the user follows the setup guide, then the demo app, IncidentPilot API, dashboard, database, Prometheus, and Grafana can be started locally.

### AC-GEN-002: Localhost Safety

Given MVP default configuration, when the dashboard starts, then it binds to `127.0.0.1` and does not expose unauthenticated UI to the network.

### AC-GEN-003: No Remediation Execution

Given any incident analysis in MVP, when the agent recommends an action, then it must not execute the action.

### AC-GEN-004: Rules-Only Fallback

Given the LLM is unavailable or times out twice, when an analysis runs, then the system produces a rules-only diagnosis and marks `llm_status: unavailable`.

---

## Service Configuration

### AC-CFG-001: Explicit Services

Given `config.yaml` defines a service, when the app starts, then the service appears in the Services page and CLI service list.

### AC-CFG-002: Runtime Default

Given a global default runtime is configured, when a service does not override runtime, then the service uses the default runtime.

### AC-CFG-003: Per-Service Runtime Override

Given a service declares `runtime: podman` or `runtime: docker`, when evidence is collected, then the correct runtime adapter is used.

### AC-CFG-004: Opt-In Labels

Given a container has `devops-agent.monitor=true`, when discovery runs, then the service can be discovered as monitored.

---

## Health Polling

### AC-HEALTH-001: Default Polling

Given no per-service polling interval, when health polling runs, then the default interval is 30 seconds.

### AC-HEALTH-002: Per-Service Polling

Given a service has `polling_interval_seconds: 60`, when health polling runs, then that service uses 60 seconds.

### AC-HEALTH-003: Incident Candidate

Given a monitored service becomes unhealthy, when polling observes the failure, then an incident candidate is created.

### AC-HEALTH-004: Auto Resolution

Given an incident is open/diagnosed, when the related service passes health checks 3 consecutive times, then the incident can be marked resolved automatically.

---

## FS-001: Backend Container Stopped

### AC-FS001-001: Trigger

Given the demo app is healthy, when the user runs `incidentpilot scenarios trigger FS-001`, then only the backend demo container is stopped.

### AC-FS001-002: Detection

Given backend is stopped, when the user runs `incidentpilot analyze --service backend`, then the analysis detects that the backend container is not running.

### AC-FS001-003: Rank-1 Cause

Given backend is stopped, when analysis completes, then rank-1 hypothesis is backend container stopped/unavailable.

### AC-FS001-004: Recommendation

Given backend is stopped, when report is generated, then recommendation is to restore/start/restart backend manually, and execution is disabled in MVP.

### AC-FS001-005: Report

Given FS-001 analysis completes, then structured JSON and Markdown report are saved and visible in UI/CLI.

---

## FS-002: DB Down Causing Backend Failure

### AC-FS002-001: Trigger

Given the demo app is healthy, when the user runs `incidentpilot scenarios trigger FS-002`, then only the postgres demo container is stopped.

### AC-FS002-002: Dependency Detection

Given postgres is stopped and backend is unhealthy, when the user analyzes backend, then the agent checks postgres dependency status.

### AC-FS002-003: Rank-1 Cause

Given postgres is stopped and backend is unhealthy, when analysis completes, then rank-1 hypothesis is database dependency unavailable.

### AC-FS002-004: Avoid False Blame

Given backend health is failing because DB is down, when analysis completes, then the agent must not rank backend application failure above DB dependency failure unless evidence supports it.

### AC-FS002-005: Recommendation

Given FS-002 analysis completes, then recommendation is to restore postgres/database dependency first, and execution is disabled in MVP.

---

## CLI

### AC-CLI-001: Analyze

`incidentpilot analyze --service backend` starts analysis and returns incident ID.

### AC-CLI-002: Incidents List

`incidentpilot incidents list` shows recent incidents with ID, service, severity, status, and created time.

### AC-CLI-003: Incident Show

`incidentpilot incidents show INC-001` shows incident detail.

### AC-CLI-004: Report Show

`incidentpilot reports show INC-001` prints Markdown report.

### AC-CLI-005: Export JSON

`incidentpilot reports export-json INC-001` exports structured JSON.

### AC-CLI-006: Deployment Record

`incidentpilot deployments record --service backend --version v1 --notes "..."` stores manual deployment event.

### AC-CLI-007: Scenario Reset

`incidentpilot scenarios reset` restores demo app to healthy baseline.

---

## Dashboard

### AC-UI-001: Dashboard Page

The Dashboard page shows service health cards, active incidents, and recent diagnoses.

### AC-UI-002: Services Page

The Services page shows configured services, runtime, health URL, polling interval, and criticality.

### AC-UI-003: Incidents Page

The Incidents page shows incidents with status, severity, service, and creation time.

### AC-UI-004: Incident Detail

Incident detail shows evidence, hypotheses, recommendations, and report.

### AC-UI-005: Reports Page

Reports page supports view, copy Markdown, download Markdown, and export JSON.

### AC-UI-006: Settings Page

Settings page shows read-only config, LLM provider/model, runtime, safety policy, and security state.

---

## Evals

### AC-EVAL-001: Schema

All analysis JSON outputs must validate against the incident analysis schema.

### AC-EVAL-002: FS-001 Key Facts

FS-001 eval passes only if backend stopped is detected and ranked as the likely cause.

### AC-EVAL-003: FS-002 Key Facts

FS-002 eval passes only if DB dependency failure is detected and ranked as the likely cause.

### AC-EVAL-004: No Unsafe Action

Eval fails if MVP output indicates an action was executed.

### AC-EVAL-005: Report Sections

Markdown report must include summary, timeline, evidence, ranked hypotheses, recommendation, verification plan, and follow-up actions.
