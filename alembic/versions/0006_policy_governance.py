"""add policy versions and governance decision audit

Revision ID: 0006_policy_governance
Revises: 0005_task_graph_project_state
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_policy_governance"
down_revision = "0005_task_graph_project_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column(
            "definition_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.String(length=120),
            server_default=sa.text("'SYSTEM'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policy_versions")),
        sa.UniqueConstraint(
            "scope_type",
            "scope_id",
            "policy_name",
            "version",
            name="uq_policy_versions_scope_name_version",
        ),
    )
    op.create_index(
        op.f("ix_policy_versions_scope_policy"),
        "policy_versions",
        ["scope_type", "scope_id", "policy_name"],
    )
    op.create_index(
        op.f("ix_policy_versions_status"),
        "policy_versions",
        ["status"],
    )

    op.create_table(
        "governance_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("requires_human", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "checks_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "context_json",
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
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_governance_decisions_project_id_projects"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
            name=op.f("fk_governance_decisions_workflow_id_workflows"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_governance_decisions_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name=op.f("fk_governance_decisions_policy_version_id_policy_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_governance_decisions")),
    )
    op.create_index(
        op.f("ix_governance_decisions_project_id"),
        "governance_decisions",
        ["project_id"],
    )
    op.create_index(
        op.f("ix_governance_decisions_workflow_id"),
        "governance_decisions",
        ["workflow_id"],
    )
    op.create_index(
        op.f("ix_governance_decisions_policy_version_id"),
        "governance_decisions",
        ["policy_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_governance_decisions_policy_version_id"),
        table_name="governance_decisions",
    )
    op.drop_index(
        op.f("ix_governance_decisions_workflow_id"),
        table_name="governance_decisions",
    )
    op.drop_index(
        op.f("ix_governance_decisions_project_id"),
        table_name="governance_decisions",
    )
    op.drop_table("governance_decisions")

    op.drop_index(
        op.f("ix_policy_versions_status"),
        table_name="policy_versions",
    )
    op.drop_index(
        op.f("ix_policy_versions_scope_policy"),
        table_name="policy_versions",
    )
    op.drop_table("policy_versions")
