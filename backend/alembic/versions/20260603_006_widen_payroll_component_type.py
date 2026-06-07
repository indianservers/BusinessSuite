"""Widen payroll component type for employer contributions

Revision ID: 20260603_006
Revises: 20260603_005
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260603_006"
down_revision = "20260603_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("payroll_components") as batch_op:
        batch_op.alter_column(
            "component_type",
            existing_type=sa.String(length=20),
            type_=sa.String(length=50),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("payroll_components") as batch_op:
        batch_op.alter_column(
            "component_type",
            existing_type=sa.String(length=50),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
