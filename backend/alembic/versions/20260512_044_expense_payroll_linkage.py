"""add expense claim payroll linkage

Revision ID: 20260512_044
Revises: 20260512_043
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_044"
down_revision = "20260512_043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expense_claims", sa.Column("payroll_reimbursement_id", sa.Integer(), nullable=True))
    op.add_column("expense_claims", sa.Column("payroll_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_expense_claims_payroll_reimbursement_id_reimbursements",
        "expense_claims",
        "reimbursements",
        ["payroll_reimbursement_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_expense_claims_payroll_run_id_payroll_runs",
        "expense_claims",
        "payroll_runs",
        ["payroll_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_expense_claims_payroll_reimbursement_id", "expense_claims", ["payroll_reimbursement_id"])
    op.create_index("ix_expense_claims_payroll_run_id", "expense_claims", ["payroll_run_id"])


def downgrade() -> None:
    op.drop_index("ix_expense_claims_payroll_run_id", table_name="expense_claims")
    op.drop_index("ix_expense_claims_payroll_reimbursement_id", table_name="expense_claims")
    op.drop_constraint("fk_expense_claims_payroll_run_id_payroll_runs", "expense_claims", type_="foreignkey")
    op.drop_constraint("fk_expense_claims_payroll_reimbursement_id_reimbursements", "expense_claims", type_="foreignkey")
    op.drop_column("expense_claims", "payroll_run_id")
    op.drop_column("expense_claims", "payroll_reimbursement_id")
