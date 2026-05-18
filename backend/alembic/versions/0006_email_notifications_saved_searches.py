"""add email verification and saved searches

Revision ID: 0006_email_notifications_saved_searches
Revises: 0005_user_phone_password_reset
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_email_notifications_saved_searches"
down_revision = "0005_user_phone_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    tables = set(inspector.get_table_names())

    if "email_verified" not in user_cols:
        op.add_column("users", sa.Column("email_verified", sa.Integer(), nullable=False, server_default="0"))
    if "email_notifications_enabled" not in user_cols:
        op.add_column("users", sa.Column("email_notifications_enabled", sa.Integer(), nullable=False, server_default="0"))

    if "email_verification_tokens" not in tables:
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if "saved_searches" not in tables:
        op.create_table(
            "saved_searches",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("search_text", sa.String(length=255), nullable=True),
            sa.Column("country", sa.String(length=120), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("job_title", sa.String(length=160), nullable=True),
            sa.Column("work_mode", sa.String(length=40), nullable=True),
            sa.Column("job_type", sa.String(length=40), nullable=True),
            sa.Column("experience_level", sa.String(length=40), nullable=True),
            sa.Column("radius_km", sa.Integer(), nullable=False, server_default="20"),
            sa.Column("email_notifications_enabled", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_notified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if "email_verification_tokens" in set(inspector.get_table_names()):
        idx = {row["name"] for row in inspector.get_indexes("email_verification_tokens")}
        if "ix_email_verification_tokens_id" not in idx:
            op.create_index("ix_email_verification_tokens_id", "email_verification_tokens", ["id"], unique=False)
        if "ix_email_verification_tokens_token_hash" not in idx:
            op.create_index("ix_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"], unique=True)
    if "saved_searches" in set(inspector.get_table_names()):
        idx = {row["name"] for row in inspector.get_indexes("saved_searches")}
        if "ix_saved_searches_id" not in idx:
            op.create_index("ix_saved_searches_id", "saved_searches", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saved_searches_id", table_name="saved_searches")
    op.drop_table("saved_searches")

    op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")

    op.drop_column("users", "email_notifications_enabled")
    op.drop_column("users", "email_verified")
