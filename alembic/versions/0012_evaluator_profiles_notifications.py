"""add versioned evaluator profiles, criteria and operator notifications

Revision ID: 0012_evaluator_profiles_notifications
Revises: 0011_evaluation_quality_gates
Create Date: 2026-09-30
"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_evaluator_profiles_notifications"
down_revision = "0011_evaluation_quality_gates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scope_type", sa.String(length=32), server_default=sa.text("'GLOBAL'"), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("evaluator_kind", sa.String(length=32), server_default=sa.text("'RULE_BASED'"), nullable=False),
        sa.Column("evaluator_model", sa.String(length=255), nullable=True),
        sa.Column("min_score", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("min_confidence", sa.Float(), server_default=sa.text("0.75"), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=120), server_default=sa.text("'SYSTEM'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("min_score >= 0 AND min_score <= 1", name="evaluation_profile_min_score_range"),
        sa.CheckConstraint("min_confidence >= 0 AND min_confidence <= 1", name="evaluation_profile_min_confidence_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "name",
            "scope_type",
            "scope_id",
            "version",
            name="uq_evaluation_profiles_name_scope_version",
        ),
    )
    op.create_index(
        "ix_evaluation_profiles_scope_status",
        "evaluation_profiles",
        ["scope_type", "scope_id", "status"],
    )

    op.create_table(
        "evaluation_criteria",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), server_default=sa.text("'PRESENCE'"), nullable=False),
        sa.Column("weight", sa.Float(), server_default=sa.text("1.0"), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weight > 0", name="evaluation_criterion_weight_positive"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["evaluation_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "key", name="uq_evaluation_criteria_profile_key"),
    )
    op.create_index("ix_evaluation_criteria_profile_id", "evaluation_criteria", ["profile_id"])

    default_profile_id = uuid.uuid4()
    op.bulk_insert(
        sa.table(
            "evaluation_profiles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String(length=120)),
            sa.column("scope_type", sa.String(length=32)),
            sa.column("scope_id", postgresql.UUID(as_uuid=True)),
            sa.column("version", sa.Integer()),
            sa.column("status", sa.String(length=32)),
            sa.column("evaluator_kind", sa.String(length=32)),
            sa.column("evaluator_model", sa.String(length=255)),
            sa.column("min_score", sa.Float()),
            sa.column("min_confidence", sa.Float()),
            sa.column("system_prompt", sa.Text()),
            sa.column("created_by", sa.String(length=120)),
        ),
        [{
            "id": default_profile_id,
            "name": "default-quality",
            "scope_type": "GLOBAL",
            "scope_id": None,
            "version": 1,
            "status": "ACTIVE",
            "evaluator_kind": "RULE_BASED",
            "evaluator_model": None,
            "min_score": 1.0,
            "min_confidence": 0.75,
            "system_prompt": None,
            "created_by": "SYSTEM",
        }],
    )

    criteria = (
        ("structured_output", "The execution output must use the declared structured contract.", "STRUCTURE"),
        ("summary_present", "A non-empty execution summary must be present.", "PRESENCE"),
        ("result_present", "The execution must contain non-empty structured result data.", "PRESENCE"),
        ("artifact_present", "A non-empty artifact must be present.", "PRESENCE"),
    )
    op.bulk_insert(
        sa.table(
            "evaluation_criteria",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("profile_id", postgresql.UUID(as_uuid=True)),
            sa.column("key", sa.String(length=120)),
            sa.column("description", sa.Text()),
            sa.column("kind", sa.String(length=32)),
            sa.column("weight", sa.Float()),
            sa.column("required", sa.Boolean()),
            sa.column("position", sa.Integer()),
            sa.column("status", sa.String(length=32)),
        ),
        [
            {
                "id": uuid.uuid4(),
                "profile_id": default_profile_id,
                "key": key,
                "description": description,
                "kind": kind,
                "weight": 1.0,
                "required": True,
                "position": position,
                "status": "ACTIVE",
            }
            for position, (key, description, kind) in enumerate(criteria)
        ],
    )

    op.add_column(
        "evaluations",
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "evaluations",
        sa.Column("profile_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.create_foreign_key(
        "fk_evaluations_profile_id_evaluation_profiles",
        "evaluations",
        "evaluation_profiles",
        ["profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_evaluations_profile_id", "evaluations", ["profile_id"])
    op.execute(
        sa.text(
            "UPDATE evaluations SET profile_id = :profile_id, profile_version = 1 "
            "WHERE profile_id IS NULL"
        ),
        {"profile_id": default_profile_id},
    )

    op.create_table(
        "operator_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(length=16), server_default=sa.text("'WARNING'"), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'UNREAD'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_id"], ["evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operator_notifications_project_status_created",
        "operator_notifications",
        ["project_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operator_notifications_project_status_created",
        table_name="operator_notifications",
    )
    op.drop_table("operator_notifications")

    op.drop_index("ix_evaluations_profile_id", table_name="evaluations")
    op.drop_constraint(
        "fk_evaluations_profile_id_evaluation_profiles",
        "evaluations",
        type_="foreignkey",
    )
    op.drop_column("evaluations", "profile_version")
    op.drop_column("evaluations", "profile_id")

    op.drop_index("ix_evaluation_criteria_profile_id", table_name="evaluation_criteria")
    op.drop_table("evaluation_criteria")

    op.drop_index("ix_evaluation_profiles_scope_status", table_name="evaluation_profiles")
    op.drop_table("evaluation_profiles")
