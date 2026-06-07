"""fam phase 5 bank cash reconciliation

Revision ID: 20260606_015
Revises: 20260606_014
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_015"
down_revision = "20260606_014"
branch_labels = None
depends_on = None


def _ensure_fam_foundation_tables() -> None:
    """Repair databases stamped past FAM Phase 1-4 but missing FAM tables.

    Some development databases were already stamped at the previous revision
    before FAM operational tables existed physically. Phase 5 depends on the
    earlier ledger and voucher tables, so create any missing FAM model tables
    with SQLAlchemy's normal metadata ordering before applying this migration.
    Existing databases with the tables already present are left untouched.
    """

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "fam_ledgers" in inspector.get_table_names():
        return

    import app.db.base  # noqa: F401
    import app.apps.fam.models  # noqa: F401
    from app.db.base_class import Base

    for table in Base.metadata.sorted_tables:
        if table.name.startswith("fam_"):
            table.create(bind=bind, checkfirst=True)


def upgrade() -> None:
    _ensure_fam_foundation_tables()

    op.create_table(
        "fam_bank_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("bank_name", sa.String(length=180), nullable=False),
        sa.Column("branch_name", sa.String(length=180), nullable=True),
        sa.Column("account_number_masked", sa.String(length=80), nullable=False),
        sa.Column("ifsc", sa.String(length=20), nullable=True),
        sa.Column("account_type", sa.String(length=40), nullable=True),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ledger_id"], ["fam_ledgers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "ledger_id", name="uq_fam_bank_account_company_ledger"),
    )
    op.create_index(op.f("ix_fam_bank_accounts_id"), "fam_bank_accounts", ["id"], unique=False)
    op.create_index("ix_fam_bank_accounts_company_id", "fam_bank_accounts", ["company_id"], unique=False)
    op.create_index("ix_fam_bank_accounts_ledger_id", "fam_bank_accounts", ["ledger_id"], unique=False)

    op.create_table(
        "fam_payment_modes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("default_ledger_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["default_ledger_id"], ["fam_ledgers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "name", name="uq_fam_payment_mode_company_name"),
    )
    op.create_index(op.f("ix_fam_payment_modes_id"), "fam_payment_modes", ["id"], unique=False)
    op.create_index("ix_fam_payment_modes_company_id", "fam_payment_modes", ["company_id"], unique=False)

    op.create_table(
        "fam_bank_statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=False),
        sa.Column("statement_period_start", sa.Date(), nullable=False),
        sa.Column("statement_period_end", sa.Date(), nullable=False),
        sa.Column("imported_file_name", sa.String(length=220), nullable=False),
        sa.Column("imported_file_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("imported_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["bank_account_id"], ["fam_bank_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "bank_account_id", "imported_file_hash", name="uq_fam_bank_statement_file_hash"),
    )
    op.create_index(op.f("ix_fam_bank_statements_id"), "fam_bank_statements", ["id"], unique=False)
    op.create_index("ix_fam_bank_statements_company_id", "fam_bank_statements", ["company_id"], unique=False)
    op.create_index("ix_fam_bank_statements_bank_account_id", "fam_bank_statements", ["bank_account_id"], unique=False)

    op.create_table(
        "fam_bank_statement_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference_number", sa.String(length=160), nullable=True),
        sa.Column("debit_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("credit_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("matched_status", sa.String(length=30), nullable=True),
        sa.Column("matched_voucher_id", sa.Integer(), nullable=True),
        sa.Column("line_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["matched_voucher_id"], ["fam_vouchers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["statement_id"], ["fam_bank_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statement_id", "line_hash", name="uq_fam_bank_statement_line_hash"),
    )
    op.create_index(op.f("ix_fam_bank_statement_lines_id"), "fam_bank_statement_lines", ["id"], unique=False)
    op.create_index("ix_fam_bank_statement_lines_statement_id", "fam_bank_statement_lines", ["statement_id"], unique=False)
    op.create_index("ix_fam_bank_statement_lines_matched_status", "fam_bank_statement_lines", ["matched_status"], unique=False)

    op.create_table(
        "fam_bank_reconciliation_matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("statement_line_id", sa.Integer(), nullable=False),
        sa.Column("voucher_id", sa.Integer(), nullable=False),
        sa.Column("ledger_entry_id", sa.Integer(), nullable=True),
        sa.Column("match_type", sa.String(length=30), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("matched_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("matched_by", sa.Integer(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ledger_entry_id"], ["fam_ledger_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["statement_line_id"], ["fam_bank_statement_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voucher_id"], ["fam_vouchers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("statement_line_id", "voucher_id", name="uq_fam_bank_recon_line_voucher"),
    )
    op.create_index(op.f("ix_fam_bank_reconciliation_matches_id"), "fam_bank_reconciliation_matches", ["id"], unique=False)

    op.create_table(
        "fam_bank_reconciliation_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=False),
        sa.Column("book_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("bank_statement_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("unreconciled_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("reconciled_by", sa.Integer(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["bank_account_id"], ["fam_bank_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reconciled_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["statement_id"], ["fam_bank_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fam_bank_reconciliation_sessions_id"), "fam_bank_reconciliation_sessions", ["id"], unique=False)
    op.create_index("ix_fam_bank_reconciliation_sessions_company_id", "fam_bank_reconciliation_sessions", ["company_id"], unique=False)

    op.create_table(
        "fam_cash_registers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("register_name", sa.String(length=160), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ledger_id"], ["fam_ledgers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "ledger_id", name="uq_fam_cash_register_company_ledger"),
    )
    op.create_index(op.f("ix_fam_cash_registers_id"), "fam_cash_registers", ["id"], unique=False)
    op.create_index("ix_fam_cash_registers_company_id", "fam_cash_registers", ["company_id"], unique=False)

    op.create_table(
        "fam_payment_references",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("voucher_id", sa.Integer(), nullable=False),
        sa.Column("voucher_line_id", sa.Integer(), nullable=True),
        sa.Column("payment_mode_id", sa.Integer(), nullable=True),
        sa.Column("reference_number", sa.String(length=160), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column("bank_account_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["bank_account_id"], ["fam_bank_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_mode_id"], ["fam_payment_modes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["voucher_id"], ["fam_vouchers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["voucher_line_id"], ["fam_voucher_lines.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "reference_number", "payment_mode_id", name="uq_fam_payment_reference"),
    )
    op.create_index(op.f("ix_fam_payment_references_id"), "fam_payment_references", ["id"], unique=False)
    op.create_index("ix_fam_payment_references_company_id", "fam_payment_references", ["company_id"], unique=False)


def downgrade() -> None:
    op.drop_table("fam_payment_references")
    op.drop_table("fam_cash_registers")
    op.drop_table("fam_bank_reconciliation_sessions")
    op.drop_table("fam_bank_reconciliation_matches")
    op.drop_table("fam_bank_statement_lines")
    op.drop_table("fam_bank_statements")
    op.drop_table("fam_payment_modes")
    op.drop_table("fam_bank_accounts")
