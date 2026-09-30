"""add task approval quorum and decision audit

Revision ID: 0009_task_approval_quorum
Revises: 0008_operator_sessions
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_task_approval_quorum"
down_revision = "0008_operator_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("approval_quorum", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_check_constraint(
        "approval_quorum_range",
        "tasks",
        "approval_quorum BETWEEN 1 AND 10",
    )
    op.create_table(
        "task_approval_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operator_subject", sa.String(length=255), nullable=False),
        sa.Column("operator_role", sa.String(length=32), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["operator_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "operator_subject",
            name="uq_task_approval_decisions_task_operator",
        ),
    )
    op.create_index(
        "ix_task_approval_decisions_task_created",
        "task_approval_decisions",
        ["task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_approval_decisions_task_created",
        table_name="task_approval_decisions",
    )
    op.drop_table("task_approval_decisions")
    op.drop_constraint(
        "approval_quorum_range",
        "tasks",
        type_="check",
    )
    op.drop_column("tasks", "approval_quorum")
