"""fam phase 10 final hardening

Revision ID: 20260607_020
Revises: 20260607_019
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_020"
down_revision = "20260607_019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fam_import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("import_type", sa.String(length=80), nullable=False),
        sa.Column("file_name", sa.String(length=220), nullable=False),
        sa.Column("file_content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("mapping_json", sa.JSON(), nullable=True),
        sa.Column("validation_result_json", sa.JSON(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("posted_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "fam_export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("export_type", sa.String(length=80), nullable=False),
        sa.Column("export_format", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("file_name", sa.String(length=220), nullable=True),
        sa.Column("file_content", sa.Text(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_table(
        "fam_integrity_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("run_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_table(
        "fam_period_close_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("financial_year_id", sa.Integer(), sa.ForeignKey("fam_financial_years.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accounting_period_id", sa.Integer(), sa.ForeignKey("fam_accounting_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("checklist_json", sa.JSON(), nullable=True),
        sa.Column("locked_period_id", sa.Integer(), sa.ForeignKey("fam_accounting_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approval_note", sa.Text(), nullable=True),
        sa.Column("run_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "fam_ai_accounting_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("request_type", sa.String(length=80), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Numeric(7, 3), nullable=True),
        sa.Column("evidence_json", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    for table in ["fam_import_jobs", "fam_export_jobs", "fam_integrity_runs", "fam_period_close_runs", "fam_ai_accounting_logs"]:
        op.create_index(f"ix_{table}_company_id", table, ["company_id"])
        op.create_index(f"ix_{table}_status", table, ["status"])
    op.create_index("ix_fam_import_jobs_import_type", "fam_import_jobs", ["import_type"])
    op.create_index("ix_fam_export_jobs_export_type", "fam_export_jobs", ["export_type"])
    op.create_index("ix_fam_ai_accounting_logs_request_type", "fam_ai_accounting_logs", ["request_type"])


def downgrade() -> None:
    op.drop_table("fam_ai_accounting_logs")
    op.drop_table("fam_period_close_runs")
    op.drop_table("fam_integrity_runs")
    op.drop_table("fam_export_jobs")
    op.drop_table("fam_import_jobs")
