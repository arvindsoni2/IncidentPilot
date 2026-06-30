# IncidentPilot Portfolio and Interview Demo

Target duration: 8–12 minutes.

## Before the session

```bash
source .venv/bin/activate
docker compose -f infra/compose.yaml up -d --build
incidentpilot scenarios reset
incidentpilot poll run --once
incidentpilot evals run
```

In another terminal:

```bash
incidentpilot web
```

Open:

- IncidentPilot: <http://127.0.0.1:8083>
- Grafana: <http://127.0.0.1:3001>

If using Ollama:

```bash
ollama list
```

## 1. Frame the problem

Show the Dashboard and Services pages.

Say:

> IncidentPilot removes the repetitive first minutes of local incident triage.
> It collects evidence, establishes deterministic facts, optionally uses an
> LLM for evidence-grounded ranking, and produces an auditable report.

Point out:

- Docker/Podman runtime selection;
- dependency mapping;
- polling interval;
- localhost binding;
- read-only safety state.

## 2. Explain the safety architecture

Show Settings.

Say:

> I deliberately shipped diagnosis before self-healing. The LLM has no tools
> or terminal. It cannot invent evidence or action keys, relax policy flags,
> enable execution, or claim an action happened.

Clarify that scenario commands are a separate, fixed demo harness—not agent
remediation.

## 3. Demonstrate FS-001

```bash
incidentpilot scenarios trigger FS-001
incidentpilot analyze --service backend
```

Expected:

- backend is stopped;
- severity is high;
- rank one is `backend_container_stopped`;
- recommendation is manual restoration;
- execution is disabled and false.

Show Incident Detail:

- timeline;
- runtime evidence and bounded logs;
- ranked hypothesis with evidence references;
- Markdown report and JSON export.

Say:

> The stopped-container fact comes from deterministic runtime evidence. The LLM
> may improve ranking and narrative, but it cannot override the safety policy.

Reset:

```bash
incidentpilot scenarios reset
incidentpilot health check --service backend
```

## 4. Demonstrate FS-002

```bash
incidentpilot scenarios trigger FS-002
incidentpilot analyze --service backend
```

Expected:

- backend container is running;
- backend health returns 503;
- PostgreSQL is stopped;
- rank one is `dependency_unavailable`;
- recommendation is to restore the dependency first.

Say:

> This scenario demonstrates dependency reasoning: the system avoids falsely
> blaming the application when database evidence explains the health failure.

Reset:

```bash
incidentpilot scenarios reset
incidentpilot poll run --once
```

## 5. Show observability and degraded mode

Show the Grafana dashboard:

- backend target up;
- request rate by status;
- 5xx rate.

Say:

> Prometheus enriches evidence but is not a hard dependency. If Prometheus or
> Ollama is unavailable, IncidentPilot records the gap and still produces a
> rules-only diagnosis.

## 6. Show evaluations

```bash
incidentpilot evals run
```

Point out:

- JSON Schema validation;
- correct rank-one cause;
- report sections;
- `no_action_executed`;
- prompt/model metadata;
- semantic checks rather than brittle exact prose.

## 7. Close with the roadmap

Say:

> The next iteration would add a predefined action catalogue, policy engine,
> approval workflow, audited executor, and post-action verification. The LLM
> would still recommend only; policy and fixed implementations would execute.

Future roadmap:

- approval-gated controlled self-healing;
- one-attempt allowlisted container restart;
- rollback safeguards;
- execution audit log;
- pattern memory and incident similarity;
- Alertmanager, Loki, and OpenTelemetry;
- authentication for server deployment.

## Recovery before ending

```bash
incidentpilot scenarios reset
docker compose -f infra/compose.yaml ps
```

Leave the demo stack healthy.
