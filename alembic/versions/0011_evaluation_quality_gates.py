"""harden evidence, evaluation lineage and bounded repair lifecycle

Revision ID: 0011_evaluation_quality_gates
Revises: 0010_resource_rbac_delegation
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_evaluation_quality_gates"
down_revision = "0010_resource_rbac_delegation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluations", sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("evaluations", sa.Column("evaluator_version", sa.String(length=32), server_default=sa.text("'1.0'"), nullable=False))
    op.add_column("evaluations", sa.Column("producer_agent", sa.String(length=120), nullable=True))
    op.add_column("evaluations", sa.Column("independent", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("evaluations", sa.Column("decision", sa.String(length=32), server_default=sa.text("'NEEDS_REVIEW'"), nullable=False))
    op.add_column("evaluations", sa.Column("confidence", sa.Float(), server_default=sa.text("1.0"), nullable=False))
    op.add_column("evaluations", sa.Column("repair_attempt", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_foreign_key(
        op.f("fk_evaluations_artifact_id_artifacts"),
        "evaluations",
        "artifacts",
        ["artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint("evaluation_confidence_range", "evaluations", "confidence >= 0 AND confidence <= 1")
    op.create_check_constraint("evaluation_repair_attempt_range", "evaluations", "repair_attempt >= 0")
    op.create_index("ix_evaluations_artifact_id", "evaluations", ["artifact_id"])

    op.add_column("evidence", sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("evidence", sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_evidence_evaluation_id_evaluations"),
        "evidence",
        "evaluations",
        ["evaluation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_evidence_artifact_id_artifacts"),
        "evidence",
        "artifacts",
        ["artifact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_evidence_evaluation_id", "evidence", ["evaluation_id"])
    op.create_index("ix_evidence_artifact_id", "evidence", ["artifact_id"])

    op.add_column("repair_attempts", sa.Column("max_attempts", sa.Integer(), server_default=sa.text("2"), nullable=False))
    op.add_column("repair_attempts", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("repair_max_attempts_range", "repair_attempts", "max_attempts > 0")


def downgrade() -> None:
    op.drop_constraint("repair_max_attempts_range", "repair_attempts", type_="check")
    op.drop_column("repair_attempts", "started_at")
    op.drop_column("repair_attempts", "max_attempts")

    op.drop_index("ix_evidence_artifact_id", table_name="evidence")
    op.drop_index("ix_evidence_evaluation_id", table_name="evidence")
    op.drop_constraint(op.f("fk_evidence_artifact_id_artifacts"), "evidence", type_="foreignkey")
    op.drop_constraint(op.f("fk_evidence_evaluation_id_evaluations"), "evidence", type_="foreignkey")
    op.drop_column("evidence", "artifact_id")
    op.drop_column("evidence", "evaluation_id")

    op.drop_index("ix_evaluations_artifact_id", table_name="evaluations")
    op.drop_constraint(op.f("fk_evaluations_artifact_id_artifacts"), "evaluations", type_="foreignkey")
    op.drop_constraint("evaluation_repair_attempt_range", "evaluations", type_="check")
    op.drop_constraint("evaluation_confidence_range", "evaluations", type_="check")
    op.drop_column("evaluations", "repair_attempt")
    op.drop_column("evaluations", "confidence")
    op.drop_column("decision", "independent") if False else None
    op.drop_column("evaluations", "independent")
    op.drop_column("evaluations", "producer_agent")
    op.drop_column("evaluations", "evaluator_version")
    op.drop_column("evaluations", "artifact_id")
