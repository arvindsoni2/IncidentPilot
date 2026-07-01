# IncidentPilot v0.3 Golden Fixture List

Target repo path suggestion: `tests/fixtures/what_changed/`

Use exact filenames only if they fit existing repo convention.

## 1. `wc_001_http_500_dependency_healthy.json`

Purpose: main thin vertical slice.

Baseline:

- primary HTTP endpoint: `200 OK`;
- dependency: healthy.

Incident:

- primary HTTP endpoint: `500 Internal Server Error`;
- dependency: healthy.

Expected:

- status: `available`;
- material count: `1`;
- supporting_context count: `1`;
- other count: `0`;
- HTTP card:
  - category: `http`;
  - severity: `critical`;
  - materiality: `material`;
  - rule ID: `WC_HTTP_STATUS_PRIMARY_200_TO_500`.
- dependency card:
  - category: `dependency`;
  - severity: `info`;
  - materiality: `supporting_context`;
  - rule ID: `WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED`.

## 2. `no_baseline_available.json`

Purpose: no-baseline behavior.

Expected:

- status: `no_baseline`;
- no changes;
- no supporting context;
- rule summary explains comparison skipped;
- normal diagnosis remains allowed.

Expected wording:

> What Changed? comparison skipped because no last known healthy snapshot exists yet.

## 3. `llm_unavailable_fallback.json`

Purpose: LLM failure does not block deterministic output.

Expected:

- deterministic cards present;
- `llm.status: failed`, `configured: true`, `attempted: true`, and `retry_attempted: true`;
- `llm_failed: true`;
- `failure_reason: timeout`;
- `advisory_is_authoritative: false`;
- rule summary present;
- advisory summary absent/null.

## 4. `llm_validation_failure_hidden.json`

Purpose: unsafe/invalid advisory hidden.

Expected:

- deterministic cards present;
- validation metadata present;
- `validation_failed: true`;
- `advisory_hidden: true`;
- `fallback_used: deterministic_rule_summary`;
- raw rejected advisory text absent.

## 5. `http_latency_material_increase.json`

Purpose: hybrid latency threshold positive case.

Baseline:

- HTTP latency: `200ms`.

Incident:

- HTTP latency: `1400ms`.

Expected:

- material latency card;
- severity `high`, materiality `material`, rank `100`;
- rule ID: `WC_HTTP_LATENCY_HIGH_INCREASE`.

## 6. `http_latency_relative_only_ignored.json`

Purpose: prevent noisy latency false positives.

Baseline:

- HTTP latency: `10ms`.

Incident:

- HTTP latency: `30ms`.

Expected:

- no material latency card;
- no card in any group; all counts are zero.

## 7. `dependency_became_unreachable.json`

Purpose: dependency failure rule.

Baseline:

- dependency healthy.

Incident:

- dependency unreachable.

Expected:

- material dependency card;
- severity `critical`, materiality `material`, rank `30`;
- rule ID: `WC_DEPENDENCY_BECAME_UNREACHABLE`.

## 8. `runtime_restart_count_increased.json`

Purpose: runtime restart rule.

Baseline:

- restart count: `0`.

Incident:

- restart count: `2`.

Expected:

- runtime card;
- severity `high`, materiality `material`, rank `80`;
- rule ID: `WC_RUNTIME_RESTART_COUNT_INCREASED`.

## 9. `important_unchanged_image_dependency.json`

Purpose: supporting context examples.

Expected:

- dependency remained healthy card with `supporting_context`;
- unchanged image is deferred and omitted from v0.3 fixtures;
- no noise flood.

## 10. `mixed_material_supporting_other.json`

Purpose: UI/report grouping.

Expected:

- at least one `material` card;
- at least one `supporting_context` card;
- at least one `other` card;
- counts match card lists;
- Markdown and UI group sections correctly.

## 11. `comparison_failed_rule_engine_error.json`

- status `comparison_failed`;
- typed reason `rule_engine_error`;
- fixed safe message and error reference;
- normal diagnosis continues; no cards or fake baseline.

## 12. `safe_response_metadata_redaction.json`

- query values, userinfo, sensitive headers, request/response bodies, and unknown fields are absent;
- `path_without_query` is retained and `redaction_applied` is true.
