# What Changed? v0.3 Implementation Plan

1. Verify migrations, CI, FS-001/FS-002 live automation, reports, and UI test foundations.
2. Add typed contracts and exact golden fixtures before production behavior.
3. Implement WC-001 as a thin deterministic JSON/Markdown/UI slice.
4. Add transactional healthy snapshots, deterministic latest selection, and 21-row retention.
5. Complete runtime, HTTP, dependency, ordering, latency, and redaction rules.
6. Add optional validated advisory behavior after deterministic comparison.
7. Add grouped accessible UI, no-baseline and comparison-failure states.
8. Exercise WC-001 in the isolated live stack and preserve FS-001/FS-002.

The implementation must remain local-first and read-only. It must not add restart, rollback,
delete, exec, arbitrary shell, approvals, action execution, authentication, or deployment.

Done requires lint, fast tests, migration smoke, report/UI tests, evaluations, and relevant
live integration to pass, with environmental limitations documented.
