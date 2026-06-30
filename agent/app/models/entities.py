"""Core SQLAlchemy entities for IncidentPilot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent.app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    runtime: Mapped[str] = mapped_column(String(32), default="docker")
    container_name: Mapped[str] = mapped_column(String(255), unique=True)
    health_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, default=30)
    criticality: Mapped[str] = mapped_column(String(32), default="medium")
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    health_checks: Mapped[list[HealthCheckResult]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    deployment_events: Mapped[list[DeploymentEvent]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    incidents: Mapped[list[Incident]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )


class HealthCheckResult(Base):
    __tablename__ = "health_check_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32))
    http_status_code: Mapped[int | None] = mapped_column(nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    service: Mapped[Service] = relationship(back_populates="health_checks")


class DeploymentEvent(Base):
    __tablename__ = "deployment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    service: Mapped[Service] = relationship(back_populates="deployment_events")


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'analyzing', 'diagnosed', 'resolved', 'closed')",
            name="ck_incident_status",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incident_severity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    severity: Mapped[str] = mapped_column(String(32), default="medium")
    trigger_type: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    diagnosed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    llm_status: Mapped[str | None] = mapped_column(String(64), nullable=True)

    service: Mapped[Service] = relationship(back_populates="incidents")
    evidence: Mapped[list[IncidentEvidence]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    hypotheses: Mapped[list[Hypothesis]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="Hypothesis.rank",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    reports: Mapped[list[IncidentReport]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON, nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    incident: Mapped[Incident] = relationship(back_populates="evidence")


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    __table_args__ = (
        CheckConstraint("rank > 0", name="ck_hypothesis_positive_rank"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_hypothesis_confidence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    cause: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    reasoning: Mapped[str] = mapped_column(Text)

    incident: Mapped[Incident] = relationship(back_populates="hypotheses")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "execution_enabled_in_mvp = false",
            name="ck_recommendation_mvp_execution_disabled",
        ),
        CheckConstraint(
            "executed = false",
            name="ck_recommendation_never_executed",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    action_key: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(512))
    rationale: Mapped[str] = mapped_column(Text)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    allowed_by_policy: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_enabled_in_mvp: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    executed: Mapped[bool] = mapped_column(Boolean, default=False)

    incident: Mapped[Incident] = relationship(back_populates="recommendations")


class IncidentReport(Base):
    __tablename__ = "incident_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    markdown: Mapped[str] = mapped_column(Text)
    json_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    incident: Mapped[Incident] = relationship(back_populates="reports")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), index=True
    )
    workflow_version: Mapped[str] = mapped_column(String(64))
    prompt_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="agent_runs")
