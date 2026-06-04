"""Backfill master data defaults for company listing

Revision ID: 20260603_005
Revises: 20260603_004
Create Date: 2026-06-03
"""

from alembic import op


revision = "20260603_005"
down_revision = "20260603_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE companies SET country = 'India' WHERE country IS NULL OR country = ''")
    op.execute("UPDATE companies SET working_days_per_week = 5 WHERE working_days_per_week IS NULL")
    op.execute("UPDATE companies SET fiscal_year_start_month = 4 WHERE fiscal_year_start_month IS NULL")
    op.execute("UPDATE companies SET default_timezone = 'Asia/Kolkata' WHERE default_timezone IS NULL OR default_timezone = ''")
    op.execute("UPDATE companies SET default_currency = 'INR' WHERE default_currency IS NULL OR default_currency = ''")
    op.execute("UPDATE branches SET country = 'India' WHERE country IS NULL OR country = ''")
    op.execute("UPDATE designations SET level = 1 WHERE level IS NULL")


def downgrade() -> None:
    pass
