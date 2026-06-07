"""fam phase 1 accounting foundation

Revision ID: 20260605_011
Revises: 20260605_010
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_011"
down_revision = "20260605_010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fam_company_financial_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="IN"),
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("gst_enabled", sa.Boolean(), server_default=sa.false()),
        sa.Column("gstin", sa.String(length=20)),
        sa.Column("legal_name", sa.String(length=220)),
        sa.Column("trade_name", sa.String(length=220)),
        sa.Column("pan", sa.String(length=20)),
        sa.Column("tan", sa.String(length=20)),
        sa.Column("cin", sa.String(length=30)),
        sa.Column("registered_address", sa.Text()),
        sa.Column("state_code", sa.String(length=4)),
        sa.Column("financial_year_start_month", sa.Integer(), server_default="4"),
        sa.Column("books_start_date", sa.Date()),
        sa.Column("decimal_places", sa.Integer(), server_default="2"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", name="uq_fam_company_settings"),
    )
    op.create_index("ix_fam_company_financial_settings_company_id", "fam_company_financial_settings", ["company_id"])

    op.create_table(
        "fam_financial_years",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open"),
        sa.Column("is_current", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "name", name="uq_fam_financial_year_company_name"),
    )
    op.create_index("ix_fam_financial_years_company_id", "fam_financial_years", ["company_id"])
    op.create_index("ix_fam_financial_years_start_date", "fam_financial_years", ["start_date"])
    op.create_index("ix_fam_financial_years_end_date", "fam_financial_years", ["end_date"])

    op.create_table(
        "fam_accounting_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("financial_year_id", sa.Integer(), sa.ForeignKey("fam_financial_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_name", sa.String(length=80), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_fam_accounting_periods_financial_year_id", "fam_accounting_periods", ["financial_year_id"])

    op.create_table(
        "fam_ledger_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("parent_group_id", sa.Integer(), sa.ForeignKey("fam_ledger_groups.id", ondelete="SET NULL")),
        sa.Column("group_name", sa.String(length=160), nullable=False),
        sa.Column("group_code", sa.String(length=80), nullable=False),
        sa.Column("nature", sa.String(length=20), nullable=False),
        sa.Column("system_group", sa.Boolean(), server_default=sa.false()),
        sa.Column("affects_gross_profit", sa.Boolean(), server_default=sa.false()),
        sa.Column("sequence_order", sa.Integer(), server_default="100"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "group_code", name="uq_fam_ledger_group_company_code"),
    )
    op.create_index("ix_fam_ledger_groups_company_id", "fam_ledger_groups", ["company_id"])
    op.create_index("ix_fam_ledger_groups_parent_group_id", "fam_ledger_groups", ["parent_group_id"])
    op.create_index("ix_fam_ledger_groups_nature", "fam_ledger_groups", ["nature"])

    op.create_table(
        "fam_ledgers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("ledger_code", sa.String(length=80), nullable=False),
        sa.Column("ledger_name", sa.String(length=180), nullable=False),
        sa.Column("ledger_group_id", sa.Integer(), sa.ForeignKey("fam_ledger_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nature", sa.String(length=20), nullable=False),
        sa.Column("ledger_type", sa.String(length=30), server_default="general"),
        sa.Column("gst_applicable", sa.Boolean(), server_default=sa.false()),
        sa.Column("pan", sa.String(length=20)),
        sa.Column("gstin", sa.String(length=20)),
        sa.Column("state_code", sa.String(length=4)),
        sa.Column("billing_address", sa.Text()),
        sa.Column("opening_balance_dr", sa.Numeric(14, 2), server_default="0"),
        sa.Column("opening_balance_cr", sa.Numeric(14, 2), server_default="0"),
        sa.Column("current_balance_dr", sa.Numeric(14, 2), server_default="0"),
        sa.Column("current_balance_cr", sa.Numeric(14, 2), server_default="0"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("system_ledger", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "ledger_code", name="uq_fam_ledger_company_code"),
        sa.UniqueConstraint("company_id", "ledger_name", name="uq_fam_ledger_company_name"),
    )
    op.create_index("ix_fam_ledgers_company_id", "fam_ledgers", ["company_id"])
    op.create_index("ix_fam_ledgers_ledger_group_id", "fam_ledgers", ["ledger_group_id"])
    op.create_index("ix_fam_ledgers_nature", "fam_ledgers", ["nature"])

    op.create_table(
        "fam_opening_balances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("financial_year_id", sa.Integer(), sa.ForeignKey("fam_financial_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debit_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("credit_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("narration", sa.Text()),
        sa.Column("posted", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "financial_year_id", "ledger_id", name="uq_fam_opening_balance"),
    )
    op.create_index("ix_fam_opening_balances_company_id", "fam_opening_balances", ["company_id"])
    op.create_index("ix_fam_opening_balances_financial_year_id", "fam_opening_balances", ["financial_year_id"])
    op.create_index("ix_fam_opening_balances_ledger_id", "fam_opening_balances", ["ledger_id"])

    op.create_table(
        "fam_cost_centers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("fam_cost_centers.id", ondelete="SET NULL")),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "code", name="uq_fam_cost_center_company_code"),
    )
    op.create_index("ix_fam_cost_centers_company_id", "fam_cost_centers", ["company_id"])

    op.create_table(
        "fam_branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_code", sa.String(length=80), nullable=False),
        sa.Column("branch_name", sa.String(length=180), nullable=False),
        sa.Column("gstin", sa.String(length=20)),
        sa.Column("state_code", sa.String(length=4)),
        sa.Column("address", sa.Text()),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "branch_code", name="uq_fam_branch_company_code"),
    )
    op.create_index("ix_fam_branches_company_id", "fam_branches", ["company_id"])

    op.create_table(
        "fam_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("module_name", sa.String(length=80), server_default="fam"),
        sa.Column("record_type", sa.String(length=80), nullable=False),
        sa.Column("record_id", sa.Integer()),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("old_value_json", sa.JSON()),
        sa.Column("new_value_json", sa.JSON()),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ip_address", sa.String(length=80)),
        sa.Column("user_agent", sa.Text()),
    )
    op.create_index("ix_fam_audit_logs_company_id", "fam_audit_logs", ["company_id"])
    op.create_index("ix_fam_audit_logs_record_type", "fam_audit_logs", ["record_type"])
    op.create_index("ix_fam_audit_logs_action", "fam_audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("fam_audit_logs")
    op.drop_table("fam_branches")
    op.drop_table("fam_cost_centers")
    op.drop_table("fam_opening_balances")
    op.drop_table("fam_ledgers")
    op.drop_table("fam_ledger_groups")
    op.drop_table("fam_accounting_periods")
    op.drop_table("fam_financial_years")
    op.drop_table("fam_company_financial_settings")
