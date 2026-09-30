"""add resource grants and operator delegations

Revision ID: 0010_resource_rbac_delegation
Revises: 0009_task_approval_quorum
Create Date: 2026-09-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_resource_rbac_delegation"
down_revision = "0009_task_approval_quorum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_resource_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("permissions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["operator_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operator_resource_grants_user_resource",
        "operator_resource_grants",
        ["user_id", "resource_type", "resource_id", "status"],
    )

    op.create_table(
        "operator_delegations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegator_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delegatee_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("permissions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_subject", sa.String(length=255), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["delegator_user_id"], ["operator_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delegatee_user_id"], ["operator_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operator_delegations_delegatee_resource",
        "operator_delegations",
        ["delegatee_user_id", "resource_type", "resource_id", "status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operator_delegations_delegatee_resource",
        table_name="operator_delegations",
    )
    op.drop_table("operator_delegations")
    op.drop_index(
        "ix_operator_resource_grants_user_resource",
        table_name="operator_resource_grants",
    )
    op.drop_table("operator_resource_grants")
