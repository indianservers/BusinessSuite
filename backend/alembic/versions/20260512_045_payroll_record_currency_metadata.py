"""add payroll record currency metadata

Revision ID: 20260512_045
Revises: 20260512_044
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_045"
down_revision = "20260512_044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payroll_records", sa.Column("salary_currency", sa.String(length=3), nullable=True))
    op.add_column("payroll_records", sa.Column("exchange_rate", sa.Numeric(14, 6), nullable=True))
    op.add_column("payroll_records", sa.Column("converted_currency", sa.String(length=3), nullable=True))


def downgrade() -> None:
    op.drop_column("payroll_records", "converted_currency")
    op.drop_column("payroll_records", "exchange_rate")
    op.drop_column("payroll_records", "salary_currency")
