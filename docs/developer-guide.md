# IncidentPilot Developer Guide

## Prerequisites

IncidentPilot development is Linux-first and supports Python 3.11 and 3.12.
Install Git, GNU Make, [uv](https://docs.astral.sh/uv/getting-started/installation/),
and Docker with Compose v2. Ollama is optional.

Install uv with the official standalone installer if your package manager does
not provide it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On macOS, the same uv and Make commands apply once Docker Desktop is running.
On Windows, use WSL2 for the documented Linux workflow.

## Install

From the repository root:

```bash
make install
```

This runs `uv sync --group dev`, installs the project into `.venv`, and uses the
committed `uv.lock`.

## Verification levels

| Command | Purpose | Underlying commands |
|---|---|---|
| `make lint` | Conservative Ruff checks | `uv run ruff check .` |
| `make test` | Normal pytest suite | `uv run pytest` |
| `make eval` | Deterministic FS-001/FS-002 evals | `uv run incidentpilot evals run` |
| `make check` | Fast developer loop | lint + test |
| `make verify` | Docker-free product verification | check + eval |
| `make smoke-clean` | Fresh-checkout install/startup smoke | isolated archive + locked sync + health probe |
| `make compose-check` | Validate the demo Compose model | `docker compose -f infra/compose.yaml config --quiet` |
| `make compose-build` | Build local demo images | `docker compose -f infra/compose.yaml build` |
| `make live-integration` | Exercise live FS-001/FS-002 flows | isolated Compose stack + live pytest suite |
| `make ci-local` | Standard local CI checks | verify + Compose validation + build |

`make ci-local` and `make live-integration` deliberately fail when Docker or
Compose is unavailable.

CI installs dependencies with `uv sync --locked --group dev`; `--locked`
rejects drift between `pyproject.toml` and `uv.lock`.

## Docker and Podman

Docker Compose is the primary reviewer and CI path. Podman Compose is
best-effort locally:

```bash
make compose-check COMPOSE="podman compose -f infra/compose.yaml"
make compose-build COMPOSE="podman compose -f infra/compose.yaml"
make live-integration RUNTIME=podman
```

The Compose validation and build targets do not start services. The separate
live integration target starts an isolated stack, injects FS-001 and FS-002,
checks the persisted reports, resets the services, and tears the stack down.

## Local configuration

Create ignored local configuration before running the application:

```bash
cp .env.example .env
cp config.example.yaml config.yaml
uv run incidentpilot db init
uv run incidentpilot web
```

`incidentpilot db init` is idempotent. It runs Alembic migrations to the latest
revision and safely adopts databases created by the MVP before migration
versioning existed.

Evaluation runs are stored both as timestamped JSON files and queryable database
records:

```bash
uv run incidentpilot evals list
uv run incidentpilot evals export --output eval-history.json
uv run incidentpilot evals prune --older-than-days 90 --yes
```

See [Data retention and export](data-retention.md) for the deletion contract.

If dependency metadata changes, run `uv lock` and commit the updated lockfile.
If CI reports lockfile drift, reproduce it with `uv lock --check`.
