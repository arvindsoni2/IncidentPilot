# IncidentPilot Story Map

## Backbone

1. Configure monitored services
2. Observe service health
3. Detect incident candidate
4. Collect evidence
5. Diagnose with rules
6. Enrich with LLM reasoning
7. Recommend safe action
8. Generate incident report
9. Track incident lifecycle
10. Review from UI/CLI
11. Run repeatable demo scenarios
12. Evaluate behaviour

---

## Release Slice 1: Architecture Skeleton

### User Activities

- Configure app
- Start dashboard
- Use CLI
- Store incidents

### Stories

- As a developer, I can start IncidentPilot locally.
- As a developer, I can configure Docker/Podman runtime settings.
- As a developer, I can configure monitored services in `config.yaml`.
- As a developer, I can open a dashboard on localhost.
- As a developer, I can run a CLI command.
- As the system, I can persist services, incidents, evidence, hypotheses, recommendations, reports, and agent runs.

### Acceptance Notes

- FastAPI app starts.
- Typer CLI works.
- SQLite database works.
- SQLAlchemy models are ready for PostgreSQL.
- Basic pages render.

---

## Release Slice 2: FS-001 Backend Container Stopped

### User Activity

Diagnose backend stopped incident.

### Stories

- As a user, I can trigger `FS-001`.
- As the agent, I can detect that backend container is stopped.
- As the agent, I can collect backend status and recent logs.
- As the agent, I can classify severity as high.
- As the agent, I can recommend that the human restore/restart the backend.
- As a user, I can view the incident report in UI and CLI.

### Acceptance Notes

- Scenario runner stops only demo backend.
- Agent does not restart the backend.
- Diagnosis identifies backend stopped as rank-1 cause.
- JSON and Markdown report are generated.
- Golden eval passes.

---

## Release Slice 3: FS-002 DB Down Causing Backend Failure

### User Activity

Diagnose dependency failure.

### Stories

- As a user, I can trigger `FS-002`.
- As the agent, I can detect backend health check failure.
- As the agent, I can check postgres dependency status.
- As the agent, I can avoid blaming backend incorrectly when DB is down.
- As the agent, I can recommend restoring the database first.
- As a user, I can compare FS-001 and FS-002 reports.

### Acceptance Notes

- Scenario runner stops only demo postgres.
- Backend becomes unhealthy.
- Diagnosis identifies DB dependency unavailable as rank-1 cause.
- Report includes dependency evidence.
- Golden eval passes.

---

## Release Slice 4: Health Polling and Incident History

### User Activity

Let the agent observe passively.

### Stories

- As the system, I can poll service health at configured intervals.
- As the system, I can create incident candidates when a service becomes unhealthy.
- As the system, I can avoid duplicate noisy incidents for the same ongoing failure.
- As a user, I can view previous incidents.
- As a user, I can filter incidents by service, status, severity, and date.
- As the system, I can auto-resolve after 3 successful health checks.

### Acceptance Notes

- Default polling is 30 seconds.
- Per-service override works.
- Incident history is persisted.
- Manual resolve works.
- Auto-resolve works after 3 successful checks.

---

## Release Slice 5: Dashboard and Reports

### User Activity

Review and present the system.

### Stories

- As a user, I can see service health cards.
- As a user, I can see incident list.
- As a user, I can open incident detail.
- As a user, I can view evidence, hypotheses, recommendations, and report.
- As a user, I can copy Markdown.
- As a user, I can download Markdown.
- As a user, I can export structured JSON.
- As a user, I can view read-only settings.

### Acceptance Notes

- HTMX partial refresh works.
- Dashboard feels demo-ready but minimal.
- Settings do not edit `.env` or YAML.
- Reports are accessible from incident detail and Reports page.

---

## Release Slice 6: Observability

### User Activity

Correlate runtime health with metrics.

### Stories

- As the system, I can query Prometheus for selected metrics.
- As a user, I can open Grafana to inspect service metrics.
- As the agent, I can include metrics snapshot as evidence when available.
- As the system, I can continue diagnosis even if Prometheus is unavailable.

### Acceptance Notes

- Prometheus and Grafana run in Compose.
- Agent does not hard depend on Prometheus.
- Metrics evidence is marked unavailable when needed.

---

## Release Slice 7: Documentation and Demo Script

### User Activity

Run and explain the project.

### Stories

- As a user, I can follow setup guide.
- As a user, I can follow demo script.
- As a user, I can run tests and evals.
- As a user, I can troubleshoot common local issues.
- As an interviewer, I can understand architecture from docs.

### Acceptance Notes

- Docs are in Markdown.
- Visual HTML guide exists.
- Demo script includes FS-001 and FS-002 walkthrough.
