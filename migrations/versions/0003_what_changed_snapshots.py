"""Add healthy snapshot history for What Changed.

Revision ID: 0003_what_changed
Revises: 0002_lifecycle_eval
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_what_changed"
down_revision = "0002_lifecycle_eval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "healthy_snapshots",
        sa.Column("snapshot_id", sa.String(64), primary_key=True),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_identity", sa.JSON(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_healthy_snapshots_service_id", "healthy_snapshots", ["service_id"])
    op.create_index("ix_healthy_snapshots_observed_at", "healthy_snapshots", ["observed_at"])
    op.create_index("ix_healthy_snapshots_created_at", "healthy_snapshots", ["created_at"])


def downgrade() -> None:
    op.drop_table("healthy_snapshots")
