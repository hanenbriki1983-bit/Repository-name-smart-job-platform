"""add company website url to jobs

Revision ID: 0007_job_company_website
Revises: 0006_email_notifications_saved_searches
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0007_job_company_website"
down_revision = "0006_email_notifications_saved_searches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    job_cols = {col["name"] for col in inspector.get_columns("jobs")}
    if "company_website_url" not in job_cols:
        op.add_column("jobs", sa.Column("company_website_url", sa.String(length=600), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "company_website_url")
