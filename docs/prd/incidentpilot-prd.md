# IncidentPilot PRD

**Date:** 2026-06-29
**Version:** Foundation Pack v0.1
**Status:** Draft for implementation planning

## 1. Product Summary

**IncidentPilot** is a local-first incident triage and future self-healing DevOps agent. It watches Docker/Podman-hosted applications, diagnoses failures, ranks probable causes, recommends safe recovery actions, and generates SRE-style incident reports.

The first iteration is intentionally **read-only**. It does not restart, rollback, delete, or modify anything. It observes, reasons, recommends, and reports.

## 2. Product Positioning

IncidentPilot is designed for:

1. A solo developer running local containerised applications.
2. A portfolio/interview audience evaluating agentic AI, DevOps, observability, and safety architecture.
3. A future small DevOps/SRE team managing services on a single server or cloud VM.

## 3. Problem Statement

When a local or small-server containerised application fails, developers often manually inspect:

- container status
- runtime logs
- health checks
- recent deployment changes
- dependency containers
- resource usage
- metrics dashboards

This is repetitive and error-prone. IncidentPilot should collect the relevant evidence, diagnose the likely cause, explain the reasoning, and produce a structured incident report.

## 4. Goals

### MVP Goals

- Monitor explicitly configured and opt-in labelled Docker/Podman services.
- Detect unhealthy services through manual trigger and configurable health polling.
- Collect evidence from container runtime, recent logs, health checks, and Prometheus metrics.
- Diagnose two initial failure scenarios:
  - FS-001: backend container stopped.
  - FS-002: backend health check failing because database is down.
- Produce structured JSON and human-readable SRE-style Markdown reports.
- Provide both web dashboard and CLI access.
- Store incident history, evidence, hypotheses, recommendations, and reports.
- Support rules + LLM diagnosis, with rules-only fallback if LLM is unavailable.
- Execute no remediation actions in MVP.

### Future Goals

- Enable controlled self-healing for predefined safe actions.
- Add approval workflows for rollback.
- Add Loki and OpenTelemetry Collector.
- Add LangGraph implementation behind the workflow interface.
- Add pattern memory and incident similarity search.
- Add full postmortem workflow.
- Add server/cloud security model.

## 5. Non-Goals for MVP

- No unrestricted shell execution.
- No autonomous remediation.
- No delete volume capability.
- No Kubernetes support.
- No multi-user authentication.
- No production network exposure.
- No full ITSM workflow.
- No semantic vector memory.
- No Loki or OpenTelemetry Collector in Iteration 1.

## 6. Core Decisions

| Area | Decision |
|---|---|
| Project name | IncidentPilot |
| Product type | Local-first incident triage and future self-healing DevOps agent |
| Primary environment | Local laptop |
| Future portability | Single server / cloud VM compatible |
| Runtime support | Docker + Podman from day one |
| Target app | Demo app + intentional failure scenarios |
| Autonomy | Read-only diagnosis and recommendations in MVP |
| Triggers | Manual UI/CLI trigger + health polling |
| Polling | Configurable per service, default 30 seconds |
| UI | Web dashboard + CLI |
| UI stack | FastAPI + Jinja + HTMX |
| Main language | Python |
| LLM strategy | Hybrid rules + LLM |
| First LLM provider | Ollama |
| LLM model | Configurable |
| LLM fallback | Rules-only diagnosis if LLM fails |
| Storage | SQLite + PostgreSQL via SQLAlchemy |
| Operational memory | Basic incident history first; pattern memory later |
| Observability | Container runtime + Prometheus + Grafana |
| Logs | Runtime logs first; Loki later |
| Severity | low / medium / high / critical first; impact × urgency later |
| Incident lifecycle | new, analyzing, diagnosed, resolved, closed |
| Resolution rule | 3 successful health checks or manual resolve |
| Monitored services | Explicit config + opt-in labels |
| Runtime selection | Global default with per-service override |
| Deployment correlation | Manual deployment events + image/container metadata |
| First failure scenarios | FS-001 backend stopped; FS-002 DB down causing backend failure |
| Analysis output | Structured JSON + SRE-style Markdown report |
| Report format | SRE-style first; postmortem later |
| Primary persona | Solo developer + portfolio/interview demo audience |
| Success metric | Functional correctness + basic dashboard/demo polish |
| Implementation style | Architecture skeleton + vertical slices |
| Workflow orchestration | Internal workflow interface first; LangGraph adapter later |
| Testing | Integration tests + golden-file evals + targeted unit tests |
| Golden evals | Schema + key facts first; rubric later |
| Prompts | Editable Markdown prompt files first; DB/UI later |
| Config | .env + config.yaml first; DB-backed later |
| Safety policy | Model future action catalogue, execute nothing in MVP |
| Security | Localhost-only, no auth first; simple password later |
| Repo shape | Monorepo with clear packages |
| Compose strategy | One shared Compose spec, runtime overrides only when needed |
| Docs | Markdown source + standalone visual HTML guide |
| Dashboard style | Minimal admin dashboard first; portfolio polish later |
| Dashboard refresh | HTMX partial refresh first; WebSockets later |
| Navigation | Dashboard, Services, Incidents, Reports, Settings; Evals later |
| Settings | Read-only config display first |
| Reports | View/copy Markdown, download Markdown, export JSON; PDF later |
| CLI | Analyze, list/show incidents, show/export reports, record deployment, trigger/reset scenarios |
| Scenario runner | Predefined scripts only, scoped to demo app |
| Definition of done | FS-001 and FS-002 end-to-end from CLI/UI, reports, evals, docs/demo script complete |
| First deliverable | Foundation Pack |


## 7. User Personas

### Persona 1: Solo Developer

Needs to understand why a local app is broken without manually checking every container and log.

### Persona 2: Portfolio / Interview Audience

Needs to see agentic concepts clearly:

- observe
- reason
- rank hypotheses
- recommend safe action
- report

### Persona 3: Future SRE User

Needs trustworthy evidence, safe controls, incident history, and portability to a server/cloud VM.

## 8. MVP User Journeys

### Journey 1: Manual Incident Analysis

1. User opens dashboard.
2. User sees backend service is unhealthy.
3. User clicks **Analyze incident**.
4. IncidentPilot collects evidence.
5. IncidentPilot applies deterministic rules.
6. IncidentPilot asks LLM to rank hypotheses and write report.
7. User reviews recommendations and report.
8. User manually resolves the underlying issue.
9. IncidentPilot marks incident resolved after 3 successful checks, or user manually resolves it.
10. User closes the incident.

### Journey 2: CLI Incident Analysis

```bash
incidentpilot analyze --service backend
incidentpilot incidents list
incidentpilot reports show INC-001
incidentpilot reports export-json INC-001
```

### Journey 3: Demo Failure Scenario

```bash
incidentpilot scenarios trigger FS-001
incidentpilot analyze --service backend
incidentpilot reports show INC-001
incidentpilot scenarios reset
```

## 9. Functional Requirements

### FR-001: Service Configuration

IncidentPilot must support monitored services from:

- explicit `config.yaml`
- opt-in container labels

### FR-002: Runtime Support

IncidentPilot must support Docker and Podman through adapter interfaces.

### FR-003: Health Polling

IncidentPilot must poll configured health endpoints at configurable intervals, defaulting to 30 seconds.

### FR-004: Manual Trigger

The user must be able to trigger incident analysis from both UI and CLI.

### FR-005: Evidence Collection

For a target service, the agent must collect:

- container status
- health check result
- recent runtime logs
- dependency status where configured/inferred
- selected Prometheus metrics where available
- image/container metadata
- related manual deployment events

### FR-006: Deterministic Rule Diagnosis

The rules layer must detect at least:

- target container stopped
- target health check failing
- dependency container stopped/unhealthy
- LLM unavailable
- Prometheus unavailable

### FR-007: LLM Reasoning

The LLM must receive structured incident context, not unrestricted raw terminal access.

It should produce:

- ranked hypotheses
- confidence
- evidence references
- recommendation
- report draft

### FR-008: Degraded Mode

If the LLM times out:

1. Retry once.
2. Produce rules-only diagnosis.
3. Mark `llm_status: unavailable`.
4. Show warning in UI and report.

### FR-009: Incident Report

Every incident analysis must produce:

- structured JSON
- SRE-style Markdown report

### FR-010: Dashboard

MVP dashboard must include:

- Dashboard
- Services
- Incidents
- Reports
- Settings

### FR-011: CLI

MVP CLI must support:

- analyze service
- list/show incidents
- show/export reports
- record deployment event
- trigger/reset failure scenarios

### FR-012: Safety Policy

MVP must model future action catalogue but execute no action.

## 10. Non-Functional Requirements

### Reliability

Rules-only mode must still diagnose FS-001 and FS-002.

### Safety

LLM must never receive arbitrary shell access. Remediation execution is disabled in MVP.

### Portability

The app must run locally and be configurable for a single server/cloud VM later.

### Observability

Prometheus and Grafana are included in MVP, but the agent must still work without Prometheus.

### Maintainability

Use clean adapters for runtime, LLM, metrics, workflow, and storage.

### Demo Quality

The MVP must include docs and demo script sufficient for a portfolio/interview walkthrough.

## 11. MVP Definition of Done

MVP Iteration 1 is done when:

- demo app runs locally through Compose
- Docker and Podman paths are documented
- runtime adapters exist for both
- FS-001 works end-to-end
- FS-002 works end-to-end
- CLI can trigger scenarios, analyze incidents, and export reports
- UI shows dashboard, services, incidents, reports, and settings
- rules + LLM path works
- rules-only fallback works
- structured JSON and Markdown reports are generated
- golden-file evals pass
- agent executes no remediation
- setup guide, runbook, troubleshooting guide, eval guide, and demo script exist
