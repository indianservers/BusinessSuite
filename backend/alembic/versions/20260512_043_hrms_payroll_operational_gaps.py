"""add payroll operational gap tables

Revision ID: 20260512_043
Revises: 20260512_042
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260512_043"
down_revision = "20260512_042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payslip_delivery_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payroll_record_id", sa.Integer(), sa.ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("destination", sa.String(180)),
        sa.Column("status", sa.String(30), server_default="Queued"),
        sa.Column("message", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payslip_delivery_logs_payroll_record_id", "payslip_delivery_logs", ["payroll_record_id"])
    op.create_index("ix_payslip_delivery_logs_employee_id", "payslip_delivery_logs", ["employee_id"])
    op.create_index("ix_payslip_delivery_logs_channel", "payslip_delivery_logs", ["channel"])
    op.create_index("ix_payslip_delivery_logs_status", "payslip_delivery_logs", ["status"])

    op.create_table(
        "payslip_queries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payroll_record_id", sa.Integer(), sa.ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), server_default="Open"),
        sa.Column("priority", sa.String(20), server_default="Medium"),
        sa.Column("resolution", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("assigned_to", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_payslip_queries_payroll_record_id", "payslip_queries", ["payroll_record_id"])
    op.create_index("ix_payslip_queries_employee_id", "payslip_queries", ["employee_id"])
    op.create_index("ix_payslip_queries_status", "payslip_queries", ["status"])

    op.create_table(
        "salary_advances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("reason", sa.Text()),
        sa.Column("requested_deduction_month", sa.Integer(), nullable=False),
        sa.Column("requested_deduction_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), server_default="Pending"),
        sa.Column("payroll_record_id", sa.Integer(), sa.ForeignKey("payroll_records.id", ondelete="SET NULL")),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_remarks", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_salary_advances_employee_id", "salary_advances", ["employee_id"])
    op.create_index("ix_salary_advances_status", "salary_advances", ["status"])

    op.create_table(
        "salary_revision_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), server_default="Draft"),
        sa.Column("total_rows", sa.Integer(), server_default="0"),
        sa.Column("applied_rows", sa.Integer(), server_default="0"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("applied_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_salary_revision_batches_status", "salary_revision_batches", ["status"])
    op.create_table(
        "salary_revision_batch_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("salary_revision_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_ctc", sa.Numeric(14, 2), server_default="0"),
        sa.Column("new_ctc", sa.Numeric(14, 2), nullable=False),
        sa.Column("structure_id", sa.Integer(), sa.ForeignKey("salary_structures.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(30), server_default="Pending"),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index("ix_salary_revision_batch_lines_batch_id", "salary_revision_batch_lines", ["batch_id"])
    op.create_index("ix_salary_revision_batch_lines_employee_id", "salary_revision_batch_lines", ["employee_id"])

    op.create_table(
        "bonus_policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("bonus_type", sa.String(60), server_default="Festival"),
        sa.Column("amount_type", sa.String(30), server_default="Fixed"),
        sa.Column("amount_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("applicable_month", sa.Integer()),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("grade_band_id", sa.Integer(), sa.ForeignKey("grade_bands.id", ondelete="SET NULL")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("description", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bonus_policies_bonus_type", "bonus_policies", ["bonus_type"])
    op.create_index("ix_bonus_policies_is_active", "bonus_policies", ["is_active"])

    op.create_table(
        "gratuity_accruals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payroll_run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id", ondelete="SET NULL")),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("gratuity_wage", sa.Numeric(14, 2), server_default="0"),
        sa.Column("accrual_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("status", sa.String(30), server_default="Posted"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_gratuity_accruals_employee_id", "gratuity_accruals", ["employee_id"])
    op.create_index("ix_gratuity_accruals_payroll_run_id", "gratuity_accruals", ["payroll_run_id"])

    op.create_table(
        "salary_certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(160), nullable=False),
        sa.Column("period_from", sa.Date()),
        sa.Column("period_to", sa.Date()),
        sa.Column("annual_ctc", sa.Numeric(14, 2), server_default="0"),
        sa.Column("monthly_gross", sa.Numeric(14, 2), server_default="0"),
        sa.Column("file_url", sa.String(500)),
        sa.Column("status", sa.String(30), server_default="Generated"),
        sa.Column("generated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_salary_certificates_employee_id", "salary_certificates", ["employee_id"])

    op.create_table(
        "payroll_budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")),
        sa.Column("cost_center_id", sa.Integer(), sa.ForeignKey("cost_centers.id", ondelete="SET NULL")),
        sa.Column("budget_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("remarks", sa.Text()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payroll_budgets_month", "payroll_budgets", ["month"])
    op.create_index("ix_payroll_budgets_year", "payroll_budgets", ["year"])

    op.create_table("payroll_bank_validations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("payroll_run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id", ondelete="SET NULL")), sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE")), sa.Column("status", sa.String(30), server_default="Pending"), sa.Column("error_code", sa.String(80)), sa.Column("message", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("payroll_bank_file_validations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("payroll_run_id", sa.Integer(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("bank_name", sa.String(120), nullable=False), sa.Column("status", sa.String(30), server_default="Pending"), sa.Column("error_count", sa.Integer(), server_default="0"), sa.Column("warnings_json", sa.JSON()), sa.Column("errors_json", sa.JSON()), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("tds_26as_reconciliations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False), sa.Column("financial_year", sa.String(20), nullable=False), sa.Column("company_tds", sa.Numeric(14, 2), server_default="0"), sa.Column("reported_26as_tds", sa.Numeric(14, 2), server_default="0"), sa.Column("difference", sa.Numeric(14, 2), server_default="0"), sa.Column("status", sa.String(30), server_default="Pending"), sa.Column("remarks", sa.Text()), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("form_12ba_records", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False), sa.Column("financial_year", sa.String(20), nullable=False), sa.Column("perquisites_json", sa.JSON()), sa.Column("total_perquisite_value", sa.Numeric(14, 2), server_default="0"), sa.Column("file_url", sa.String(500)), sa.Column("status", sa.String(30), server_default="Generated"), sa.Column("generated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("payroll_exchange_rates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("from_currency", sa.String(3), nullable=False), sa.Column("to_currency", sa.String(3), nullable=False, server_default="INR"), sa.Column("rate", sa.Numeric(14, 6), nullable=False), sa.Column("effective_date", sa.Date(), nullable=False), sa.Column("source", sa.String(80), server_default="Manual"), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("payroll_report_definitions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("report_type", sa.String(80), nullable=False), sa.Column("filters_json", sa.JSON()), sa.Column("columns_json", sa.JSON()), sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))


def downgrade() -> None:
    for table_name in (
        "payroll_report_definitions",
        "payroll_exchange_rates",
        "form_12ba_records",
        "tds_26as_reconciliations",
        "payroll_bank_file_validations",
        "payroll_bank_validations",
        "payroll_budgets",
        "salary_certificates",
        "gratuity_accruals",
        "bonus_policies",
        "salary_revision_batch_lines",
        "salary_revision_batches",
        "salary_advances",
        "payslip_queries",
        "payslip_delivery_logs",
    ):
        op.drop_table(table_name)
