"""fam phase 3 party ar ap

Revision ID: 20260606_013
Revises: 20260606_012
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_013"
down_revision = "20260606_012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fam_parties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("party_type", sa.String(length=20), nullable=False),
        sa.Column("crm_account_id", sa.Integer()),
        sa.Column("crm_contact_id", sa.Integer()),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="SET NULL")),
        sa.Column("party_code", sa.String(length=80), nullable=False),
        sa.Column("legal_name", sa.String(length=220), nullable=False),
        sa.Column("trade_name", sa.String(length=220)),
        sa.Column("pan", sa.String(length=20)),
        sa.Column("gstin", sa.String(length=20)),
        sa.Column("registration_type", sa.String(length=30), server_default="regular"),
        sa.Column("state_code", sa.String(length=4)),
        sa.Column("billing_address", sa.Text()),
        sa.Column("shipping_address", sa.Text()),
        sa.Column("email", sa.String(length=180)),
        sa.Column("phone", sa.String(length=60)),
        sa.Column("mobile", sa.String(length=60)),
        sa.Column("payment_terms_days", sa.Integer(), server_default="30"),
        sa.Column("credit_limit", sa.Numeric(14, 2), server_default="0"),
        sa.Column("opening_balance_dr", sa.Numeric(14, 2), server_default="0"),
        sa.Column("opening_balance_cr", sa.Numeric(14, 2), server_default="0"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "party_code", name="uq_fam_party_company_code"),
        sa.UniqueConstraint("company_id", "ledger_id", name="uq_fam_party_company_ledger"),
    )
    for column in ["company_id", "party_type", "crm_account_id", "crm_contact_id", "ledger_id", "party_code", "legal_name", "trade_name", "registration_type", "active"]:
        op.create_index(f"ix_fam_parties_{column}", "fam_parties", [column])

    op.create_table(
        "fam_party_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("email", sa.String(length=180)),
        sa.Column("phone", sa.String(length=60)),
        sa.Column("designation", sa.String(length=120)),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fam_party_contacts_party_id", "fam_party_contacts", ["party_id"])

    op.create_table(
        "fam_bill_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("fam_ledgers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("fam_vouchers.id", ondelete="SET NULL")),
        sa.Column("voucher_line_id", sa.Integer(), sa.ForeignKey("fam_voucher_lines.id", ondelete="SET NULL")),
        sa.Column("bill_number", sa.String(length=120), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("bill_type", sa.String(length=30), nullable=False),
        sa.Column("original_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("outstanding_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("status", sa.String(length=30), server_default="open"),
        sa.Column("source_module", sa.String(length=40), server_default="fam"),
        sa.Column("source_record_type", sa.String(length=80)),
        sa.Column("source_record_id", sa.String(length=120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("company_id", "party_id", "bill_number", name="uq_fam_bill_company_party_number"),
    )
    for column in ["company_id", "party_id", "ledger_id", "voucher_id", "voucher_line_id", "bill_number", "bill_date", "due_date", "bill_type", "status", "source_module", "source_record_type", "source_record_id"]:
        op.create_index(f"ix_fam_bill_references_{column}", "fam_bill_references", [column])

    op.create_table(
        "fam_bill_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("allocation_date", sa.Date(), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_bill_reference_id", sa.Integer(), sa.ForeignKey("fam_bill_references.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("to_bill_reference_id", sa.Integer(), sa.ForeignKey("fam_bill_references.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("voucher_id", sa.Integer(), sa.ForeignKey("fam_vouchers.id", ondelete="SET NULL")),
        sa.Column("allocated_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("allocation_type", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for column in ["company_id", "allocation_date", "party_id", "from_bill_reference_id", "to_bill_reference_id", "voucher_id", "allocation_type", "created_by"]:
        op.create_index(f"ix_fam_bill_allocations_{column}", "fam_bill_allocations", [column])

    op.create_table(
        "fam_party_credit_terms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("fam_parties.id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_name", sa.String(length=120), nullable=False),
        sa.Column("days", sa.Integer(), server_default="30"),
        sa.Column("discount_percentage", sa.Numeric(6, 2), server_default="0"),
        sa.Column("active", sa.Boolean(), server_default=sa.true()),
    )
    op.create_index("ix_fam_party_credit_terms_party_id", "fam_party_credit_terms", ["party_id"])


def downgrade() -> None:
    op.drop_table("fam_party_credit_terms")
    op.drop_table("fam_bill_allocations")
    op.drop_table("fam_bill_references")
    op.drop_table("fam_party_contacts")
    op.drop_table("fam_parties")
