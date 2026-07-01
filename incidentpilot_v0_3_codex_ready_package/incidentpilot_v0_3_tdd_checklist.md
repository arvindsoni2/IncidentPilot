# IncidentPilot v0.3 Contract-First TDD Checklist

## A. Before production code

- [ ] Read current repo structure and existing report/evidence/test patterns.
- [ ] Create `docs/features/what-changed-v0.3.md`.
- [ ] Create `docs/implementation/what-changed-v0.3-implementation-plan.md`.
- [ ] Define data contracts before implementation.
- [ ] Define golden fixtures before implementation.
- [ ] Add failing tests that describe expected behavior.
- [ ] Confirm failing tests fail for missing implementation, not syntax/import errors.

## B. Contract tests

- [ ] `ChangeSeverity` enum includes `critical`, `high`, `medium`, `low`, `info`.
- [ ] `ChangeMateriality` enum includes `material`, `supporting_context`, `other`.
- [ ] `WhatChangedStatus` includes `available`, `no_baseline`, `comparison_failed`.
- [ ] LLM failure categories include `not_configured`, `timeout`, `provider_error`, `invalid_response`, `empty_response`, `policy_blocked`, `unknown`.
- [ ] Golden fixtures validate against contract models.
- [ ] JSON serialization is stable.
- [ ] Required fields are enforced.
- [ ] Rank, grouped counts, typed LLM metadata, and typed comparison diagnostics are enforced.
- [ ] Recovery transitions and below-threshold latency produce no cards.

## C. Baseline tests

- [ ] Full healthy runtime + HTTP + dependency evidence creates latest healthy snapshot.
- [ ] Partial healthy evidence does not create or update snapshot.
- [ ] Unhealthy evidence does not create or update snapshot.
- [ ] Latest snapshot is queryable by stable service identity.
- [ ] Compose project + service name is preferred over container ID.
- [ ] Container name fallback works.
- [ ] Retention keeps latest plus last 20 healthy snapshots.

## D. Comparison tests

- [ ] No baseline returns `status: no_baseline` and does not block diagnosis.
- [ ] HTTP `200 -> 500` on primary endpoint produces severity `critical`.
- [ ] HTTP `200 -> 500` card materiality is `material`.
- [ ] Dependency healthy -> healthy while HTTP fails produces severity `info`.
- [ ] Dependency unchanged card materiality is `supporting_context`.
- [ ] Rule summary is deterministic.
- [ ] Evidence refs are present and known.
- [ ] Rule IDs are stable.

## E. Latency tests

- [ ] `10ms -> 30ms` is not material.
- [ ] `200ms -> 1400ms` is material.
- [ ] Relative threshold alone is not enough.
- [ ] Absolute threshold alone is not enough.
- [ ] Material latency increase gets expected severity/materiality.

## F. Report tests

- [ ] JSON report includes `what_changed` object.
- [ ] JSON report includes counts by materiality.
- [ ] JSON report includes rule summary and evidence refs.
- [ ] JSON report separates `rule_summary` and `ai_advisory_summary`.
- [ ] Markdown report includes `## What Changed?`.
- [ ] Markdown report includes Material Changes, Supporting Context, Other Changes.
- [ ] Markdown report includes evidence refs and rule IDs.
- [ ] No-baseline report has clear skipped-comparison wording.

## G. UI tests

- [ ] Incident list shows change-count badge.
- [ ] Incident list shows no-baseline badge when relevant.
- [ ] Incident detail shows summary first.
- [ ] Material Changes section renders before Supporting Context.
- [ ] Other Changes is collapsed by default.
- [ ] Severity appears as text, not only color.
- [ ] Evidence refs are visible.
- [ ] LLM unavailable note is visible and non-alarming.
- [ ] LLM validation failure note is visible and non-alarming.
- [ ] Expandable diagnostics include reason/retry/model/fallback/authorship metadata.

## H. LLM advisory tests

- [ ] Deterministic analysis succeeds when LLM is not configured.
- [ ] LLM timeout retries once and falls back.
- [ ] Empty advisory response is rejected.
- [ ] Invalid schema response is rejected.
- [ ] Advisory containing shell/remediation/rollback instructions is rejected.
- [ ] Invalid advisory is hidden from UI/report narrative.
- [ ] Validation failure metadata is persisted.
- [ ] Raw rejected advisory text is not persisted in normal reports.

## I. Live integration smoke

- [ ] `WC-001` creates healthy baseline.
- [ ] `WC-001` injects HTTP 500 while dependency remains healthy.
- [ ] Analysis produces material HTTP critical card.
- [ ] Analysis produces supporting dependency info card.
- [ ] JSON report persists What Changed? result.
- [ ] Markdown report persists What Changed? result.
- [ ] UI renders What Changed? result.
- [ ] Scenario reset works.
- [ ] Existing FS-001/FS-002 live integration remains green.

## J. Safety checks

- [ ] No restart/remediation code added.
- [ ] No arbitrary shell execution added.
- [ ] No rollback action added.
- [ ] No approval workflow/action executor added.
- [ ] No volume deletion behavior added.
- [ ] LLM cannot change severity/materiality/evidence refs/ranking.
- [ ] LLM cannot mark action executed.
- [ ] Dashboard remains localhost/local MVP oriented.
- [ ] Query values, userinfo, sensitive headers, and bodies are never persisted.
- [ ] Snapshot write/latest selection/pruning is atomic and deterministic.
- [ ] `comparison_failed` exposes only fixed safe messages and an opaque error reference.
