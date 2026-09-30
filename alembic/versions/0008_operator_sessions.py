"""add operator users, sessions and OIDC authorization state

Revision ID: 0008_operator_sessions
Revises: 0007_operator_identity_audit
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_operator_sessions"
down_revision = "0007_operator_identity_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), server_default=sa.text("'viewer'"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject", name="uq_operator_users_issuer_subject"),
    )
    op.create_index(
        "ix_operator_users_role_status",
        "operator_users",
        ["role", "status"],
    )

    op.create_table(
        "operator_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_from_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["rotated_from_session_id"], ["operator_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["operator_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_operator_sessions_user_expires",
        "operator_sessions",
        ["user_id", "expires_at"],
    )
    op.create_index(
        "ix_operator_sessions_revoked_expires",
        "operator_sessions",
        ["revoked_at", "expires_at"],
    )

    op.create_table(
        "oidc_authorization_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state_hash", sa.String(length=128), nullable=False),
        sa.Column("code_verifier", sa.String(length=255), nullable=False),
        sa.Column("nonce", sa.String(length=255), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2000), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index(
        "ix_oidc_authorization_states_expires",
        "oidc_authorization_states",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_oidc_authorization_states_expires",
        table_name="oidc_authorization_states",
    )
    op.drop_table("oidc_authorization_states")
    op.drop_index(
        "ix_operator_sessions_revoked_expires",
        table_name="operator_sessions",
    )
    op.drop_index(
        "ix_operator_sessions_user_expires",
        table_name="operator_sessions",
    )
    op.drop_table("operator_sessions")
    op.drop_index(
        "ix_operator_users_role_status",
        table_name="operator_users",
    )
    op.drop_table("operator_users")
