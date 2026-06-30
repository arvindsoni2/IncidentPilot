# Data Retention and Export

IncidentPilot is local-first and does not delete incident evidence, reports, or
evaluation history automatically.

## Incident evidence and reports

Incident records, evidence, hypotheses, recommendations, agent runs, and
reports remain in the configured database until the operator removes the local
database. Reports can be exported without mutation:

```bash
incidentpilot reports export-json INC-001
incidentpilot reports download-markdown INC-001 --output INC-001.md
```

Automatic incident deletion is intentionally absent because partial deletion
would weaken the audit trail. Back up the database before any operator-managed
database removal.

## Evaluation history

Every deterministic evaluation is retained in two forms:

- timestamped JSON under `data/evals/` (or the configured output directory);
- queryable `eval_runs` and `eval_check_results` database records.

Export database history before pruning:

```bash
incidentpilot evals export --output eval-history.json
```

Pruning is explicit, age-based, and requires confirmation:

```bash
incidentpilot evals prune --older-than-days 90 --yes
```

This deletes matching database evaluation records and their checks. It does not
delete timestamped JSON files, incident evidence, or incident reports.
