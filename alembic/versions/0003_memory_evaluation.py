"""add memory evidence evaluations and repair attempts

Revision ID: 0003_memory_evaluation
Revises: 0002_workflow_runtime
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_memory_evaluation"
down_revision = "0002_workflow_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("source_type", sa.String(length=64), server_default=sa.text("'SYSTEM'"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("importance BETWEEN 0 AND 100", name=op.f("ck_memory_items_importance")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_memory_items_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_memory_items_task_id_tasks"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_items")),
    )
    op.create_index(op.f("ix_memory_items_project_id"), "memory_items", ["project_id"])
    op.create_index(op.f("ix_memory_items_task_id"), "memory_items", ["task_id"])
    op.create_index(op.f("ix_memory_items_kind"), "memory_items", ["kind"])
    op.create_index(op.f("ix_memory_items_created_at"), "memory_items", ["created_at"])

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name=op.f("ck_evidence_confidence")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_evidence_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_evidence_task_id_tasks"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence")),
    )
    op.create_index(op.f("ix_evidence_project_id"), "evidence", ["project_id"])
    op.create_index(op.f("ix_evidence_task_id"), "evidence", ["task_id"])
    op.create_index(op.f("ix_evidence_type"), "evidence", ["evidence_type"])
    op.create_index(op.f("ix_evidence_created_at"), "evidence", ["created_at"])

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evaluator_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "criteria",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "findings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 1)",
            name=op.f("ck_evaluations_score"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_evaluations_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_evaluations_task_id_tasks"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_evaluations_run_id_runs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluations")),
    )
    op.create_index(op.f("ix_evaluations_project_id"), "evaluations", ["project_id"])
    op.create_index(op.f("ix_evaluations_task_id"), "evaluations", ["task_id"])
    op.create_index(op.f("ix_evaluations_run_id"), "evaluations", ["run_id"])
    op.create_index(op.f("ix_evaluations_status"), "evaluations", ["status"])

    op.create_table(
        "repair_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=False),
        sa.Column("corrective_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PLANNED'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt > 0", name=op.f("ck_repair_attempts_attempt")),
        sa.ForeignKeyConstraint(
            ["evaluation_id"], ["evaluations.id"], name=op.f("fk_repair_attempts_evaluation_id_evaluations"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_repair_attempts_task_id_tasks"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repair_attempts")),
    )
    op.create_index(op.f("ix_repair_attempts_evaluation_id"), "repair_attempts", ["evaluation_id"])
    op.create_index(op.f("ix_repair_attempts_task_id"), "repair_attempts", ["task_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_repair_attempts_task_id"), table_name="repair_attempts")
    op.drop_index(op.f("ix_repair_attempts_evaluation_id"), table_name="repair_attempts")
    op.drop_table("repair_attempts")

    op.drop_index(op.f("ix_evaluations_status"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_run_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_task_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_project_id"), table_name="evaluations")
    op.drop_table("evaluations")

    op.drop_index(op.f("ix_evidence_created_at"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_type"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_task_id"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_project_id"), table_name="evidence")
    op.drop_table("evidence")

    op.drop_index(op.f("ix_memory_items_created_at"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_kind"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_task_id"), table_name="memory_items")
    op.drop_index(op.f("ix_memory_items_project_id"), table_name="memory_items")
    op.drop_table("memory_items")
