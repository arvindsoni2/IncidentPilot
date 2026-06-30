# IncidentPilot Codex Development Plan

## 1. Implementation Strategy

Use **architecture skeleton first, then vertical slices**.

This is important because Codex should work against a clear structure, but each feature must become testable end-to-end quickly.

## 2. Proposed Repository Structure

```text
incident-devops-agent/
  agent/
    app/
      main.py
      config.py
      database.py
      models/
      services/
      web/
      templates/
      static/
    cli/
      main.py
    workflows/
      base.py
      plain_python.py
    adapters/
      runtime/
        base.py
        docker_adapter.py
        podman_adapter.py
      llm/
        base.py
        ollama_adapter.py
      metrics/
        prometheus_adapter.py
    prompts/
      incident_diagnosis.md
      incident_report.md
      hypothesis_ranking.md
    tests/

  demo-app/
    frontend/
    backend/
    db/
    failure-scenarios/

  infra/
    compose.yaml
    compose.docker.override.yaml
    compose.podman.override.yaml
    prometheus/
    grafana/

  docs/
    prd/
    story-map/
    acceptance-criteria/
    architecture/
    implementation/
    evals/
    runbooks/
    incidentpilot-foundation-guide.html

  tests/
    integration/
    golden-files/
    fixtures/
```

## 3. Build Phases

### Phase 0: Project Bootstrap

Tasks:

- Create repo structure.
- Add Python package setup.
- Add FastAPI app shell.
- Add Typer CLI shell.
- Add SQLAlchemy database setup.
- Add `.env.example`.
- Add `config.example.yaml`.
- Add basic tests.

Done when:

- API starts.
- CLI runs.
- DB migration/create works.
- Health page renders.

### Phase 1: Demo App and Compose

Tasks:

- Create backend service with `/health`.
- Create frontend placeholder.
- Create postgres dependency.
- Add Compose spec.
- Add Prometheus and Grafana baseline.
- Add failure scenario scripts for FS-001 and FS-002.

Done when:

- Demo app starts healthy.
- FS-001 stops backend.
- FS-002 stops postgres.
- Reset restores healthy state.

### Phase 2: Runtime Adapters

Tasks:

- Define runtime adapter interface.
- Implement Docker adapter.
- Implement Podman adapter.
- Add service config loading.
- Add recent log collection.
- Add container metadata collection.

Done when:

- CLI can show service runtime status.
- Tests cover adapter interface with mocks.
- At least one runtime path is integration-tested.

### Phase 3: Evidence Collection

Tasks:

- Implement health endpoint checker.
- Implement dependency checker.
- Implement runtime log collector.
- Implement Prometheus metrics adapter.
- Store evidence in DB.

Done when:

- Evidence exists for FS-001 and FS-002.
- Evidence is structured and referenceable.

### Phase 4: Rules Diagnosis

Tasks:

- Implement rule engine.
- Detect container stopped.
- Detect health failing.
- Detect dependency down.
- Assign severity.
- Generate baseline hypotheses and recommendations.

Done when:

- Rules-only diagnosis passes FS-001 and FS-002 evals.

### Phase 5: LLM Adapter and Prompts

Tasks:

- Implement Ollama adapter.
- Add retry and timeout logic.
- Add prompt files.
- Send structured context to LLM.
- Parse structured JSON response.
- Fall back to rules-only mode.

Done when:

- LLM path works.
- Timeout fallback works.
- LLM output validates schema.

### Phase 6: Incident Workflow

Tasks:

- Implement `IncidentWorkflow` interface.
- Implement `PlainPythonIncidentWorkflow`.
- Persist incident lifecycle.
- Persist agent runs.
- Generate final JSON and Markdown report.

Done when:

- `incidentpilot analyze --service backend` works end-to-end.

### Phase 7: CLI

Tasks:

- `analyze`
- `incidents list`
- `incidents show`
- `reports show`
- `reports export-json`
- `reports download-markdown`
- `deployments record`
- `scenarios trigger`
- `scenarios reset`

Done when:

- FS-001 and FS-002 can be run from CLI.

### Phase 8: Dashboard

Tasks:

- Dashboard page.
- Services page.
- Incidents page.
- Incident detail page.
- Reports page.
- Settings page.
- HTMX partial refresh.

Done when:

- FS-001 and FS-002 can be analysed and reviewed from UI.

### Phase 9: Testing and Evals

Tasks:

- Integration tests for FS-001.
- Integration tests for FS-002.
- Golden-file evals.
- Schema validation.
- Unit tests for rules and config.
- UI smoke tests.

Done when:

- MVP eval suite passes.

### Phase 10: Docs and Demo Script

Tasks:

- Setup guide.
- Architecture overview.
- Runbook.
- Testing/evals guide.
- Troubleshooting.
- Portfolio/interview demo script.

Done when:

- A new user can run the demo from docs.

## 4. Codex Working Rules

- Work in small vertical slices.
- Do not add remediation execution.
- Do not add arbitrary shell execution.
- Keep runtime-specific code inside adapters.
- Keep prompts in files.
- Keep output schema stable.
- Add tests with every behaviour change.
- Prefer simple implementation over premature LangGraph complexity.
- Maintain Docker and Podman abstraction.
