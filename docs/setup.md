# IncidentPilot Setup Guide

## Prerequisites

- Python 3.11 or newer
- Git
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- GNU Make
- Docker with Compose v2, or Podman with `podman compose`
- Optional: Ollama for LLM-enhanced diagnosis

All application and demo ports bind to `127.0.0.1`.

## Python setup

From the repository root:

```bash
make install
cp .env.example .env
cp config.example.yaml config.yaml
uv run incidentpilot db init
```

On Windows, use WSL2 for the documented Linux workflow. To activate the
generated environment manually:

```bash
source .venv/bin/activate
```

Verify the installation:

```bash
uv run incidentpilot version
uv run incidentpilot services list
make verify
```

## Configuration

`.env` holds runtime/provider settings:

```env
INCIDENTPILOT_DATABASE_URL=sqlite:///./incidentpilot.db
INCIDENTPILOT_HOST=127.0.0.1
INCIDENTPILOT_PORT=8083
INCIDENTPILOT_DEFAULT_RUNTIME=docker
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
LLM_BASE_URL=http://127.0.0.1:11434
LLM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=1
```

`config.yaml` defines services, dependencies, polling, metrics, evidence
limits, eval output, and the read-only policy. The example already targets the
demo backend, frontend, and PostgreSQL containers.

To use Podman globally:

```yaml
runtime:
  default: podman
```

Individual services may override `runtime`.

Never commit `.env`, `config.yaml`, database files, or generated reports. The
repository `.gitignore` excludes them.

## Start with Docker

```bash
docker compose -f infra/compose.yaml up -d --build
docker compose -f infra/compose.yaml ps
```

## Start with Podman

```bash
podman compose -f infra/compose.yaml up -d --build
podman compose -f infra/compose.yaml ps
```

The shared Compose file is the baseline. Runtime override files are present for
future differences but currently contain no required changes.

## Optional Ollama setup

Install Ollama using its platform instructions, then:

```bash
ollama serve
ollama pull qwen3:8b
ollama list
```

Use a different installed model by changing `LLM_MODEL`. IncidentPilot sends
only structured incident context and requests JSON. The model receives no
terminal, tools, or runtime access.

If Ollama is unavailable, IncidentPilot retries once, marks
`llm_status: unavailable`, and completes a rules-only diagnosis.

## Start IncidentPilot

```bash
incidentpilot web
```

Open <http://127.0.0.1:8083>. Verify:

```bash
curl http://127.0.0.1:8083/health
incidentpilot health check --service backend
```

To run health polling continuously:

```bash
incidentpilot poll run
```

Use `Ctrl+C` to stop it. For one pass:

```bash
incidentpilot poll run --once
```

## Service URLs

| Component | URL | Notes |
|---|---|---|
| IncidentPilot | <http://127.0.0.1:8083> | Dashboard |
| Demo frontend | <http://127.0.0.1:8082> | Static workload |
| Demo backend | <http://127.0.0.1:8001/health> | DB-aware health |
| Prometheus | <http://127.0.0.1:9090> | Supplementary metrics |
| Grafana | <http://127.0.0.1:3001> | `admin` / `incidentpilot-demo-only` |
