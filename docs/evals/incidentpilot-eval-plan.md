# IncidentPilot Testing and Evaluation Plan

## 1. Testing Philosophy

IncidentPilot must prove behaviour, not just code coverage.

The MVP is successful only if the system diagnoses the intended failure scenarios correctly, explains evidence, generates reports, and remains safe.

## 2. Test Types

| Test Type | Purpose |
|---|---|
| Unit tests | Rules, config, adapters, schema |
| Integration tests | Demo app + runtime + analysis |
| Golden-file evals | Validate key facts and schema |
| UI smoke tests | Ensure pages render and navigation works |
| Degraded-mode tests | LLM unavailable / Prometheus unavailable |

## 3. MVP Failure Scenarios

### FS-001: Backend Container Stopped

Setup:

```bash
incidentpilot scenarios trigger FS-001
```

Expected:

- backend container stopped
- backend health unavailable
- rank-1 hypothesis: backend container stopped
- severity: high
- recommendation: manually restore/restart backend
- no action executed

### FS-002: DB Down Causing Backend Failure

Setup:

```bash
incidentpilot scenarios trigger FS-002
```

Expected:

- postgres stopped
- backend unhealthy
- rank-1 hypothesis: database dependency unavailable
- recommendation: restore database dependency first
- no action executed

## 4. Golden-File Eval Strategy

Use schema + key facts matching.

Do not require exact Markdown wording because local LLM output may vary.

### Required Checks

- JSON schema valid
- incident ID present
- service name correct
- severity present
- status present
- evidence exists
- ranked hypotheses exist
- recommendations exist
- report Markdown exists
- no remediation executed
- correct rank-1 cause for scenario

## 5. Eval Output Contract

```json
{
  "scenario_id": "FS-001",
  "passed": true,
  "checks": [
    {
      "name": "schema_valid",
      "passed": true
    },
    {
      "name": "rank1_cause_correct",
      "passed": true,
      "expected": "backend_container_stopped",
      "actual": "backend_container_stopped"
    }
  ],
  "model": "qwen3:8b",
  "prompt_versions": {
    "incident_diagnosis": "v1"
  }
}
```

## 6. Degraded Mode Evals

### LLM Unavailable

Given Ollama is unavailable, analysis should:

- retry once
- produce rules-only diagnosis
- mark `llm_status: unavailable`
- pass FS-001 and FS-002 key fact checks

### Prometheus Unavailable

Given Prometheus is unavailable, analysis should:

- mark metrics evidence unavailable
- continue with runtime and health evidence
- still pass FS-001 and FS-002

## 7. Future Report Quality Rubric

Later, score reports on:

- clarity
- evidence grounding
- hypothesis quality
- recommendation safety
- verification plan usefulness
- SRE trustworthiness
