"""add user phone and password reset tokens

Revision ID: 0005_user_phone_password_reset
Revises: 0004_job_freshness_cv_context
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0005_user_phone_password_reset"
down_revision = "0004_job_freshness_cv_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    tables = set(inspector.get_table_names())

    if "phone" not in user_cols:
        op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))

    if "password_reset_tokens" not in tables:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = {idx["name"] for idx in inspector.get_indexes("password_reset_tokens")} if "password_reset_tokens" in set(inspector.get_table_names()) else set()
    if "ix_password_reset_tokens_id" not in indexes:
        op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"], unique=False)
    if "ix_password_reset_tokens_token_hash" not in indexes:
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "phone")
