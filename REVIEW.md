# IncidentPilot MVP Final Review

Review date: 2026-06-29
Source of truth: IncidentPilot Foundation Pack
Verdict: **GO for a local, single-user MVP demonstration**

IncidentPilot implements the Foundation Pack's read-only incident-triage scope.
It observes a containerised service, collects bounded evidence, diagnoses the
two required failure scenarios, optionally improves the narrative with an LLM,
and persists an auditable report. It does not contain a remediation executor.

This verdict applies to the documented localhost deployment. The application is
not ready for an unauthenticated shared or internet-facing deployment.

## Product scope

Implemented MVP capabilities:

- Docker and Podman inspection adapters;
- health polling and incident lifecycle persistence;
- bounded logs, health, dependency, metadata, deployment, and optional
  Prometheus evidence;
- deterministic diagnosis for FS-001 and FS-002;
- Ollama-compatible enhancement with rules-only fallback;
- JSON and Markdown reports;
- CLI and server-rendered web dashboard;
- controlled demo failure/reset harness;
- golden-file evaluations and automated tests.

No material overbuilding was found. FastAPI, Typer, Jinja/HTMX, SQLAlchemy,
Compose, Prometheus, and Grafana each support a stated MVP requirement.
Approval-gated remediation, authentication, alert ingestion, and distributed
deployment remain outside MVP scope.

## Safety

The MVP safety boundary passes review:

- runtime adapters expose inspection methods only;
- the LLM receives text and structured evidence, with no tools or shell;
- subprocess calls use argument lists, `shell=False`, timeouts, and validated
  container names or fixed demo targets;
- scenario operations are limited to FS-001, FS-002, and reset against exact
  `incidentpilot-demo-*` mappings;
- no `delete_volume`, rollback, arbitrary command, or remediation execution
  path exists;
- recommendation schemas require `execution_enabled_in_mvp: false` and
  `executed: false`;
- persistence overwrites both safety fields to false, and database constraints
  reject unsafe values;
- LLM output cannot add action keys or change deterministic policy flags.

One small hardening fix was made during review: the three safety configuration
values are now literal MVP invariants. Configuration validation rejects
`read_only: false`, `allow_remediation: true`, and
`allow_arbitrary_shell: true`.

The scenario harness intentionally mutates only the disposable demo stack. It
is separate from analysis and is not an agent remediation capability.

## Architecture

- Runtime-specific commands are isolated behind `ContainerRuntimeAdapter`.
- LLM transport is isolated behind `LLMProvider`.
- Prometheus is optional and returns an unavailable snapshot rather than
  aborting collection.
- `IncidentWorkflow` provides a small orchestration interface; the plain Python
  implementation keeps collection, rules, LLM enhancement, reporting, and
  persistence separated.
- SQLAlchemy relationships and constraints coherently model services, health
  history, incidents, evidence, hypotheses, recommendations, reports, and
  agent runs.

The architecture is appropriate for MVP scale. Migration tooling, an `EvalRun`
database entity, and asynchronous persistence are sensible later additions,
not blockers for the local MVP.

## Reliability

Verified automated paths:

- Ollama timeout retries once and becomes a structured provider error;
- provider errors, invalid JSON, invalid schemas, ungrounded evidence, and
  policy changes fall back to deterministic rules;
- Prometheus connection failure produces optional unavailable evidence;
- missing runtime logs are recorded as an evidence gap;
- unknown or unsafe scenarios are rejected before subprocess execution;
- scenario reset builds a fixed Compose `up -d` command.

The live demo stack was healthy at review time: backend, frontend, PostgreSQL,
Prometheus, and Grafana were running.

## Test and evaluation results

| Check | Result |
|---|---|
| Full pytest suite | Pass |
| FS-001 golden evaluation | Pass |
| FS-002 golden evaluation | Pass |
| Rules-only mode | Pass |
| UI pages, partials, actions, and exports | Pass |
| Compose configuration | Pass |
| Demo stack status | Five services running |
| Whitespace/error-marker check | Pass |

Both evaluations passed schema, service, severity, evidence, rank-one cause,
recommendation, report-section, LLM-status, and `no_action_executed` checks.

The host uses Python 3.14 with an installed `pytest-asyncio` plugin that emits
upstream deprecation warnings. These warnings do not indicate application test
failures; dependency compatibility should be pinned in the next hardening
cycle.

## Documentation

The setup guide, MVP runbook, troubleshooting guide, evaluation guide,
observability guide, architecture overview, and interview demo script are
complete and mutually consistent. They document localhost binding, degraded
operation, both failure scenarios, reset/recovery, and the read-only boundary.

## Release conditions

The code is ready for a local MVP demo. Before calling it a distributable
release:

1. create the initial reviewed Git commit and tag;
2. run the documented setup in a fresh virtual environment;
3. keep the web process bound to localhost;
4. keep Prompt 15/self-healing work deferred until separately approved.
