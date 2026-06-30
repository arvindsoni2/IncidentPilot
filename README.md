# IncidentPilot

[![CI](https://github.com/arvindsoni2/IncidentPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/arvindsoni2/IncidentPilot/actions/workflows/ci.yml)

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

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- GNU Make
- Docker Compose or Podman Compose
- Ollama is optional; rules-only diagnosis works without it

```bash
make install
cp .env.example .env
cp config.example.yaml config.yaml
uv run incidentpilot version
uv run incidentpilot db init
docker compose -f infra/compose.yaml up -d --build
uv run incidentpilot web
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

`uv run` executes commands in the locked project environment. The generated
console script is also available after activating `.venv`.

```bash
uv run incidentpilot --help
uv run incidentpilot web
```

To restore the short `incidentpilot` command in Bash:

```bash
source .venv/bin/activate
incidentpilot version
```

The equivalent dashboard launch command, which does not depend on the generated
console script, is:

```bash
INCIDENTPILOT_CONFIG_FILE=config.example.yaml \
  uv run incidentpilot web --host 127.0.0.1 --port 8083
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

Live failure scenarios are intentionally manual in v0.2 Milestone 1. CI runs
deterministic evaluations and builds the Compose images, but does not inject
FS-001 or FS-002.

## Reviewer verification

From a fresh checkout:

```bash
make install
make verify
make compose-build
```

Use `make check` for the fast lint-and-test loop or `make ci-local` for full
local CI parity, including Compose validation and image builds.

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
make check
make verify
make ci-local
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
- [Developer guide](docs/developer-guide.md)
- [v0.2 release-engineering plan](docs/v0.2-release-engineering-plan.md)
- [Architecture overview](docs/architecture/incidentpilot-architecture-overview.md)
- [Runbook](docs/runbooks/incidentpilot-mvp-runbook.md)
- [Testing and evaluations](docs/evals/incidentpilot-testing-guide.md)
- [Observability](docs/observability.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Portfolio/interview demo](docs/incidentpilot-demo-script.md)
- [Foundation guide](docs/incidentpilot-foundation-guide.html)
