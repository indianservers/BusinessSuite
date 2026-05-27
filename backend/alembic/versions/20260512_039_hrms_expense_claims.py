"""add hrms expense claims

Revision ID: 20260512_039
Revises: 20260512_038
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_039"
down_revision = "20260512_038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_number", sa.String(length=50), nullable=False, unique=True),
        sa.Column("claim_type", sa.String(length=60), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(12, 2), nullable=True, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=True, server_default="INR"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("receipt_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True, server_default="submitted"),
        sa.Column("manager_approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("manager_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finance_approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("finance_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reimbursed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reimbursement_reference", sa.String(length=120), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_expense_claims_employee_id", "expense_claims", ["employee_id"])
    op.create_index("ix_expense_claims_claim_number", "expense_claims", ["claim_number"])
    op.create_index("ix_expense_claims_claim_type", "expense_claims", ["claim_type"])
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"])


def downgrade() -> None:
    op.drop_table("expense_claims")
