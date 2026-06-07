"""fam phase 2 voucher engine

Revision ID: 20260606_012
Revises: 20260605_011
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_012"
down_revision = "20260605_011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fam_voucher_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("voucher_type_code", sa.String(length=40), nullable=False),
        sa.Column("voucher_type_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("numbering_prefix", sa.String(length=30), nullable=False),
        sa.Column("numbering_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_numbering", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("system_type", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "voucher_type_code", name="uq_fam_voucher_type_company_code"),
    )
    op.create_index("ix_fam_voucher_types_company_id", "fam_voucher_types", ["company_id"])
    op.create_index("ix_fam_voucher_types_category", "fam_voucher_types", ["category"])

    op.create_table(
        "fam_vouchers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("financial_year_id", sa.Integer(), sa.ForeignKey("fam_financial_years.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accounting_period_id", sa.Integer(), sa.ForeignKey("fam_accounting_periods.id", ondelete="RESTRICT")),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("fam_branches.id", ondelete="SET NULL")),
        sa.Column("voucher_type_id", sa.Integer(), sa.ForeignKey("fam_voucher_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("voucher_number", sa.String(length=80), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("reference_number", sa.String(length=120)),
        sa.Column("reference_date", sa.Date()),
        sa.Column("narration", sa.Text()),
        sa.Column("total_debit", sa.Numeric(14, 2), server_default="0"),
        sa.Column("total_credit", sa.Numeric(14, 2), server_default="0"),
        sa.Column("status", sa.String(length=20), server_default="draft"),
        sa.Column("source_module", sa.String(length=40), server_default="fam"),
        sa.Column("source_record_type", sa.String(length=80)),
        sa.Column("source_record_id", sa.String(length=120)),
        sa.Column("posted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("reversed_voucher_id", sa.Integer(), sa.ForeignKey("fam_vouchers.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "voucher_number", name="uq_fam_voucher_company_number"),
    )
    for column in ["company_id", "financial_year_id", "accounting_period_id", "branch_id", "voucher_type_id", "voucher_number", "voucher_date", "status", "source_module", "source_record_type", "source_record_id", "posted_at", "reversed_voucher_id"]:
        op.create_index(f"ix_fam_vouchers_{column}", "fam_vouchers", [column])

    op.create_table(
        "fam_voucher_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debit_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("credit_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("narration", sa.Text()),
        sa.Column("cost_center_id", sa.Integer(), sa.ForeignKey("fam_cost_centers.id", ondelete="SET NULL")),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("fam_branches.id", ondelete="SET NULL")),
        sa.Column("party_id", sa.Integer()),
        sa.Column("tax_component_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    for column in ["voucher_id", "ledger_id", "cost_center_id", "branch_id", "party_id", "tax_component_id"]:
        op.create_index(f"ix_fam_voucher_lines_{column}", "fam_voucher_lines", [column])

    op.create_table(
        "fam_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("financial_year_id", sa.Integer(), sa.ForeignKey("fam_financial_years.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accounting_period_id", sa.Integer(), sa.ForeignKey("fam_accounting_periods.id", ondelete="RESTRICT")),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("fam_vouchers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("voucher_line_id", sa.Integer(), sa.ForeignKey("fam_voucher_lines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("voucher_number", sa.String(length=80), nullable=False),
        sa.Column("voucher_date", sa.Date(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debit_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("credit_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("running_balance", sa.Numeric(14, 2), server_default="0"),
        sa.Column("narration", sa.Text()),
        sa.Column("source_module", sa.String(length=40), server_default="fam"),
        sa.Column("source_record_type", sa.String(length=80)),
        sa.Column("source_record_id", sa.String(length=120)),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ["company_id", "financial_year_id", "accounting_period_id", "voucher_id", "voucher_line_id", "voucher_number", "voucher_date", "ledger_id", "source_module", "source_record_type", "source_record_id", "posted_at"]:
        op.create_index(f"ix_fam_ledger_entries_{column}", "fam_ledger_entries", [column])

    op.create_table(
        "fam_voucher_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("fam_vouchers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("old_value_json", sa.JSON()),
        sa.Column("new_value_json", sa.JSON()),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fam_voucher_audit_logs_voucher_id", "fam_voucher_audit_logs", ["voucher_id"])
    op.create_index("ix_fam_voucher_audit_logs_action", "fam_voucher_audit_logs", ["action"])
    op.create_index("ix_fam_voucher_audit_logs_performed_at", "fam_voucher_audit_logs", ["performed_at"])


def downgrade() -> None:
    op.drop_table("fam_voucher_audit_logs")
    op.drop_table("fam_ledger_entries")
    op.drop_table("fam_voucher_lines")
    op.drop_table("fam_vouchers")
    op.drop_table("fam_voucher_types")
