"""Add failed lifecycle state and persisted evaluation history.

Revision ID: 0002_lifecycle_eval
Revises: 0001_mvp_baseline
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_lifecycle_eval"
down_revision = "0001_mvp_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("incidents") as batch:
        batch.drop_constraint("ck_incident_status", type_="check")
        batch.create_check_constraint(
            "ck_incident_status",
            "status IN ('new', 'analyzing', 'diagnosed', 'failed', 'resolved', 'closed')",
        )

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scenario_id", sa.String(64), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("prompt_versions", sa.JSON(), nullable=False),
        sa.Column("output_path", sa.String(2048)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_runs_scenario_id", "eval_runs", ["scenario_id"])
    op.create_index("ix_eval_runs_started_at", "eval_runs", ["started_at"])
    op.create_table(
        "eval_check_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "eval_run_id",
            sa.Integer(),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("expected", sa.JSON()),
        sa.Column("actual", sa.JSON()),
    )
    op.create_index("ix_eval_check_results_eval_run_id", "eval_check_results", ["eval_run_id"])


def downgrade() -> None:
    op.drop_table("eval_check_results")
    op.drop_table("eval_runs")
    with op.batch_alter_table("incidents") as batch:
        batch.drop_constraint("ck_incident_status", type_="check")
        batch.create_check_constraint(
            "ck_incident_status",
            "status IN ('new', 'analyzing', 'diagnosed', 'resolved', 'closed')",
        )
