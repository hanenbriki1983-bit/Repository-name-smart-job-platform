"""add job freshness and cv context fields

Revision ID: 0004_job_freshness_cv_context
Revises: 0003_real_jobs_fields
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0004_job_freshness_cv_context"
down_revision = "0003_real_jobs_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    job_cols = {col["name"] for col in inspector.get_columns("jobs")}
    user_cols = {col["name"] for col in inspector.get_columns("users")}

    if "company_logo_url" not in job_cols:
        op.add_column("jobs", sa.Column("company_logo_url", sa.String(length=600), nullable=True))
    if "posted_date" not in job_cols:
        op.add_column("jobs", sa.Column("posted_date", sa.DateTime(), nullable=True))
    if "last_updated" not in job_cols:
        op.add_column("jobs", sa.Column("last_updated", sa.DateTime(), nullable=True))

    if "cv_candidate_name" not in user_cols:
        op.add_column("users", sa.Column("cv_candidate_name", sa.String(length=160), nullable=True))
    if "cv_skills_csv" not in user_cols:
        op.add_column("users", sa.Column("cv_skills_csv", sa.Text(), nullable=True))
    if "cv_experience_summary" not in user_cols:
        op.add_column("users", sa.Column("cv_experience_summary", sa.Text(), nullable=True))
    if "cv_preferred_keywords_csv" not in user_cols:
        op.add_column("users", sa.Column("cv_preferred_keywords_csv", sa.Text(), nullable=True))

    op.execute("UPDATE jobs SET posted_date = created_at WHERE posted_date IS NULL")
    op.execute("UPDATE jobs SET last_updated = COALESCE(last_updated, CURRENT_TIMESTAMP)")


def downgrade() -> None:
    op.drop_column("users", "cv_preferred_keywords_csv")
    op.drop_column("users", "cv_experience_summary")
    op.drop_column("users", "cv_skills_csv")
    op.drop_column("users", "cv_candidate_name")

    op.drop_column("jobs", "last_updated")
    op.drop_column("jobs", "posted_date")
    op.drop_column("jobs", "company_logo_url")
