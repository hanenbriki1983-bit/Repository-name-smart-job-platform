"""add user job preferences

Revision ID: 0002_user_preferences
Revises: 0001_initial_schema
Create Date: 2026-05-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_user_preferences"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_country", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("preferred_city", sa.String(length=120), nullable=True))
    op.add_column("users", sa.Column("preferred_work_mode", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("preferred_job_type", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("preferred_experience_level", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "preferred_experience_level")
    op.drop_column("users", "preferred_job_type")
    op.drop_column("users", "preferred_work_mode")
    op.drop_column("users", "preferred_city")
    op.drop_column("users", "preferred_country")
