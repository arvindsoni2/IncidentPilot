# IncidentPilot MVP Runbook

## 1. Establish a healthy baseline

```bash
source .venv/bin/activate
cp .env.example .env            # first run only
cp config.example.yaml config.yaml  # first run only
incidentpilot db init
docker compose -f infra/compose.yaml up -d --build
docker compose -f infra/compose.yaml ps
incidentpilot poll run --once
```

Expected:

- backend and PostgreSQL are healthy;
- frontend, Prometheus, and Grafana are running;
- `incidentpilot health list` shows HTTP 200 for backend/frontend.

Start the dashboard separately:

```bash
incidentpilot web
```

## 2. FS-001: backend container stopped

```bash
incidentpilot scenarios trigger FS-001
incidentpilot services status --service backend
incidentpilot analyze --service backend
incidentpilot incidents list
```

Expected diagnosis:

- severity `high`;
- rank-one cause `backend_container_stopped`;
- recommendation to restore backend manually;
- `execution_enabled_in_mvp: false`;
- `executed: false`.

Inspect the generated report:

```bash
incidentpilot incidents show INC-001
incidentpilot reports show INC-001
incidentpilot reports export-json INC-001
incidentpilot reports download-markdown INC-001
```

Restore:

```bash
incidentpilot scenarios reset
incidentpilot health check --service backend
```

## 3. FS-002: PostgreSQL dependency stopped

```bash
incidentpilot scenarios trigger FS-002
incidentpilot health check --service backend  # expected non-zero and HTTP 503
incidentpilot analyze --service backend
incidentpilot incidents list
```

Expected diagnosis:

- backend container still runs but health fails;
- PostgreSQL dependency is stopped;
- rank-one cause `dependency_unavailable`;
- recommendation to restore the dependency first;
- no action executed.

Restore:

```bash
incidentpilot scenarios reset
incidentpilot poll run --once
```

## 4. Resolve and close

After manually verifying recovery:

```bash
incidentpilot incidents resolve INC-001
incidentpilot incidents close INC-001
```

Continuous polling can resolve an active incident automatically after three
consecutive successful checks:

```bash
incidentpilot poll run
```

## 5. Run evaluations

```bash
incidentpilot evals run
incidentpilot evals run --scenario FS-001
incidentpilot evals run --scenario FS-002
```

Results are printed and stored under `data/evals/`.

## 6. Stop the environment

```bash
docker compose -f infra/compose.yaml down
```

Use `podman compose` in place of `docker compose` for Podman.

Do not use `down -v` unless you intentionally want to delete the demo
PostgreSQL volume.

## Safety note

`incidentpilot analyze`, polling, runtime inspection, and the dashboard are
read-only. `scenarios trigger/reset` is a separate demo harness limited to
fixed Compose operations and exact demo container names.
