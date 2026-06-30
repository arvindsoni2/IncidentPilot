# IncidentPilot MVP Runbook and Demo Script

## 1. Demo Objective

Show that IncidentPilot can diagnose containerised application failures safely and explainably.

The MVP demonstrates:

- local-first DevOps agent
- Docker/Podman support
- health polling
- manual analysis
- runtime evidence collection
- rules + LLM diagnosis
- structured JSON output
- SRE-style report
- no remediation execution

## 2. Setup Flow

```bash
git clone <repo-url>
cd incident-devops-agent
cp .env.example .env
cp config.example.yaml config.yaml
```

Start demo stack:

```bash
docker compose -f infra/compose.yaml up -d
```

or Podman path:

```bash
podman compose -f infra/compose.yaml up -d
```

Start IncidentPilot:

```bash
incidentpilot web
```

Open:

```text
http://127.0.0.1:8083
```

## 3. Demo Walkthrough

### Step 1: Healthy Baseline

Show:

- Dashboard service cards are healthy.
- Services page shows backend, frontend, postgres.
- Settings page shows read-only runtime, LLM, safety policy.

### Step 2: Trigger FS-001

```bash
incidentpilot scenarios trigger FS-001
```

Expected:

- backend stops
- dashboard shows backend unhealthy
- incident candidate appears, or user triggers manual analysis

Run:

```bash
incidentpilot analyze --service backend
```

Show:

- rank-1 cause: backend container stopped
- evidence: container status/logs/health
- recommendation: manually restore/restart backend
- execution disabled in MVP
- SRE report generated

### Step 3: Reset

```bash
incidentpilot scenarios reset
```

Expected:

- backend healthy again
- incident resolved after 3 checks or manually resolved

### Step 4: Trigger FS-002

```bash
incidentpilot scenarios trigger FS-002
```

Run:

```bash
incidentpilot analyze --service backend
```

Show:

- backend unhealthy
- postgres stopped
- rank-1 cause: database dependency unavailable
- recommendation: restore DB first
- report includes dependency evidence

### Step 5: Reports

Show:

- Reports page
- copy Markdown
- download Markdown
- export JSON

### Step 6: Safety Architecture

Show Settings safety policy:

- restart_container modelled but disabled
- rollback modelled but disabled
- delete_volume blocked
- arbitrary shell blocked

## 4. Interview Talking Points

- I started with read-only triage before self-healing to prove diagnosis correctness.
- I separated deterministic evidence collection from LLM reasoning.
- The LLM never receives unrestricted terminal access.
- Docker and Podman are isolated behind runtime adapters.
- Golden-file evals check key facts instead of brittle exact wording.
- The action catalogue is modelled early but execution is disabled in MVP.
- The project is local-first but designed for a single server/cloud VM.
- The workflow interface allows LangGraph later without blocking the MVP.

## 5. Troubleshooting

### Dashboard does not open

Check:

```bash
incidentpilot web --host 127.0.0.1 --port 8083
```

### Ollama timeout

Check:

```bash
curl http://localhost:11434/api/tags
```

If unavailable, IncidentPilot should use rules-only mode.

### Docker permission issue

Check:

```bash
docker ps
```

### Podman issue

Check:

```bash
podman ps
```

### Prometheus unavailable

The agent should continue diagnosis and mark metrics evidence unavailable.

## 6. Demo Reset

```bash
incidentpilot scenarios reset
incidentpilot incidents list
```

## Scenario Runner Safety

Only these exact commands are supported:

```bash
incidentpilot scenarios list
incidentpilot scenarios trigger FS-001
incidentpilot scenarios trigger FS-002
incidentpilot scenarios reset
```

The runner uses fixed Compose arguments and an allowlist of
`incidentpilot-demo-*` containers. It rejects unknown scenario IDs, unsafe
container mappings, unsupported runtimes, and arbitrary operations. Scenario
execution is isolated from the read-only IncidentPilot analysis workflow.
