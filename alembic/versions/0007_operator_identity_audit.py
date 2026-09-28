"""persist operator identity subject for audit events

Revision ID: 0007_operator_identity_audit
Revises: 0006_policy_governance
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_operator_identity_audit"
down_revision = "0006_policy_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("actor_subject", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_events_actor_subject_occurred_at",
        "events",
        ["actor_subject", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_events_actor_subject_occurred_at",
        table_name="events",
    )
    op.drop_column("events", "actor_subject")
