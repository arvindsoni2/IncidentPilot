# IncidentPilot Testing and Evaluation Guide

## Test strategy

IncidentPilot prioritizes behavior and safety over raw coverage numbers:

- unit tests for config, adapters, rules, schemas, persistence, polling, and
  safety boundaries;
- workflow integration tests for FS-001, FS-002, and rules-only fallback;
- HTTP integration tests for the demo backend;
- dashboard smoke tests;
- golden-file evaluations for stable key facts.

## Run tests

```bash
pytest
```

Run focused suites:

```bash
pytest agent/tests/test_runtime_adapters.py
pytest agent/tests/test_evidence_collector.py
pytest agent/tests/test_rule_diagnosis.py
pytest agent/tests/test_incident_workflow.py
pytest agent/tests/test_web_dashboard.py
pytest agent/tests/test_eval_runner.py
pytest tests/integration/test_demo_backend.py
```

## Golden evaluations

```bash
incidentpilot evals run
incidentpilot evals run --scenario FS-001
incidentpilot evals run --scenario FS-002
```

Each invocation also persists the run and its individual check results in the
configured database. Inspect or export that history with:

```bash
incidentpilot evals list
incidentpilot evals export --output eval-history.json
```

Committed assets:

- `tests/golden-files/incident-analysis.schema.json`
- `tests/golden-files/fs-001.json`
- `tests/golden-files/fs-002.json`

Generated results are timestamped under `data/evals/` and ignored by Git.

## Eval checks

- `schema_valid`
- `service_correct`
- `severity_present`
- `evidence_present`
- `rank1_cause_correct`
- `recommendation_present`
- `recommendation_action_correct`
- `report_sections_present`
- `no_action_executed`
- `llm_status_recorded`

An eval passes only if every check passes.

## Interpreting results

The golden checks compare schema and operational facts, not exact prose. This
keeps evaluations stable when LLM wording changes.

For FS-001, rank one must be `backend_container_stopped`.

For FS-002, rank one must be `dependency_unavailable`; an application-level
backend fault must not outrank the failed database without supporting evidence.

`no_action_executed` is a release-blocking safety check.

## Live integration checks

Run the isolated Docker-backed scenario suite from the repository root:

```bash
make live-integration
```

The harness builds and starts the demo Compose stack, triggers FS-001 and
FS-002, analyzes each failure, checks the persisted incident and exported
report, restores the healthy baseline, and tears down its containers and
volume. CI runs the same target in a dedicated live integration job.

For best-effort Podman Compose coverage, use:

```bash
make live-integration RUNTIME=podman
```

The normal pytest suite continues to mock runtime and LLM boundaries, so only
the marked live suite requires a container runtime.

## Offline UI check

The dashboard serves its pinned HTMX build from `/static/htmx-2.0.8.min.js`;
it makes no browser request to a CDN. Version, upstream URL, license, and
checksum are recorded in [Third-party static assets](../third-party-assets.md).

## Browser smoke check

With the demo Compose stack and IncidentPilot dashboard running, execute:

```bash
uv run playwright install chromium
make visual-smoke
```

The Playwright suite checks the dashboard, services, incidents, reports,
settings, demo workload, and Grafana at desktop and mobile viewports. It fails
on HTTP errors, empty pages, JavaScript errors, or broken action busy states
and writes screenshots under `data/playwright/`.
