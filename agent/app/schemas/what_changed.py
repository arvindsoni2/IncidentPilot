"""Validated contracts for deterministic healthy-baseline comparison."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class LlmAdvisoryStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    NOT_ATTEMPTED = "not_attempted"
    ACCEPTED = "accepted"
    FAILED = "failed"
    VALIDATION_FAILED = "validation_failed"


class LlmFailureReason(str, Enum):
    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"
    EMPTY_RESPONSE = "empty_response"
    POLICY_BLOCKED = "policy_blocked"
    UNKNOWN = "unknown"


class ComparisonFailureReason(str, Enum):
    BASELINE_LOAD_FAILED = "baseline_load_failed"
    INCIDENT_EVIDENCE_INCOMPLETE = "incident_evidence_incomplete"
    SNAPSHOT_SCHEMA_INVALID = "snapshot_schema_invalid"
    RULE_ENGINE_ERROR = "rule_engine_error"
    WHAT_CHANGED_RENDER_ERROR = "what_changed_render_error"
    UNKNOWN = "unknown"


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
    rank: int = Field(ge=0)
    before: EvidenceValue
    after: EvidenceValue
    impact: str
    why_it_matters: str
    evidence_refs: list[str] = Field(min_length=1)
    timestamp: datetime
    rule_id: str
    ai_advisory_note: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class WhatChangedCounts(BaseModel):
    material: int = Field(ge=0)
    supporting_context: int = Field(ge=0)
    other: int = Field(ge=0)
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "WhatChangedCounts":
        if self.total != self.material + self.supporting_context + self.other:
            raise ValueError("total must equal grouped counts")
        return self


class LlmAdvisoryMetadata(BaseModel):
    status: LlmAdvisoryStatus
    configured: bool
    attempted: bool
    retry_attempted: bool = False
    model: str | None = None
    failed: bool = False
    failure_reason: LlmFailureReason | None = None
    validation_failed: bool = False
    validation_reason: str | None = None
    advisory_hidden: bool = False
    advisory_accepted: bool = False
    fallback_used: Literal["deterministic_rule_summary"] | None = None
    advisory_is_authoritative: Literal[False] = False
    generated_at: datetime | None = None


class ComparisonFailureMetadata(BaseModel):
    failed: bool = False
    reason: ComparisonFailureReason | None = None
    message: str | None = None
    failed_at: datetime | None = None
    normal_diagnosis_continued: bool = True
    fallback_used: Literal["normal_diagnosis_only"] | None = None
    error_ref: str | None = None


class WhatChangedDiagnostics(BaseModel):
    comparison_failure: ComparisonFailureMetadata | None = None
    collection_window_seconds: float | None = None
    required_dependencies: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    redaction_applied: bool = True
    safe_metadata_fields: list[str] = Field(default_factory=list)


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


class WhatChangedAdvisoryResponse(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    per_change_notes: dict[str, str] = Field(default_factory=dict)


def empty_counts() -> WhatChangedCounts:
    return WhatChangedCounts(material=0, supporting_context=0, other=0, total=0)
