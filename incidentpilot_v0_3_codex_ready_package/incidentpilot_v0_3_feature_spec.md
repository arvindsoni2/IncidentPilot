# IncidentPilot v0.3 Feature Spec — What Changed?

Target repo path: `docs/features/what-changed-v0.3.md`

## 1. Feature summary

v0.3 adds read-only incident intelligence that answers the SRE question:

> What changed since the service was last known healthy?

IncidentPilot will compare current incident evidence against the last known healthy snapshot for the watched service and present the result in the dashboard, persisted Markdown report, and structured JSON report.

This phase remains read-only. It must not implement autonomous remediation, arbitrary shell execution, rollback, approval workflows, action executors, volume deletion, multi-user operation, or internet-facing deployment.

## 2. Product outcome

A user should be able to open an incident and quickly understand:

- what changed;
- what stayed the same but matters diagnostically;
- why the change matters;
- what evidence supports the conclusion;
- whether AI advisory text was used, unavailable, or rejected;
- that deterministic rules remain authoritative.

## 3. Selected v0.3 scope

### In scope

- Last known healthy snapshot.
- Snapshot scope: runtime + HTTP + dependency evidence.
- Snapshot creation only after successful full evidence collection and confirmed healthy service state.
- Latest healthy snapshot plus 20 historical healthy snapshots per watched service (21 total).
- Hybrid watched service identity:
  - primary: Compose project + service name;
  - fallback: container name;
  - container ID stored as evidence metadata only.
- What Changed? comparison against latest healthy snapshot.
- Impact-ranked change cards.
- Materiality groups:
  - `material`;
  - `supporting_context`;
  - `other`.
- Severity scale:
  - `critical`;
  - `high`;
  - `medium`;
  - `low`;
  - `info`.
- Deterministic rule-owned severity, ranking, materiality, evidence refs, and rule summary.
- Optional LLM advisory summary and per-change advisory notes.
- Strict validation and guardrails for LLM advisory text.
- UI/UX spec-first implementation.
- Contract-first TDD with golden fixtures.
- Scenario `WC-001`.

### Out of scope

- Remediation execution.
- Restart, rollback, volume deletion, shell execution, or arbitrary command execution.
- Approval workflows/action executors.
- Multi-user/auth/internet-facing deployment.
- Logs, deployment metadata, Prometheus, and config/env fingerprinting in the first What Changed? baseline.
- Configurable latency thresholds from day one.
- Multiple endpoint roles from day one.

## 4. Baseline model

### Healthy snapshot creation rule

IncidentPilot may update the last known healthy snapshot only when all are true:

1. Runtime evidence was collected successfully.
2. HTTP evidence was collected successfully.
3. Dependency evidence was collected successfully.
4. The watched service is considered healthy.
5. The configured watched HTTP endpoint is healthy.
6. Required dependencies are healthy/reachable.

Partial evidence must not create or replace a healthy snapshot.

### No baseline behavior

If no last known healthy snapshot exists when an incident is analyzed:

- do not block normal diagnosis;
- do not create a fake baseline;
- show a clear no-baseline state;
- persist no-baseline metadata in JSON and Markdown reports.

User-facing wording:

> What Changed? comparison skipped because no last known healthy snapshot exists yet.

## 5. Watched service identity

Use a stable service identity so healthy history survives container restarts/recreates.

Preferred identity:

```text
compose_project + service_name
```

Fallback identity:

```text
container_name
```

Evidence metadata only:

```text
container_id
image_id
image_tag
runtime_adapter
ports
health_status
restart_count
```

## 6. Snapshot retention

Persist:

- latest healthy snapshot per watched service;
- 20 historical healthy snapshots per watched service, in addition to latest.

The latest snapshot is used for v0.3 comparison. The 20-snapshot history prepares for future drift/trend/similar-incident work.

## 7. Evidence included in v0.3 baseline

### Runtime evidence

- container status;
- image ID/tag;
- uptime or observed running duration if available;
- restart count;
- exposed ports;
- health status;
- runtime adapter;
- container name;
- container ID as metadata.

### HTTP evidence

- watched endpoint URL/path;
- endpoint role for v0.3: configured watched endpoint is treated as `primary`;
- HTTP status;
- response classification;
- response time/latency;
- selected safe response metadata.

### Dependency evidence

- dependency name;
- dependency type if available;
- reachability/status;
- latency;
- failure category if any.

## 8. Change card contract

Each What Changed? card must contain:

```json
{
  "id": "wc_http_status_changed_primary",
  "title": "Primary HTTP endpoint started failing",
  "category": "http",
  "severity": "critical",
  "materiality": "material",
  "rank": 40,
  "before": {
    "label": "Last known healthy",
    "value": "200 OK",
    "observed_at": "2026-07-01T10:00:00Z"
  },
  "after": {
    "label": "Incident evidence",
    "value": "500 Internal Server Error",
    "observed_at": "2026-07-01T10:05:00Z"
  },
  "impact": "The primary watched endpoint is no longer serving successful responses.",
  "why_it_matters": "A primary endpoint moving from healthy to HTTP 500 is a strong app/service-layer incident signal.",
  "evidence_refs": ["http_probe_incident_001", "http_probe_baseline_001"],
  "timestamp": "2026-07-01T10:05:00Z",
  "rule_id": "WC_HTTP_STATUS_PRIMARY_200_TO_500",
  "ai_advisory_note": null
}
```

### Required fields

- `id`
- `title`
- `category`
- `severity`
- `materiality`
- `rank`
- `before`
- `after`
- `impact`
- `why_it_matters`
- `evidence_refs`
- `timestamp`
- `rule_id`

### Optional fields

- `ai_advisory_note`
- `metadata`

## 9. Severity rules

Use deterministic rules only. LLM output must not decide severity.

### Severity values

- `critical`: service unavailable or primary endpoint/core dependency down.
- `high`: likely incident-driving change but not necessarily full outage.
- `medium`: meaningful degradation or suspicious drift.
- `low`: minor but useful change.
- `info`: unchanged or neutral diagnostic context.

### First rule for WC-001

HTTP `200 -> 500` on the configured watched endpoint:

- endpoint role: `primary` for v0.3;
- severity: `critical`;
- materiality: `material`;
- category: `http`.

Later, when multiple endpoints exist:

- primary endpoint `200 -> 500`: `critical`;
- secondary endpoint `200 -> 500`: `high`.

## 10. Materiality groups

### `material`

Changed evidence likely relevant to the incident.

Examples:

- HTTP `200 -> 500` on primary endpoint;
- dependency healthy -> unreachable;
- restart count increased materially;
- health status healthy -> unhealthy.

### `supporting_context`

Unchanged or neutral evidence that helps diagnosis.

Examples:

- dependency remained healthy while HTTP failed;
- image unchanged while service failed;
- restart count unchanged while endpoint failed;
- exposed ports unchanged.

### `other`

Low-impact changes, metadata drift, or noise.

Examples:

- tiny latency movement below threshold;
- non-critical metadata change;
- low-signal timestamp drift.

## 11. Deterministic rule catalogue for v0.3

### Runtime rules

- container status changed;
- health status changed;
- restart count increased;
- image tag/ID changed;
- exposed ports changed.

### HTTP rules

- HTTP status changed;
- response classification changed;
- endpoint became unavailable;
- response latency materially increased.

### Dependency rules

- dependency status changed;
- dependency became unreachable;
- dependency latency materially increased;
- dependency remained healthy while primary HTTP endpoint failed.

## 12. Latency threshold model

Use hybrid fixed + relative thresholds.

A latency increase should be flagged only when it crosses both:

- meaningful absolute increase; and
- meaningful relative increase.

Example default rule:

```text
material latency increase if:
  after_ms - before_ms >= 500ms
  AND
  after_ms / max(before_ms, 1ms) >= 2.0
```

Examples:

- `10ms -> 30ms`: ignore despite 3x increase.
- `200ms -> 1400ms`: material change.
- `800ms -> 1200ms`: omitted because it does not cross both thresholds.

Thresholds are not configurable in v0.3 unless existing config patterns make this trivial.

## 13. Summary contract

The What Changed? summary must separate rule-owned facts from optional AI advisory text.

```json
{
  "rule_summary": "The primary HTTP endpoint changed from healthy to failing while the dependency remained healthy.",
  "ai_advisory_summary": "This points more toward an app/service-layer issue than a dependency outage.",
  "summary_evidence_refs": ["http_probe_001", "dependency_probe_001"],
  "summary_generated_at": "2026-07-01T10:05:00Z",
  "llm": {
    "status": "accepted",
    "configured": true,
    "attempted": true,
    "model": "configured-model-name",
    "advisory_accepted": true,
    "advisory_is_authoritative": false
  }
}
```

Rules own the factual summary. AI advisory is optional, non-authoritative, and must not override deterministic output.

## 14. LLM advisory behavior

### LLM may add

- incident-level advisory summary;
- per-change advisory notes;
- plain-English explanation;
- possible relationship between existing evidence-backed change cards.

### LLM must not add or modify

- severity;
- ranking;
- materiality;
- evidence refs;
- rule IDs;
- report conclusions;
- remediation commands;
- shell commands;
- rollback instructions;
- restart/delete/exec instructions;
- claims that IncidentPilot fixed the issue.

### LLM unavailable behavior

If LLM advisory fails:

1. retry once;
2. fall back to deterministic rule summary;
3. continue incident analysis;
4. persist failure metadata;
5. show a non-alarming UI note.

UI note:

> AI advisory unavailable; deterministic analysis completed.

Expandable detail:

- retry attempted;
- failure reason category;
- timestamp;
- configured LLM/model name;
- fallback used;
- `advisory_is_authoritative: false`.

### LLM failure categories

- `not_configured`
- `timeout`
- `provider_error`
- `invalid_response`
- `empty_response`
- `policy_blocked`
- `unknown`

### LLM advisory validation failure behavior

If advisory output fails validation:

1. retry once with stricter prompt;
2. if still invalid, hide advisory;
3. persist validation failure metadata;
4. continue deterministic analysis.

Persist:

```json
{
  "validation_failed": true,
  "reason_category": "contains_remediation_command",
  "retry_attempted": true,
  "timestamp": "2026-07-01T10:05:00Z",
  "model": "configured-model-name",
  "fallback_used": "deterministic_rule_summary",
  "advisory_hidden": true,
  "advisory_is_authoritative": false
}
```

Do not persist raw rejected advisory text in normal reports.

## 15. UI/UX requirements

Design UI/UX first, not as an afterthought.

The dashboard should be implemented using the current FastAPI + Jinja + HTMX stack. Do not introduce React, a frontend build step, or a new UI framework unless explicitly approved.

### Full flow

1. Healthy evidence is collected.
2. Last known healthy snapshot is stored.
3. Incident occurs.
4. Incident list shows change-count badge.
5. Incident detail shows What Changed? section.
6. Persisted Markdown and JSON reports include the comparison.
7. Empty/no-baseline/LLM-unavailable/validation-failure states are handled clearly.

### Incident list

Show a concise badge/summary, for example:

- `2 changes detected`
- `No baseline`
- `AI advisory unavailable`

### Incident detail page

Order:

1. What Changed? summary.
2. Material Changes.
3. Supporting Context.
4. Other Changes, collapsed by default.
5. Advisory diagnostics, collapsed if unavailable/rejected.

### First WC-001 UI story

Summary:

> The primary HTTP endpoint changed from healthy to failing, while the dependency remained healthy. This suggests the incident may be closer to the app/service layer than the dependency layer.

Cards:

- Material Changes:
  - HTTP `200 OK -> 500 Internal Server Error`, severity `critical`.
- Supporting Context:
  - Dependency remained healthy, severity `info`.
- Other Changes:
  - None.

### Empty state

If no baseline exists:

> No healthy baseline is available yet. What Changed? comparison will appear after IncidentPilot observes a fully healthy runtime, HTTP, and dependency evidence set.

### Accessibility/readability

- Use clear headings.
- Use text labels in addition to badges/colors.
- Ensure collapsed sections are keyboard accessible.
- Do not rely on color alone for severity.
- Keep timestamps readable.
- Preserve evidence refs for auditability.

## 16. JSON report contract

The JSON report should include a top-level or nested `what_changed` object. Exact placement may follow existing report structure, but the contract must include:

```json
{
  "what_changed": {
    "status": "available",
    "baseline_snapshot_id": "hs_123",
    "baseline_observed_at": "2026-07-01T10:00:00Z",
    "incident_observed_at": "2026-07-01T10:05:00Z",
    "service_identity": {
      "strategy": "compose_project_service",
      "compose_project": "incidentpilot-demo",
      "service_name": "backend",
      "fallback_container_name": null
    },
    "counts": {
      "material": 1,
      "supporting_context": 1,
      "other": 0,
      "total": 2
    },
    "rule_summary": "The primary HTTP endpoint changed from healthy to failing while the dependency remained healthy.",
    "ai_advisory_summary": null,
    "summary_evidence_refs": ["http_probe_incident_001", "dependency_probe_incident_001"],
    "summary_generated_at": "2026-07-01T10:05:00Z",
    "llm": {
      "status": "not_attempted",
      "configured": true,
      "attempted": false,
      "advisory_is_authoritative": false
    },
    "material_changes": [],
    "supporting_context": [],
    "other_changes": [],
    "diagnostics": {}
  }
}
```

### `status` values

- `available`
- `no_baseline`
- `comparison_failed`

## 17. Markdown report contract

Markdown report should include:

```markdown
## What Changed?

The primary HTTP endpoint changed from healthy to failing while the dependency remained healthy.

### Material Changes

#### Critical — Primary HTTP endpoint started failing

- Before: 200 OK
- Now: 500 Internal Server Error
- Impact: The primary watched endpoint is no longer serving successful responses.
- Why it matters: A primary endpoint moving from healthy to HTTP 500 is a strong app/service-layer incident signal.
- Evidence: http_probe_baseline_001, http_probe_incident_001
- Rule: WC_HTTP_STATUS_PRIMARY_200_TO_500

### Supporting Context

#### Info — Dependency remained healthy

- Before: healthy
- Now: healthy
- Why it matters: The dependency did not fail at the same time as the HTTP endpoint, so the incident may be closer to the app/service layer.
- Evidence: dependency_probe_baseline_001, dependency_probe_incident_001
- Rule: WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED

### Other Changes

No other changes detected.

### AI Advisory

AI advisory unavailable; deterministic analysis completed.
```

## 18. Scenario WC-001

### Name

`WC-001 — HTTP failure with healthy dependency baseline`

### Baseline state

- Primary HTTP endpoint returns `200 OK`.
- Dependency is healthy/reachable.

### Incident state

- Primary HTTP endpoint returns `500 Internal Server Error`.
- Dependency remains healthy/reachable.

### Expected output

- One material HTTP change card:
  - category: `http`;
  - severity: `critical`;
  - materiality: `material`;
  - rule ID: `WC_HTTP_STATUS_PRIMARY_200_TO_500`.
- One supporting-context dependency card:
  - category: `dependency`;
  - severity: `info`;
  - materiality: `supporting_context`;
  - rule ID: `WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED`.
- Rule-owned summary.
- Optional guarded AI advisory summary.
- Deterministic analysis passes even if LLM advisory fails.
- JSON, Markdown, and UI render the same result.

## 19. Acceptance criteria

### Final resolved contract

- Recovery transitions are deferred; v0.3 compares a healthy baseline to incident evidence only.
- Every configured dependency is required/core; unreachable is critical/material/rank 30.
- Below-threshold latency changes are omitted.
- HTTP latency IDs are `WC_HTTP_LATENCY_HIGH_INCREASE` (rank 100) and
  `WC_HTTP_LATENCY_MEDIUM_INCREASE` (rank 110); dependency equivalents use ranks 120/130.
- Cards sort by materiality, rank, severity, category, rule ID, then card ID.
- Snapshot writes are atomic and retain latest plus 20 history. Latest wins by
  `observed_at`, then `created_at`, then lexicographically highest snapshot ID.
- A snapshot uses one collection run with a maximum 60-second evidence window.
- No-baseline and comparison-failed results do not invoke advisory generation.
- Metadata is allowlist-only; bodies, query values, credentials, and sensitive headers are never stored.
- `comparison_failed` uses typed, sanitized diagnostics and preserves normal diagnosis.

### Baseline acceptance

- Healthy snapshot is created only after complete healthy runtime + HTTP + dependency evidence.
- Partial evidence does not update the baseline.
- Unhealthy evidence does not update the baseline.
- Latest healthy snapshot is queryable per watched service.
- Latest plus 20 historical healthy snapshots are retained per watched service.

### Comparison acceptance

- No baseline state does not block analysis.
- WC-001 produces one material HTTP card and one supporting-context dependency card.
- Severity and materiality are deterministic.
- Latency changes use hybrid fixed + relative thresholds.
- Important unchanged evidence appears only when diagnostically useful.

### UI/report acceptance

- Incident list shows change-count or no-baseline badge.
- Incident detail renders summary first, then grouped cards.
- Other Changes is collapsed by default.
- LLM unavailable/rejected state is visible but non-alarming.
- JSON report validates against golden fixtures.
- Markdown report includes What Changed? section.

### Safety acceptance

- No remediation implementation.
- No shell commands/actions exposed in advisory text.
- LLM cannot overwrite rule-owned output.
- Invalid LLM advisory is hidden and metadata is persisted.
