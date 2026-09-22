"""add intent compilation persistence

Revision ID: 0004_intent_compiler
Revises: 0003_memory_evaluation
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_intent_compiler"
down_revision = "0003_memory_evaluation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "intent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_intent", sa.Text(), nullable=False),
        sa.Column(
            "compiled",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'COMPILED'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_intent_records_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intent_records")),
    )
    op.create_index(op.f("ix_intent_records_project_id"), "intent_records", ["project_id"])
    op.create_index(op.f("ix_intent_records_created_at"), "intent_records", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_intent_records_created_at"), table_name="intent_records")
    op.drop_index(op.f("ix_intent_records_project_id"), table_name="intent_records")
    op.drop_table("intent_records")
