# IncidentPilot Next Iteration Plan

> Status (v0.3 reconnaissance): the release-engineering, migration/lifecycle,
> FS-001/FS-002 integration, and local-product foundations below were completed
> in v0.2 and verified before What Changed? implementation. They remain regression
> requirements rather than unfinished prerequisites.

Prompt 15 is deliberately deferred. The next iteration should harden the
read-only product before any remediation design begins.

## Phase 1 — release engineering

1. Create the initial reviewed commit and an `mvp-v0.1.0` tag.
2. Add CI for supported Python versions, pytest, evaluations, and Compose
   configuration validation.
3. Adopt reproducible dependency locking and remove unexpected test-plugin
   warnings.
4. Add a clean-machine installation and startup smoke test.

**Exit:** a fresh checkout can reproduce the reviewed test and eval results.

## Phase 2 — persistence and lifecycle

1. Introduce versioned database migrations.
2. Add an explicit failed-analysis incident state or failure outcome.
3. Persist evaluation runs and check results for trend reporting.
4. Define retention and export behavior for evidence and reports.

**Exit:** existing local databases upgrade safely and all workflow outcomes are
queryable.

## Phase 3 — integration confidence

1. Automate live FS-001 and FS-002 Compose tests.
2. Verify failure injection, evidence collection, diagnosis, persistence,
   report export, and reset in one test flow.
3. Add tests for runtime loss during analysis and reset failure recovery.
4. Validate Docker and Podman in environments where each runtime is available.

**Exit:** the complete demo flow is repeatable without manual intervention.

## Phase 4 — local product polish

1. Vendor the HTMX asset for offline operation.
2. Improve timestamped report timelines and evidence correlation.
3. Add clearer UI presentation for degraded evidence sources and failed runs.
4. Profile synchronous database work before deciding whether asynchronous
   persistence is justified.

**Exit:** the local experience is fully offline, clear under partial failure,
and measured before architectural expansion.

## Phase 5 — deployment security, only if scope expands

Before binding beyond localhost, add authentication, authorization, CSRF
protection, secure session handling, TLS guidance, secret management, and a
deployment threat model.

**Exit:** a separate security review approves the chosen deployment model.

## Deferred design gate — controlled self-healing

Do not implement remediation as part of the phases above. Prompt 15 should
begin only after explicit owner approval and must start with a design review
covering:

- fixed action catalogue with no arbitrary command fields;
- deterministic policy decisions outside the LLM;
- approval records and expiry;
- one-attempt execution limits;
- rollback and blast-radius controls;
- immutable audit events;
- post-action verification and fail-closed behavior;
- permanent blocking of destructive actions such as `delete_volume`.

The LLM should remain a recommender, never the executor or policy authority.
