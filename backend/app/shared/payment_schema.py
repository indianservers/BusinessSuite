"""Additive payment-request schema, shared by both migration histories."""
import sqlalchemy as sa

SOURCE_CHECK = "(source_type = 'crm_deal' AND deal_id IS NOT NULL AND deal_id = source_id AND quotation_id IS NULL AND sales_order_id IS NULL AND invoice_id IS NULL) OR (source_type = 'crm_quotation' AND quotation_id IS NOT NULL AND quotation_id = source_id AND deal_id IS NULL AND sales_order_id IS NULL AND invoice_id IS NULL) OR (source_type = 'srm_order' AND sales_order_id IS NOT NULL AND sales_order_id = source_id AND deal_id IS NULL AND quotation_id IS NULL AND invoice_id IS NULL) OR (source_type = 'srm_invoice' AND invoice_id IS NOT NULL AND invoice_id = source_id AND deal_id IS NULL AND quotation_id IS NULL AND sales_order_id IS NULL)"


def upgrade(op):
    if "suite_payment_requests" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table("suite_payment_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("crm_deals.id", ondelete="RESTRICT")),
        sa.Column("quotation_id", sa.Integer(), sa.ForeignKey("crm_quotations.id", ondelete="RESTRICT")),
        sa.Column("sales_order_id", sa.Integer(), sa.ForeignKey("srm_sales_orders.id", ondelete="RESTRICT")),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("srm_invoices.id", ondelete="RESTRICT")),
        sa.Column("reference", sa.String(180), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("provider", sa.String(30)),
        sa.Column("provider_account", sa.String(64)),
        sa.Column("provider_id", sa.String(100)),
        sa.Column("payment_url", sa.String(500)),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("srm_receipts.id", ondelete="RESTRICT"), unique=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "request_id", name="uq_suite_payment_request_id"),
        sa.CheckConstraint("amount > 0", name="ck_suite_payment_positive"),
        sa.CheckConstraint(SOURCE_CHECK, name="ck_suite_payment_source"))
    op.create_index("ix_suite_payment_source", "suite_payment_requests", ["organization_id", "source_type", "source_id"])


def downgrade(op):
    op.drop_table("suite_payment_requests")
