"""add benefit enrollment windows and dependents

Revision ID: 20260512_040
Revises: 20260512_039
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_040"
down_revision = "20260512_039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benefit_enrollment_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("plan_type", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True, server_default="Open"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_benefit_enrollment_windows_start_date", "benefit_enrollment_windows", ["start_date"])
    op.create_index("ix_benefit_enrollment_windows_end_date", "benefit_enrollment_windows", ["end_date"])
    op.create_index("ix_benefit_enrollment_windows_plan_type", "benefit_enrollment_windows", ["plan_type"])
    op.create_index("ix_benefit_enrollment_windows_status", "benefit_enrollment_windows", ["status"])

    op.create_table(
        "benefit_dependents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("employee_benefit_enrollments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("relationship", sa.String(length=50), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("identity_number", sa.String(length=80), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_benefit_dependents_employee_id", "benefit_dependents", ["employee_id"])
    op.create_index("ix_benefit_dependents_enrollment_id", "benefit_dependents", ["enrollment_id"])
    op.create_index("ix_benefit_dependents_is_active", "benefit_dependents", ["is_active"])


def downgrade() -> None:
    op.drop_table("benefit_dependents")
    op.drop_table("benefit_enrollment_windows")
