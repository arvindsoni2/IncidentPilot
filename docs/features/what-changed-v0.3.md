# What Changed? v0.3

IncidentPilot compares one atomic, last-known-healthy evidence set with current incident
evidence and renders deterministic, impact-ranked change cards in JSON, Markdown, and the
local dashboard. Recovery timelines and all remediation remain out of scope.

## Contract

- Evidence covers runtime, the configured primary HTTP endpoint, and every configured
  dependency. Every configured dependency is required/core in v0.3.
- A healthy snapshot requires one collection run, complete successful evidence, a running
  and healthy service, a healthy HTTP endpoint, healthy dependencies, and an observation
  window no longer than 60 seconds.
- Retention is the current latest plus 20 historical snapshots (21 total). Latest selection
  orders by `observed_at`, `created_at`, then snapshot ID, all descending.
- Cards contain deterministic severity, materiality, rank, rule ID, evidence references,
  before/after values, impact, and rationale. Ordering is materiality, rank, severity,
  category, rule ID, then card ID.
- Latency requires both absolute and relative growth. Medium is at least 500 ms and 2x;
  high is at least 1000 ms and 3x. Below-threshold changes are omitted.
- `no_baseline` and `comparison_failed` never invoke advisory generation.
- Optional LLM text is non-authoritative and cannot alter cards or report conclusions.

## WC-001

A primary HTTP transition from 200 to 500 produces a critical/material card at rank 40.
A required dependency that remains healthy produces an info/supporting-context card at
rank 500. The deterministic summary states that HTTP failed while the dependency remained
healthy.

## Data safety

Only allowlisted runtime, HTTP, and dependency metadata is retained. URLs are reduced to
scheme, host, and path without query. Userinfo, query values, bodies, sensitive headers,
tokens, secrets, raw exceptions, and provider errors are excluded from normal reports.

## Failure behavior

No baseline skips comparison without blocking diagnosis. Comparison failures use typed
reason metadata, fixed safe messages, and optional opaque error references. The outer report
continues and displays: “What Changed? comparison unavailable; normal diagnosis completed.”
