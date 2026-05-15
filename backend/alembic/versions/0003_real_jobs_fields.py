"""add fields for real job integration

Revision ID: 0003_real_jobs_fields
Revises: 0002_user_preferences
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_real_jobs_fields"
down_revision = "0002_user_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_job_title", sa.String(length=160), nullable=True))

    op.add_column("jobs", sa.Column("source", sa.String(length=40), nullable=False, server_default="seed"))
    op.add_column("jobs", sa.Column("external_id", sa.String(length=160), nullable=True))
    op.add_column("jobs", sa.Column("country", sa.String(length=120), nullable=True))
    op.add_column("jobs", sa.Column("city", sa.String(length=120), nullable=True))
    op.add_column("jobs", sa.Column("work_mode", sa.String(length=40), nullable=True))
    op.add_column("jobs", sa.Column("job_type", sa.String(length=40), nullable=True))
    op.add_column("jobs", sa.Column("apply_url", sa.String(length=600), nullable=True))
    op.add_column("jobs", sa.Column("skills_csv", sa.Text(), nullable=True))
    op.create_index("ix_jobs_external_id", "jobs", ["external_id"], unique=False)

    op.execute("UPDATE jobs SET source = 'seed' WHERE source IS NULL")


def downgrade() -> None:
    op.drop_column("users", "preferred_job_title")
    op.drop_index("ix_jobs_external_id", table_name="jobs")
    op.drop_column("jobs", "skills_csv")
    op.drop_column("jobs", "apply_url")
    op.drop_column("jobs", "job_type")
    op.drop_column("jobs", "work_mode")
    op.drop_column("jobs", "city")
    op.drop_column("jobs", "country")
    op.drop_column("jobs", "external_id")
    op.drop_column("jobs", "source")
