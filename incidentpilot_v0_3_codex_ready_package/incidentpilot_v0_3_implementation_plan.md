# IncidentPilot v0.3 Implementation Plan — What Changed?

Target repo path: `docs/implementation/what-changed-v0.3-implementation-plan.md`

## 1. Implementation principles

- Contract-first TDD.
- Small setup prompts first, then vertical slices.
- UI/UX spec before implementation.
- Deterministic rules own facts, severity, ranking, materiality, and evidence refs.
- LLM advisory is optional, non-authoritative, schema-validated, and safely suppressible.
- The feature remains read-only.
- No remediation, shell execution, rollback, approval workflow, action executor, volume deletion, or network deployment work.

## 2. Suggested task sequence

### Milestone 0 — Repo reconnaissance

Codex should inspect existing patterns before changing files:

- report models/renderers;
- evidence models;
- incident workflow;
- health polling;
- SQLAlchemy models and Alembic migrations;
- Jinja templates;
- existing tests, golden files, live integration harness;
- FS-001/FS-002 scenario runner.
- Verify Alembic, CI/live FS-001/FS-002 automation, report/UI test patterns, and reconcile
  `NEXT_ITERATION_PLAN.md` with actual repository state before implementation.

Exit criteria:

- Codex identifies exact modules/files to extend.
- No production code changed yet unless adding docs.

### Milestone 1 — Feature spec and implementation plan docs

Create:

- `docs/features/what-changed-v0.3.md`
- `docs/implementation/what-changed-v0.3-implementation-plan.md`

Exit criteria:

- Docs match approved discovery decisions.
- Read-only boundaries are explicitly stated.
- WC-001 scenario is defined.

### Milestone 2 — Contracts + golden fixtures + failing tests

Create code contracts for:

- healthy snapshot;
- service identity;
- evidence baseline sections;
- What Changed? comparison result;
- change card;
- severity enum;
- materiality enum;
- AI advisory metadata;
- validation failure metadata.

Create golden fixtures for:

- no baseline;
- WC-001 available comparison;
- LLM unavailable fallback;
- LLM validation failure fallback;
- latency material increase;
- latency ignored because only relative threshold crossed;
- important unchanged dependency evidence.

Create failing tests for:

- fixture validation;
- model serialization/deserialization;
- rule output shape;
- JSON report contract;
- Markdown report contract;
- UI rendering contract.

Exit criteria:

- Tests fail for expected missing implementation, not because of syntax/import errors.
- Fixtures are valid against contracts.

### Milestone 3 — Thin vertical slice WC-001

Implement the narrow end-to-end slice:

Baseline:

- HTTP `200 OK`;
- dependency healthy.

Incident:

- HTTP `500 Internal Server Error`;
- dependency healthy.

Output:

- material HTTP critical card;
- supporting-context dependency info card;
- rule summary;
- JSON report output;
- Markdown report output;
- UI rendering.

Exit criteria:

- All WC-001 fast tests pass.
- UI renders the expected sections and badges.
- No LLM required for test pass.

### Milestone 4 — Healthy snapshot persistence and retention

Implement:

- latest healthy snapshot per watched service;
- latest plus 20 historical snapshots per watched service (21 total);
- stable service identity;
- DB migration if needed;
- repository/query layer;
- snapshot capture only after full healthy evidence.

Exit criteria:

- Healthy snapshot saved only from complete healthy evidence.
- Partial/unhealthy evidence does not update latest snapshot.
- Retention keeps latest plus 20 historical snapshots.
- Container ID changes do not break service history when Compose project + service name are available.

### Milestone 5 — Complete deterministic rule catalogue

Implement v0.3 rules:

Runtime:

- container status changed;
- health status changed;
- restart count increased;
- image tag/ID changed;
- ports changed.

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

Exit criteria:

- Rule tests cover severity/materiality/evidence refs.
- Latency hybrid threshold tests pass.
- Low-impact changes go to `other`.
- Important unchanged evidence goes to `supporting_context`.

### Milestone 6 — Guarded LLM advisory

Implement optional advisory behavior:

- rule summary always generated first;
- LLM advisory attempted only after deterministic comparison;
- retry once on failure;
- validate structured advisory output;
- reject remediation/shell/rollback/action text;
- persist failure/validation metadata;
- expose UI note and expandable diagnostics.

Exit criteria:

- LLM unavailable does not fail analysis.
- Invalid advisory is hidden.
- Metadata persists in JSON/Markdown.
- UI shows non-alarming note and expandable diagnostics.

### Milestone 7 — UI/UX polish and accessibility

Implement full flow:

- incident list change-count/no-baseline badge;
- incident detail What Changed? section;
- summary first;
- grouped Material Changes, Supporting Context, Other Changes;
- Other Changes collapsed by default;
- advisory diagnostics collapsed;
- clear empty states.

Exit criteria:

- UI tests assert key text, sections, severity labels, and collapsed sections.
- No reliance on color alone.
- Existing dashboard behavior remains intact.

### Milestone 8 — Live integration smoke for WC-001

Add one live integration smoke test:

1. Bring up isolated demo stack.
2. Collect healthy full evidence and create baseline.
3. Inject HTTP 500 while dependency remains healthy.
4. Run analysis.
5. Verify persisted report.
6. Verify UI/report contains material HTTP card and supporting dependency card.
7. Reset environment.

Exit criteria:

- CI/local live integration passes.
- Existing FS-001/FS-002 flows are not broken.

## 3. Proposed file areas

Codex must inspect repo before deciding exact paths. Likely areas:

```text
agent/incidentpilot/domain/
agent/incidentpilot/storage/
agent/incidentpilot/reports/
agent/incidentpilot/web/
agent/incidentpilot/templates/
agent/incidentpilot/scenarios/
migrations/versions/
tests/unit/
tests/integration/
tests/ui/
tests/fixtures/
docs/features/
docs/implementation/
```

Do not create new top-level architecture unless existing structure requires it.

## 4. Data contract sketch

Use existing project style. Pydantic or dataclasses may be chosen based on current code patterns.

### Enums

```python
class ChangeSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class ChangeMateriality(str, Enum):
    MATERIAL = "material"
    SUPPORTING_CONTEXT = "supporting_context"
    OTHER = "other"

class WhatChangedStatus(str, Enum):
    AVAILABLE = "available"
    NO_BASELINE = "no_baseline"
    COMPARISON_FAILED = "comparison_failed"

class LlmFailureReason(str, Enum):
    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"
    EMPTY_RESPONSE = "empty_response"
    POLICY_BLOCKED = "policy_blocked"
    UNKNOWN = "unknown"
```

### Key models

```python
class ServiceIdentity(BaseModel):
    strategy: Literal["compose_project_service", "container_name"]
    compose_project: str | None = None
    service_name: str | None = None
    container_name: str | None = None

class EvidenceValue(BaseModel):
    label: str
    value: str
    observed_at: datetime | None = None

class WhatChangedCard(BaseModel):
    id: str
    title: str
    category: Literal["runtime", "http", "dependency"]
    severity: ChangeSeverity
    materiality: ChangeMateriality
    rank: int
    before: EvidenceValue
    after: EvidenceValue
    impact: str
    why_it_matters: str
    evidence_refs: list[str]
    timestamp: datetime
    rule_id: str
    ai_advisory_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class WhatChangedResult(BaseModel):
    status: WhatChangedStatus
    baseline_snapshot_id: str | None = None
    baseline_observed_at: datetime | None = None
    incident_observed_at: datetime | None = None
    service_identity: ServiceIdentity
    rule_summary: str | None = None
    ai_advisory_summary: str | None = None
    summary_evidence_refs: list[str] = Field(default_factory=list)
    summary_generated_at: datetime | None = None
    material_changes: list[WhatChangedCard] = Field(default_factory=list)
    supporting_context: list[WhatChangedCard] = Field(default_factory=list)
    other_changes: list[WhatChangedCard] = Field(default_factory=list)
    counts: WhatChangedCounts
    llm: LlmAdvisoryMetadata
    diagnostics: WhatChangedDiagnostics
```

## 5. Rule ID conventions

Use stable string constants:

```text
WC_HTTP_STATUS_PRIMARY_200_TO_500
WC_DEPENDENCY_REMAINED_HEALTHY_WHILE_HTTP_FAILED
WC_DEPENDENCY_BECAME_UNREACHABLE
WC_HTTP_LATENCY_HIGH_INCREASE
WC_HTTP_LATENCY_MEDIUM_INCREASE
WC_DEPENDENCY_LATENCY_HIGH_INCREASE
WC_DEPENDENCY_LATENCY_MEDIUM_INCREASE
WC_RUNTIME_RESTART_COUNT_INCREASED
WC_RUNTIME_HEALTH_STATUS_CHANGED
WC_RUNTIME_IMAGE_CHANGED
WC_RUNTIME_PORTS_CHANGED
```

Tests should assert rule IDs so future report changes do not break auditability.

## 6. Test strategy

### Unit tests

- service identity derivation;
- healthy snapshot eligibility;
- snapshot retention;
- rule severity/materiality;
- latency thresholds;
- no-baseline result;
- LLM failure metadata;
- LLM validation failure metadata.

### Contract/fixture tests

- all golden fixtures validate against models;
- JSON report contains required fields;
- enum values stay stable.

### Markdown tests

Assert expected headings and content:

- `## What Changed?`
- `### Material Changes`
- `### Supporting Context`
- `### Other Changes`
- `AI advisory unavailable; deterministic analysis completed.`

### UI tests

Assert rendered HTML contains:

- change-count badge;
- no-baseline state;
- Material Changes section;
- Supporting Context section;
- collapsed Other Changes section;
- severity text labels;
- evidence refs;
- advisory unavailable/hidden note;
- expandable diagnostics.

### Integration test

`WC-001` live smoke:

- baseline created;
- HTTP 500 injected;
- dependency remains healthy;
- report persisted;
- UI/report verified;
- reset performed.

## 7. Done definition

v0.3 What Changed? is done when:

- spec docs are present;
- contracts and golden fixtures are present;
- fast tests pass;
- WC-001 live integration smoke passes;
- UI and reports render What Changed? consistently;
- no unsafe remediation/execution paths are introduced;
- existing FS-001/FS-002 coverage still passes;
- `make check`, `make verify`, and relevant live integration targets pass locally.
