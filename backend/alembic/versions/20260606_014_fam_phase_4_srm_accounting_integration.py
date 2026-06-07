"""fam phase 4 srm accounting integration

Revision ID: 20260606_014
Revises: 20260606_013
Create Date: 2026-06-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_014"
down_revision = "20260606_013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fam_srm_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("srm_record_type", sa.String(length=40), nullable=False),
        sa.Column("srm_record_id", sa.Integer(), nullable=False),
        sa.Column("fam_record_type", sa.String(length=40), nullable=False),
        sa.Column("fam_record_id", sa.Integer(), nullable=False),
        sa.Column("mapping_status", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "srm_record_type", "srm_record_id", "fam_record_type", name="uq_fam_srm_mapping_source_target"),
    )
    op.create_index(op.f("ix_fam_srm_mapping_company_id"), "fam_srm_mapping", ["company_id"], unique=False)
    op.create_index(op.f("ix_fam_srm_mapping_srm_record_type"), "fam_srm_mapping", ["srm_record_type"], unique=False)
    op.create_index(op.f("ix_fam_srm_mapping_srm_record_id"), "fam_srm_mapping", ["srm_record_id"], unique=False)
    op.create_index(op.f("ix_fam_srm_mapping_fam_record_type"), "fam_srm_mapping", ["fam_record_type"], unique=False)
    op.create_index(op.f("ix_fam_srm_mapping_fam_record_id"), "fam_srm_mapping", ["fam_record_id"], unique=False)
    op.create_index(op.f("ix_fam_srm_mapping_mapping_status"), "fam_srm_mapping", ["mapping_status"], unique=False)
    op.create_index(op.f("ix_fam_srm_mapping_created_at"), "fam_srm_mapping", ["created_at"], unique=False)

    op.create_table(
        "fam_posting_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_module", sa.String(length=40), nullable=False),
        sa.Column("source_record_type", sa.String(length=80), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=False),
        sa.Column("posting_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("voucher_id", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["voucher_id"], ["fam_vouchers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "source_module", "source_record_type", "source_record_id", "posting_type", name="uq_fam_posting_job_source"),
    )
    for column in ["company_id", "source_module", "source_record_type", "source_record_id", "posting_type", "status", "voucher_id", "posted_at", "created_at"]:
        op.create_index(op.f(f"ix_fam_posting_jobs_{column}"), "fam_posting_jobs", [column], unique=False)

    op.create_table(
        "fam_posting_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_module", sa.String(length=40), nullable=False),
        sa.Column("transaction_type", sa.String(length=80), nullable=False),
        sa.Column("debit_ledger_rule_json", sa.JSON(), nullable=True),
        sa.Column("credit_ledger_rule_json", sa.JSON(), nullable=True),
        sa.Column("tax_ledger_rule_json", sa.JSON(), nullable=True),
        sa.Column("roundoff_ledger_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["roundoff_ledger_id"], ["fam_ledgers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "source_module", "transaction_type", name="uq_fam_posting_rule"),
    )
    for column in ["company_id", "source_module", "transaction_type", "roundoff_ledger_id", "active", "created_at"]:
        op.create_index(op.f(f"ix_fam_posting_rules_{column}"), "fam_posting_rules", [column], unique=False)


def downgrade() -> None:
    op.drop_table("fam_posting_rules")
    op.drop_table("fam_posting_jobs")
    op.drop_table("fam_srm_mapping")

