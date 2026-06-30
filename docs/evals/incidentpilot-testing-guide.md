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

Start the demo stack before live checks:

```bash
docker compose -f infra/compose.yaml up -d --build
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:9090/-/healthy
```

The automated workflow tests mock runtime and LLM boundaries so CI does not
require Docker, Podman, Ollama, Prometheus, or network access.
