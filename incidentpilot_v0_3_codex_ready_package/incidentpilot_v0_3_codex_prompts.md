# IncidentPilot v0.3 Sequential Codex Prompts

Use these prompts one at a time. Do not give Codex the whole implementation at once. Each prompt should end with tests or verification commands.

## Global instruction to prepend to every Codex prompt

You are working in the IncidentPilot repo.

Act as a senior product engineer with SRE dashboard UX experience and strong test-driven development discipline.

Non-negotiable constraints:

- IncidentPilot remains read-only.
- Do not implement remediation, restart, rollback, shell execution, arbitrary command execution, approval workflows, action executors, volume deletion, multi-user auth, or internet-facing deployment.
- Deterministic rules own facts, severity, ranking, materiality, rule IDs, evidence refs, and report conclusions.
- LLM output is optional, non-authoritative, schema-validated advisory text only.
- Do not introduce React or a frontend build chain. Use the existing FastAPI + Jinja + HTMX approach.
- Follow existing repo style and tests. Inspect before changing.
- Prefer small, reviewable changes.
- Keep existing FS-001/FS-002 tests and behavior green.

## Prompt 1 — Repo reconnaissance and exact implementation map

Inspect the repo and produce a concise implementation map for v0.3 What Changed?.

Goal: identify exact files/modules to extend for:

- evidence models;
- incident workflow;
- report JSON/Markdown generation;
- SQLAlchemy models and migrations;
- Jinja/HTMX UI;
- tests and fixtures;
- live integration/scenario harness.

Do not implement production behavior yet.

Output:

1. exact current files to modify;
2. new files to create;
3. test files to create/update;
4. migration need/no-need decision;
5. risks or unknowns;
6. commands to run for verification.

Respect all read-only safety constraints.

Before proceeding, verify Alembic, CI and FS-001/FS-002 live automation, report/UI test
patterns, and reconcile stale planning docs. Treat missing foundations as explicit prerequisite
work. Apply the resolved contract: 21 retained snapshots; typed counts/LLM/diagnostics;
required rank and deterministic ordering; fixed latency rule IDs; no recovery cards; no
below-threshold cards; required/core dependencies; atomic snapshot writes; safe metadata
allowlists; and contractual comparison-failure fallback.

## Prompt 2 — Add v0.3 spec docs

Create the two approved docs:

- `docs/features/what-changed-v0.3.md`
- `docs/implementation/what-changed-v0.3-implementation-plan.md`

Use the approved scope:

- last known healthy snapshot;
- runtime + HTTP + dependency baseline;
- latest snapshot plus 20 historical snapshots (21 total);
- hybrid service identity;
- impact-ranked cards;
- severity enum: critical/high/medium/low/info;
- materiality enum: material/supporting_context/other;
- WC-001 scenario;
- guarded optional LLM advisory;
- UI/UX spec-first;
- contract-first TDD.

Do not implement production behavior in this prompt except docs.

Run formatting/lint/docs checks if available.

## Prompt 3 — Contracts, fixtures, and failing tests only

Implement contract-first TDD setup for v0.3 What Changed?.

Create or extend domain contracts for:

- service identity;
- healthy snapshot;
- What Changed? result;
- change card;
- severity enum;
- materiality enum;
- LLM failure category;
- validation failure metadata.

Create golden fixtures for:

- WC-001 HTTP 200 -> 500 while dependency remains healthy;
- no baseline available;
- LLM unavailable fallback;
- LLM validation failure hidden;
- latency material increase;
- latency relative-only ignored;
- dependency became unreachable;
- restart count increased;
- mixed material/supporting/other grouping.

Add failing tests for:

- fixture validation;
- contract serialization;
- JSON report contract;
- Markdown report contract;
- UI rendering contract if current test setup supports it.

Do not implement comparison logic or DB persistence yet except minimal model definitions needed for tests to import.

Run targeted tests and show that they fail because production implementation is missing, not because of syntax/import errors.

## Prompt 4 — Thin vertical slice WC-001

Implement the smallest end-to-end slice for WC-001.

Scenario:

- baseline HTTP endpoint returns 200 OK;
- baseline dependency is healthy;
- incident HTTP endpoint returns 500 Internal Server Error;
- incident dependency remains healthy.

Expected output:

- one material HTTP change card:
  - category `http`;
  - severity `critical`;
  - materiality `material`;
  - rule ID `WC_HTTP_STATUS_PRIMARY_200_TO_500`.
- one supporting-context dependency card:
  - category `dependency`;
  - severity `info`;
  - materiality `supporting_context`;
  - rule ID `WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED`.
- deterministic rule summary;
- JSON report output;
- Markdown report output;
- UI rendering if existing view structure supports it.

Do not require LLM for this path.

Update tests from Prompt 3 so WC-001 passes.

Run targeted tests.

## Prompt 5 — Healthy snapshot persistence and retention

Implement latest healthy snapshot storage plus 20 historical snapshots per watched service.

Rules:

- Create/update baseline only after full runtime + HTTP + dependency evidence is successfully collected and healthy.
- Do not update from partial evidence.
- Do not update from unhealthy evidence.
- Prefer service identity `compose_project + service_name`.
- Fall back to container name.
- Store container ID only as evidence metadata.
- Retain the latest plus 20 historical healthy snapshots per watched service.

Add DB migration if needed.

Tests:

- eligibility tests;
- retention tests;
- identity tests;
- migration smoke if existing pattern supports it.

Run targeted tests and existing persistence tests.

## Prompt 6 — Complete v0.3 deterministic rule catalogue

Implement balanced runtime + HTTP + dependency comparison rules.

Runtime:

- container status changed;
- health status changed;
- restart count increased;
- image tag/ID changed;
- exposed ports changed.

HTTP:

- status changed;
- classification changed;
- endpoint unavailable;
- latency materially increased.

Dependency:

- status changed;
- became unreachable;
- latency materially increased;
- remained healthy while HTTP failed.

Latency threshold:

- require meaningful absolute increase and meaningful relative increase.
- Example: `after - before >= 500ms` and `after / max(before, 1ms) >= 2.0`.

Tests:

- severity/materiality per rule;
- latency positive and negative cases;
- evidence refs;
- rule IDs;
- grouping into material/supporting_context/other.

Run targeted tests.

## Prompt 7 — Guarded optional LLM advisory

Implement optional LLM advisory for What Changed?.

Rules:

- Generate rule summary first.
- LLM advisory is optional and non-authoritative.
- Retry once on LLM failure.
- Fall back to deterministic output.
- Validate structured advisory output.
- Reject output that changes severity/ranking/materiality/evidence refs/conclusions.
- Reject output containing remediation commands, shell commands, restart/delete/exec, rollback instructions, or claims that IncidentPilot fixed the issue.
- Do not persist raw rejected advisory text in normal reports.

Failure categories:

- not_configured;
- timeout;
- provider_error;
- invalid_response;
- empty_response;
- policy_blocked;
- unknown.

Persist metadata and expose it to reports/UI diagnostics.

Tests:

- LLM unavailable fallback;
- retry once;
- invalid schema;
- empty response;
- unsafe advisory rejected;
- metadata persisted;
- deterministic output remains available.

Run targeted tests.

## Prompt 8 — Product-quality UI/UX

Implement full What Changed? UI flow using existing FastAPI + Jinja + HTMX patterns.

Incident list:

- show change-count badge;
- show no-baseline badge;
- show advisory unavailable/hidden indicator only if useful and non-alarming.

Incident detail:

1. summary first;
2. Material Changes section;
3. Supporting Context section;
4. Other Changes collapsed by default;
5. advisory unavailable/hidden note;
6. expandable diagnostics.

Requirements:

- severity labels visible as text;
- evidence refs visible;
- timestamps readable;
- no reliance on color alone;
- clear empty state when no baseline exists;
- no raw stack traces in UI.

Tests:

- rendered sections;
- change card fields;
- badges;
- no-baseline state;
- advisory unavailable state;
- validation failure state;
- collapsed sections.

Run UI tests and targeted app tests.

## Prompt 9 — WC-001 live integration smoke

Add a live integration smoke test for WC-001.

Flow:

1. Start isolated demo stack.
2. Collect full healthy evidence and create baseline.
3. Inject HTTP 500 while dependency remains healthy.
4. Run analysis.
5. Verify persisted JSON report includes What Changed? result.
6. Verify Markdown report includes What Changed? section.
7. Verify UI renders material HTTP card and supporting dependency card if live UI tests already exist.
8. Reset environment.

Do not break FS-001/FS-002 live integration.

Run relevant live integration target locally if feasible, otherwise document exact command and any environment limitation.

## Prompt 10 — Final verification and cleanup

Run final verification:

- fast tests;
- lint/type checks if present;
- migration smoke;
- UI tests;
- report/eval tests;
- live integration target if feasible.

Update docs/index or README only if necessary to surface v0.3 docs.

Produce final summary:

- files changed;
- tests added;
- commands run;
- commands not run and why;
- remaining known limitations;
- confirmation that no remediation/execution features were introduced.
