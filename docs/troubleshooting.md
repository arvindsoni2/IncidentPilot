# IncidentPilot Troubleshooting

## Docker permission or socket errors

Check:

```bash
docker version
docker ps
docker compose version
```

If Docker points to a rootless Podman socket, confirm that the user service is
running and that your current shell has the expected `DOCKER_HOST`.

## Podman Compose issues

Check:

```bash
podman version
podman info
podman compose version
podman ps
```

The Prometheus/Grafana configuration mounts use shared SELinux relabeling
(`:z`). If a custom mount reports `permission denied`, apply an appropriate
SELinux label rather than making the source world-writable.

## Ollama unavailable

Check:

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
```

Confirm `LLM_BASE_URL` and `LLM_MODEL`. IncidentPilot should still complete with
`llm_status: unavailable` and a rules-only report.

## LLM timeout

The default timeout is 120 seconds with one retry. Adjust:

```env
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=1
```

Smaller local models often respond faster. Invalid JSON or ungrounded evidence
also causes safe rules-only fallback.

## Prometheus unavailable

Check:

```bash
curl http://127.0.0.1:9090/-/healthy
docker compose -f infra/compose.yaml logs prometheus
```

Prometheus is optional. Runtime status, logs, health, dependency, metadata, and
deployment evidence remain available.

## Port conflicts

Default host ports:

| Port | Component |
|---:|---|
| 8083 | IncidentPilot |
| 8082 | Demo frontend |
| 8001 | Demo backend |
| 5433 | Demo PostgreSQL |
| 9090 | Prometheus |
| 3001 | Grafana |
| 11434 | Ollama |

Find a listener with `ss -ltnp`. Change the host side of the relevant Compose
`ports` mapping and update `config.yaml` health URLs. Change IncidentPilot with:

```bash
incidentpilot web --port 18080
```

## Backend unhealthy

```bash
curl -i http://127.0.0.1:8001/health
docker compose -f infra/compose.yaml logs backend postgres
incidentpilot services status --service backend
```

The backend intentionally returns HTTP 503 when PostgreSQL is unavailable.

## Scenario did not reset

```bash
incidentpilot scenarios reset
docker compose -f infra/compose.yaml ps
curl http://127.0.0.1:8001/health
```

Ensure `runtime.default` matches the runtime that owns the demo containers.

## Reset the SQLite database

Stop IncidentPilot first. Preserve a backup if history matters:

```bash
cp incidentpilot.db incidentpilot.db.backup
rm incidentpilot.db
incidentpilot db init
```

This deletes local incident history only; it does not touch the demo PostgreSQL
volume.

## Dashboard does not load

```bash
incidentpilot web --host 127.0.0.1 --port 8083
curl http://127.0.0.1:8083/health
```

The MVP has no authentication and must remain localhost-bound unless a future
security layer is added.
