"""crm phase 3 products quotes cpq

Revision ID: 20260605_003
Revises: 20260605_002
Create Date: 2026-06-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_003"
down_revision = "20260605_002"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    for column in [
        sa.Column("product_code", sa.String(80), nullable=True),
        sa.Column("unit_of_measure", sa.String(40), nullable=True, server_default="unit"),
        sa.Column("list_price", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
    ]:
        _add("crm_products", column)
    op.execute("UPDATE crm_products SET product_code = COALESCE(product_code, sku)")
    op.execute("UPDATE crm_products SET list_price = COALESCE(list_price, unit_price, 0)")
    op.execute("UPDATE crm_products SET active = COALESCE(active, CASE WHEN status = 'Active' THEN 1 ELSE 0 END)")

    for column in [
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("quote_date", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("approval_status", sa.String(30), nullable=True, server_default="not_required"),
        sa.Column("discount_total", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("expected_margin", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("margin_percentage", sa.Numeric(6, 2), nullable=True, server_default="0"),
        sa.Column("version_number", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("terms_and_conditions", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_srm_sales_order_id", sa.Integer(), nullable=True),
        sa.Column("converted_srm_contract_id", sa.Integer(), nullable=True),
        sa.Column("converted_srm_engagement_id", sa.Integer(), nullable=True),
    ]:
        _add("crm_quotations", column)
    op.execute("UPDATE crm_quotations SET account_id = COALESCE(account_id, company_id)")
    op.execute("UPDATE crm_quotations SET owner_id = COALESCE(owner_id, owner_user_id)")
    op.execute("UPDATE crm_quotations SET quote_date = COALESCE(quote_date, issue_date)")
    op.execute("UPDATE crm_quotations SET valid_until = COALESCE(valid_until, expiry_date)")
    op.execute("UPDATE crm_quotations SET discount_total = COALESCE(discount_total, discount_amount, 0)")
    op.execute("UPDATE crm_quotations SET tax_total = COALESCE(tax_total, tax_amount, 0)")
    op.execute("UPDATE crm_quotations SET grand_total = COALESCE(grand_total, total_amount, 0)")
    op.execute("UPDATE crm_quotations SET terms_and_conditions = COALESCE(terms_and_conditions, terms)")

    for column in [
        sa.Column("quote_id", sa.Integer(), nullable=True),
        sa.Column("item_type", sa.String(30), nullable=True, server_default="product"),
        sa.Column("service_id", sa.Integer(), nullable=True),
        sa.Column("discount_type", sa.String(20), nullable=True, server_default="amount"),
        sa.Column("discount_value", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("margin_amount", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("margin_percentage", sa.Numeric(6, 2), nullable=True, server_default="0"),
        sa.Column("billing_type", sa.String(30), nullable=True, server_default="fixed"),
    ]:
        _add("crm_quotation_items", column)
    op.execute("UPDATE crm_quotation_items SET quote_id = COALESCE(quote_id, quotation_id)")
    op.execute("UPDATE crm_quotation_items SET line_total = COALESCE(line_total, total_amount, 0)")
    op.execute("UPDATE crm_quotation_items SET discount_value = COALESCE(discount_value, discount_amount, 0)")

    op.create_table(
        "crm_services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("service_code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("billing_type", sa.String(30), nullable=True, server_default="fixed"),
        sa.Column("default_rate", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("default_cost", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "service_code", name="uq_crm_service_org_code"),
    )
    op.create_table(
        "crm_price_books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("currency", sa.String(10), nullable=True, server_default="INR"),
        sa.Column("region", sa.String(120), nullable=True),
        sa.Column("customer_segment", sa.String(120), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "crm_price_book_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("price_book_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(30), nullable=True, server_default="product"),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("service_id", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=True, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=True, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table("crm_quote_versions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer()), sa.Column("quote_id", sa.Integer(), nullable=False), sa.Column("version_number", sa.Integer(), nullable=False), sa.Column("snapshot_json", sa.JSON()), sa.Column("created_by_user_id", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_table("crm_quote_approvals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer()), sa.Column("quote_id", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), server_default="pending"), sa.Column("reason", sa.Text()), sa.Column("submitted_by", sa.Integer()), sa.Column("approver_user_id", sa.Integer()), sa.Column("approved_by", sa.Integer()), sa.Column("comments", sa.Text()), sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("decided_at", sa.DateTime(timezone=True)))
    op.create_table("crm_cpq_rules", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer()), sa.Column("name", sa.String(180), nullable=False), sa.Column("rule_type", sa.String(40), nullable=False), sa.Column("condition_json", sa.JSON()), sa.Column("action_json", sa.JSON()), sa.Column("active", sa.Boolean(), server_default=sa.true()), sa.Column("created_by_user_id", sa.Integer()), sa.Column("updated_by_user_id", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_table("crm_guided_selling_flows", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer()), sa.Column("name", sa.String(180), nullable=False), sa.Column("question_json", sa.JSON()), sa.Column("recommendation_json", sa.JSON()), sa.Column("active", sa.Boolean(), server_default=sa.true()), sa.Column("created_by_user_id", sa.Integer()), sa.Column("updated_by_user_id", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.Column("deleted_at", sa.DateTime(timezone=True)))
    op.create_table("crm_quote_srm_conversion_logs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer()), sa.Column("quote_id", sa.Integer(), nullable=False), sa.Column("deal_id", sa.Integer()), sa.Column("srm_sales_order_id", sa.Integer()), sa.Column("srm_contract_id", sa.Integer()), sa.Column("srm_engagement_id", sa.Integer()), sa.Column("srm_billing_plan_id", sa.Integer()), sa.Column("idempotency_key", sa.String(160)), sa.Column("status", sa.String(40), server_default="converted"), sa.Column("message", sa.Text()), sa.Column("payload_json", sa.JSON()), sa.Column("created_by_user_id", sa.Integer()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")))


def downgrade() -> None:
    for table_name in ["crm_quote_srm_conversion_logs", "crm_guided_selling_flows", "crm_cpq_rules", "crm_quote_approvals", "crm_quote_versions", "crm_price_book_items", "crm_price_books", "crm_services"]:
        op.drop_table(table_name)
