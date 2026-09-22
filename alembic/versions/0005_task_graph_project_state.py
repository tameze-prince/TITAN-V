"""add task graph and project state persistence

Revision ID: 0005_task_graph_project_state
Revises: 0004_intent_compiler
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_task_graph_project_state"
down_revision = "0004_intent_compiler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'ACTIVE'"),
            nullable=False,
        ),
        sa.Column(
            "phase",
            sa.String(length=64),
            server_default=sa.text("'DISCOVERY'"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "state_json",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_states_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_states")),
        sa.UniqueConstraint("project_id", name=op.f("uq_project_states_project_id")),
    )
    op.create_index(op.f("ix_project_states_project_id"), "project_states", ["project_id"])

    op.create_table(
        "task_graphs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intent_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'READY'"),
            nullable=False,
        ),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column(
            "plan_json",
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
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["intent_record_id"],
            ["intent_records.id"],
            name=op.f("fk_task_graphs_intent_record_id_intent_records"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_task_graphs_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_graphs")),
        sa.UniqueConstraint(
            "project_id",
            "version",
            name=op.f("uq_task_graphs_project_version"),
        ),
    )
    op.create_index(op.f("ix_task_graphs_project_id"), "task_graphs", ["project_id"])
    op.create_index(op.f("ix_task_graphs_intent_record_id"), "task_graphs", ["intent_record_id"])
    op.create_index(op.f("ix_task_graphs_status"), "task_graphs", ["status"])

    op.add_column(
        "tasks",
        sa.Column(
            "task_graph_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column("tasks", sa.Column("task_key", sa.String(length=120), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "required_capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_tasks_task_graph_id_task_graphs"),
        "tasks",
        "task_graphs",
        ["task_graph_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        op.f("uq_tasks_task_graph_task_key"),
        "tasks",
        ["task_graph_id", "task_key"],
    )
    op.create_index(op.f("ix_tasks_task_graph_id"), "tasks", ["task_graph_id"])
    op.create_index(op.f("ix_tasks_task_key"), "tasks", ["task_key"])

    op.add_column(
        "workflows",
        sa.Column(
            "task_graph_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        op.f("fk_workflows_task_graph_id_task_graphs"),
        "workflows",
        "task_graphs",
        ["task_graph_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_workflows_task_graph_id"), "workflows", ["task_graph_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_workflows_task_graph_id"), table_name="workflows")
    op.drop_constraint(
        op.f("fk_workflows_task_graph_id_task_graphs"),
        "workflows",
        type_="foreignkey",
    )
    op.drop_column("workflows", "task_graph_id")

    op.drop_index(op.f("ix_tasks_task_key"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_task_graph_id"), table_name="tasks")
    op.drop_constraint(
        op.f("uq_tasks_task_graph_task_key"),
        "tasks",
        type_="unique",
    )
    op.drop_constraint(
        op.f("fk_tasks_task_graph_id_task_graphs"),
        "tasks",
        type_="foreignkey",
    )
    op.drop_column("tasks", "required_capabilities")
    op.drop_column("tasks", "position")
    op.drop_column("tasks", "task_key")
    op.drop_column("tasks", "task_graph_id")

    op.drop_index(op.f("ix_task_graphs_status"), table_name="task_graphs")
    op.drop_index(op.f("ix_task_graphs_intent_record_id"), table_name="task_graphs")
    op.drop_index(op.f("ix_task_graphs_project_id"), table_name="task_graphs")
    op.drop_table("task_graphs")

    op.drop_index(op.f("ix_project_states_project_id"), table_name="project_states")
    op.drop_table("project_states")
