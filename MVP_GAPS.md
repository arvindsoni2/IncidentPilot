# IncidentPilot MVP Gaps

This register separates accepted MVP constraints from defects. No open P0
safety or correctness blocker was found in the final review.

## Closed in v0.2

### Reproducible dependency environment

Dependencies are locked with uv, and CI installs the locked development group
on the supported Python versions.

### Database migrations

Alembic migrations, legacy-database adoption, and upgrade/downgrade smoke
coverage are present.

### Automated live integration

CI starts an isolated Compose stack and runs FS-001 and FS-002 from failure
injection through persisted report verification and reset.

### Offline HTMX asset

HTMX 2.0.8 is vendored with its version, upstream source, license, and checksum
recorded in `docs/third-party-assets.md`.

### Evaluation history and failed-analysis lifecycle

Evaluation runs and check results are queryable database records, and failed
analysis has an explicit incident state with retained run errors.

### Report timeline depth

Persisted Markdown and JSON reports include timestamped lifecycle events and
evidence collection timestamps that correlate directly with evidence refs.

## P2 — accepted local-MVP constraints

### Localhost-only security model

There is no authentication, authorization, or CSRF protection. This matches the
single-user localhost MVP decision and blocks shared/network deployment.

### Synchronous persistence in web requests

The MVP uses synchronous SQLAlchemy sessions. This is simple and reliable for
a single local user but can block under concurrent load. A reproducible local
profile command now measures write and eager-read latency before any future
async design decision.

## Explicitly deferred

The following are not MVP gaps and must not be added casually:

- autonomous remediation;
- arbitrary shell execution;
- volume deletion;
- deployment rollback;
- approval workflows and action executors;
- multi-user or internet-facing operation.

Controlled self-healing design is Prompt 15 and remains deferred by owner
decision.
