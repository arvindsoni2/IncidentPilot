"""MVP schema baseline.

Revision ID: 0001_mvp_baseline
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_mvp_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("runtime", sa.String(32), nullable=False),
        sa.Column("container_name", sa.String(255), nullable=False),
        sa.Column("health_url", sa.String(2048)),
        sa.Column("polling_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("criticality", sa.String(32), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("container_name"),
    )
    op.create_index("ix_services_name", "services", ["name"], unique=True)

    op.create_table(
        "health_check_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("http_status_code", sa.Integer()),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("error", sa.Text()),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_health_check_results_service_id", "health_check_results", ["service_id"])
    op.create_index("ix_health_check_results_checked_at", "health_check_results", ["checked_at"])

    op.create_table(
        "deployment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("image_name", sa.String(512)),
        sa.Column("image_tag", sa.String(255)),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployment_events_service_id", "deployment_events", ["service_id"])
    op.create_index("ix_deployment_events_recorded_at", "deployment_events", ["recorded_at"])

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("trigger_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("diagnosed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("llm_status", sa.String(64)),
        sa.CheckConstraint(
            "status IN ('new', 'analyzing', 'diagnosed', 'resolved', 'closed')",
            name="ck_incident_status",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_incident_severity",
        ),
    )
    op.create_index("ix_incidents_service_id", "incidents", ["service_id"])
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_detected_at", "incidents", ["detected_at"])

    _create_incident_children()


def _create_incident_children() -> None:
    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("raw_payload", sa.JSON()),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_evidence_incident_id", "incident_evidence", ["incident_id"])
    op.create_index("ix_incident_evidence_type", "incident_evidence", ["type"])

    op.create_table(
        "hypotheses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.CheckConstraint("rank > 0", name="ck_hypothesis_positive_rank"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_hypothesis_confidence"),
    )
    op.create_index("ix_hypotheses_incident_id", "hypotheses", ["incident_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_key", sa.String(128), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("allowed_by_policy", sa.Boolean(), nullable=False),
        sa.Column("execution_enabled_in_mvp", sa.Boolean(), nullable=False),
        sa.Column("executed", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "execution_enabled_in_mvp = false",
            name="ck_recommendation_mvp_execution_disabled",
        ),
        sa.CheckConstraint("executed = false", name="ck_recommendation_never_executed"),
    )
    op.create_index("ix_recommendations_incident_id", "recommendations", ["incident_id"])

    op.create_table(
        "incident_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("json_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_reports_incident_id", "incident_reports", ["incident_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_version", sa.String(64), nullable=False),
        sa.Column("prompt_versions", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(255)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_agent_runs_incident_id", "agent_runs", ["incident_id"])


def downgrade() -> None:
    for table in (
        "agent_runs",
        "incident_reports",
        "recommendations",
        "hypotheses",
        "incident_evidence",
        "incidents",
        "deployment_events",
        "health_check_results",
        "services",
    ):
        op.drop_table(table)
