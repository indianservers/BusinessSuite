from pathlib import Path

from sqlalchemy import inspect

from app.apps.srm.api.router import (
    BILLING_PLAN_STATUSES,
    COLLECTION_STATUSES,
    CONTRACT_STATUSES,
    ENGAGEMENT_STATUSES,
    INVOICE_STATUSES,
    RECEIPT_STATUSES,
    SALES_ORDER_STATUSES,
)
from app.apps.srm.models import SRMSalesOrder
from app.apps.srm.schema import SRM_TABLE_MODELS, ensure_srm_schema


REQUIRED_SRM_TABLES = {
    "srm_sales_orders",
    "srm_sales_order_lines",
    "srm_contracts",
    "srm_engagements",
    "srm_engagement_links",
    "srm_billing_plans",
    "srm_billing_milestones",
    "srm_invoice_drafts",
    "srm_invoices",
    "srm_invoice_lines",
    "srm_invoice_history",
    "srm_receipts",
    "srm_receipt_allocations",
    "srm_collection_reminders",
    "srm_customer_aging",
    "srm_profitability_snapshots",
    "srm_revenue_events",
    "srm_audit_logs",
    "srm_settings",
}


def test_srm_required_operational_tables_exist(db):
    ensure_srm_schema(db)
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    assert REQUIRED_SRM_TABLES.issubset(tables)
    assert {model.__tablename__ for model in SRM_TABLE_MODELS} == REQUIRED_SRM_TABLES


def test_srm_cross_module_reference_columns_are_operational_not_reused_crm_pms(db):
    inspector = inspect(db.bind)
    sales_order_columns = {column["name"] for column in inspector.get_columns("srm_sales_orders")}
    engagement_columns = {column["name"] for column in inspector.get_columns("srm_engagements")}
    invoice_columns = {column["name"] for column in inspector.get_columns("srm_invoices")}

    assert {"crm_deal_id", "crm_quote_id", "crm_company_id", "crm_contact_id", "customer_id", "assigned_user_id", "created_by", "approved_by"}.issubset(sales_order_columns)
    assert {"crm_deal_id", "crm_quote_id", "pms_project_id", "customer_id", "assigned_user_id", "created_by"}.issubset(engagement_columns)
    assert {"sales_order_id", "engagement_id", "customer_id", "created_by", "approved_by"}.issubset(invoice_columns)
    assert SRMSalesOrder.__tablename__ == "srm_sales_orders"


def test_srm_status_catalogs_match_required_phase_2_flows():
    assert SALES_ORDER_STATUSES == {"draft", "pending_approval", "approved", "confirmed", "cancelled", "closed"}
    assert CONTRACT_STATUSES == {"draft", "under_review", "active", "expired", "terminated", "renewed"}
    assert ENGAGEMENT_STATUSES == {"created", "project_pending", "project_created", "delivery_in_progress", "billing_in_progress", "completed", "closed"}
    assert BILLING_PLAN_STATUSES == {"draft", "active", "paused", "completed", "cancelled"}
    assert INVOICE_STATUSES == {"draft", "pending_approval", "approved", "sent", "partially_paid", "paid", "overdue", "cancelled"}
    assert RECEIPT_STATUSES == {"draft", "confirmed", "allocated", "partially_allocated", "cancelled"}
    assert COLLECTION_STATUSES == {"not_due", "due", "overdue", "escalated", "collected", "written_off"}


def test_srm_alembic_migration_exists():
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260604_002_srm_database_core.py"
    assert migration.exists()
    contents = migration.read_text()
    assert 'revision = "20260604_002"' in contents
    assert "SRM_TABLES" in contents
    assert "table.create" in contents
