"""Structured incident diagnosis output."""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
LLMStatus = Literal["not_requested", "available", "unavailable"]


class EvidenceItem(BaseModel):
    ref: str
    type: str
    source: str
    summary: str


class HypothesisItem(BaseModel):
    rank: int = Field(ge=1)
    cause: str
    confidence: float = Field(ge=0, le=1)
    evidence_refs: list[str] = Field(min_length=1)
    reasoning: str


class RecommendationItem(BaseModel):
    action_key: str
    title: str
    rationale: str
    requires_approval: bool = True
    allowed_by_policy: bool = False
    execution_enabled_in_mvp: Literal[False] = False
    executed: Literal[False] = False


class IncidentAnalysisJSON(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    incident_id: int
    service: str
    severity: Severity
    status: Literal["diagnosed"] = "diagnosed"
    summary: str
    current_status: str
    evidence: list[EvidenceItem]
    evidence_gaps: list[str] = Field(default_factory=list)
    hypotheses: list[HypothesisItem] = Field(min_length=1)
    recommendations: list[RecommendationItem] = Field(min_length=1)
    verification_plan: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)
    llm_status: LLMStatus = "not_requested"
    rules_only: bool = True


class LLMAnalysisResponse(BaseModel):
    summary: str = Field(min_length=1)
    hypotheses: list[HypothesisItem] = Field(min_length=1)
    recommendations: list[RecommendationItem] = Field(min_length=1)
    verification_plan: list[str] = Field(min_length=1)
    follow_up_actions: list[str] = Field(default_factory=list)
