"""add workflow runtime persistence

Revision ID: 0002_workflow_runtime
Revises: 0001_initial_core
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_workflow_runtime"
down_revision = "0001_initial_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_tasks_workflow_id"), "tasks", ["workflow_id"])
    op.create_foreign_key(
        op.f("fk_tasks_workflow_id_workflows"),
        "tasks",
        "workflows",
        ["workflow_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "workflows",
        sa.Column("temporal_workflow_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("temporal_run_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_workflows_temporal_workflow_id"),
        "workflows",
        ["temporal_workflow_id"],
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("temporal_workflow_id", sa.String(length=255), nullable=False),
        sa.Column("temporal_run_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'RUNNING'"), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_runs_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_runs_workflow_id_workflows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.UniqueConstraint("temporal_run_id", name=op.f("uq_runs_temporal_run_id")),
    )
    op.create_index(op.f("ix_runs_workflow_id"), "runs", ["workflow_id"])
    op.create_index(op.f("ix_runs_task_id"), "runs", ["task_id"])
    op.create_index(op.f("ix_runs_status"), "runs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_runs_status"), table_name="runs")
    op.drop_index(op.f("ix_runs_task_id"), table_name="runs")
    op.drop_index(op.f("ix_runs_workflow_id"), table_name="runs")
    op.drop_table("runs")
    op.drop_constraint(op.f("uq_workflows_temporal_workflow_id"), "workflows", type_="unique")
    op.drop_column("workflows", "completed_at")
    op.drop_column("workflows", "started_at")
    op.drop_column("workflows", "temporal_run_id")
    op.drop_column("workflows", "temporal_workflow_id")
    op.drop_constraint(op.f("fk_tasks_workflow_id_workflows"), "tasks", type_="foreignkey")
    op.drop_index(op.f("ix_tasks_workflow_id"), table_name="tasks")
    op.drop_column("tasks", "workflow_id")
