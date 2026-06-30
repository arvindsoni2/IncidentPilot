# IncidentPilot

IncidentPilot is a local-first incident triage agent for Docker and Podman
services. It collects operational evidence, applies deterministic rules,
optionally asks an Ollama-compatible model to rank evidence-grounded
hypotheses, and saves structured JSON plus SRE-style Markdown reports.

The MVP is deliberately **read-only**. It cannot restart containers, roll back
deployments, delete volumes, or execute arbitrary shell commands.

## MVP capabilities

- Docker and Podman runtime adapters
- Service health polling and incident history
- Runtime status, bounded logs, HTTP health, dependency, metadata, deployment,
  and optional Prometheus evidence
- Deterministic FS-001/FS-002 diagnosis
- Ollama reasoning with timeout/retry and rules-only fallback
- FastAPI, Jinja, and HTMX dashboard
- Typer CLI
- SQLite storage through PostgreSQL-compatible SQLAlchemy models
- Golden-file evaluations and UI/integration tests
- Controlled demo-only failure scenarios

## Quickstart

Requirements:

- Python 3.11 or newer
- Docker Compose or Podman Compose
- Ollama is optional; rules-only diagnosis works without it

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
cp config.example.yaml config.yaml
command -v incidentpilot
incidentpilot version
incidentpilot db init
docker compose -f infra/compose.yaml up -d --build
incidentpilot web
```

Open the IncidentPilot dashboard at <http://127.0.0.1:8083>.

The local interfaces are:

- IncidentPilot dashboard: <http://127.0.0.1:8083>
- Demo workload page: <http://127.0.0.1:8082>
- Backend health: <http://127.0.0.1:8001/health>
- Demo PostgreSQL: `127.0.0.1:5433`
- Prometheus: <http://127.0.0.1:9090>
- Grafana: <http://127.0.0.1:3001>

The page on port `8082` is intentionally a minimal static workload for
IncidentPilot to observe. It is not the IncidentPilot dashboard. The dashboard
and navigation pages are served by the separate `incidentpilot web` process on
port `8083`.

All commands below assume the virtual environment is active and the editable
install completed successfully. If `incidentpilot` is not found, use the module
entry point from the repository root:

```bash
python -m agent.cli.main --help
python -m agent.cli.main web
```

To restore the short `incidentpilot` command in Bash:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
hash -r
incidentpilot version
incidentpilot web
```

The equivalent dashboard launch command, which does not depend on the generated
console script, is:

```bash
INCIDENTPILOT_CONFIG_FILE=config.example.yaml \
  python -m agent.cli.main web --host 127.0.0.1 --port 8083
```

Do not use port `8080` for IncidentPilot on this workstation; it is already
owned by the local `llama.cpp` service.

## Demo

```bash
incidentpilot scenarios trigger FS-001
incidentpilot analyze --service backend
incidentpilot incidents list
incidentpilot reports show INC-001
incidentpilot scenarios reset

incidentpilot scenarios trigger FS-002
incidentpilot analyze --service backend
incidentpilot scenarios reset
```

Scenario commands are the sole exception to read-only operation: they use
fixed Compose arguments and an exact allowlist of `incidentpilot-demo-*`
containers. They are isolated from the analysis workflow.

## Common commands

```bash
incidentpilot services list
incidentpilot services status --service backend
incidentpilot health check --service backend
incidentpilot poll run --once
incidentpilot incidents show INC-001
incidentpilot incidents resolve INC-001
incidentpilot incidents close INC-001
incidentpilot reports export-json INC-001
incidentpilot reports download-markdown INC-001
incidentpilot evals run
pytest
```

Run `incidentpilot --help` for the complete command tree.

## Architecture

```text
Dashboard / CLI
       |
Incident workflow
       |
Evidence collector ---- Docker / Podman / HTTP / Prometheus
       |
Deterministic rules ---- optional Ollama reasoning
       |
SQLAlchemy storage ---- JSON + Markdown reports
```

Runtime-specific operations stay inside adapters. The LLM receives validated,
structured evidence and no tools. Deterministic rules retain control of
severity, evidence references, action keys, approval flags, and safety state.

## Configuration

Copy `.env.example` to `.env` for runtime/provider settings and
`config.example.yaml` to `config.yaml` for services, polling, metrics, and
safety policy. Environment variables override equivalent YAML values.

The dashboard binds to `127.0.0.1` by default. Settings are displayed
read-only, and credentials are never rendered.

## Documentation

- [Setup guide](docs/setup.md)
- [Architecture overview](docs/architecture/incidentpilot-architecture-overview.md)
- [Runbook](docs/runbooks/incidentpilot-mvp-runbook.md)
- [Testing and evaluations](docs/evals/incidentpilot-testing-guide.md)
- [Observability](docs/observability.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Portfolio/interview demo](docs/incidentpilot-demo-script.md)
- [Foundation guide](docs/incidentpilot-foundation-guide.html)
