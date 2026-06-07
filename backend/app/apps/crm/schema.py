from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.apps.crm.models import (
    CRMAccount,
    CRMCPQRule,
    CRMForecastSnapshot,
    CRMGuidedSellingFlow,
    CRMLeadConversionLog,
    CRMLostReason,
    CRMPriceBook,
    CRMPriceBookItem,
    CRMQuoteApproval,
    CRMQuoteSRMConversionLog,
    CRMQuoteVersion,
    CRMService,
    CRMSalesPerformanceSnapshot,
    CRMSalesTarget,
    CRMTerritoryAssignment,
    CRMTimelineEvent,
)


AUDIT_TABLES = [
    "crm_companies",
    "crm_contacts",
    "crm_leads",
    "crm_lead_scoring_rules",
    "crm_pipelines",
    "crm_pipeline_stages",
    "crm_deals",
    "crm_products",
    "crm_services",
    "crm_price_books",
    "crm_price_book_items",
    "crm_quotations",
    "crm_quotation_items",
    "crm_quote_versions",
    "crm_quote_approvals",
    "crm_cpq_rules",
    "crm_guided_selling_flows",
    "crm_quote_srm_conversion_logs",
    "crm_activities",
    "crm_tasks",
    "crm_notes",
    "crm_email_logs",
    "crm_email_templates",
    "crm_messages",
    "crm_message_templates",
    "calendar_integrations",
    "crm_call_logs",
    "crm_meetings",
    "crm_tickets",
    "crm_campaigns",
    "crm_file_assets",
    "crm_custom_field_values",
    "crm_webhooks",
    "crm_webhook_deliveries",
    "crm_territories",
    "crm_territory_users",
    "crm_territory_assignments",
    "crm_sales_targets",
    "crm_forecast_snapshots",
    "crm_lost_reasons",
    "crm_sales_performance_snapshots",
    "crm_enrichment_logs",
]

ACTIVITY_COLUMNS = {
    "entity_type": "VARCHAR(40)",
    "entity_id": "INTEGER",
    "title": "VARCHAR(220)",
    "body": "TEXT",
    "metadata_json": "JSON",
    "activity_date": "DATETIME",
}

EMAIL_LOG_COLUMNS = {
    "entity_type": "VARCHAR(40)",
    "entity_id": "INTEGER",
    "bcc": "VARCHAR(500)",
    "status": "VARCHAR(30)",
    "provider_message_id": "VARCHAR(160)",
    "failure_reason": "TEXT",
    "sent_by_user_id": "INTEGER",
}

MESSAGE_COLUMNS = {
    "template_id": "INTEGER",
    "failure_reason": "TEXT",
}

MEETING_SYNC_COLUMNS = {
    "external_provider": "VARCHAR(40)",
    "external_event_id": "VARCHAR(180)",
    "sync_status": "VARCHAR(30)",
    "last_synced_at": "DATETIME",
}

LEAD_SCORE_COLUMNS = {
    "lead_score": "INTEGER",
    "lead_score_label": "VARCHAR(20)",
    "lead_score_mode": "VARCHAR(20)",
    "last_score_calculated_at": "DATETIME",
}

CUSTOM_FIELD_COLUMNS = {
    "field_name": "VARCHAR(160)",
    "is_unique": "BOOLEAN",
    "is_visible": "BOOLEAN",
    "is_filterable": "BOOLEAN",
}

DEAL_REPORT_COLUMNS = {
    "lost_reason": "TEXT",
    "win_reason": "TEXT",
    "source": "VARCHAR(80)",
    "won_at": "DATETIME",
    "lost_at": "DATETIME",
    "closed_at": "DATETIME",
}

TERRITORY_COLUMNS = {
    "rules_json": "JSON",
    "priority": "INTEGER",
    "is_active": "BOOLEAN",
    "manager_id": "INTEGER",
    "region": "VARCHAR(120)",
    "product_line": "VARCHAR(120)",
    "service_line": "VARCHAR(120)",
    "active": "BOOLEAN",
}

PIPELINE_COLUMNS = {
    "active": "BOOLEAN",
}

PIPELINE_STAGE_COLUMNS = {
    "organization_id": "INTEGER",
    "order_index": "INTEGER",
    "stage_type": "VARCHAR(20)",
    "active": "BOOLEAN",
}

TERRITORY_RECORD_COLUMNS = {
    "territory_id": "INTEGER",
}

CRM_SCOPE_COLUMNS = {
    "branch_id": "INTEGER",
    "department_id": "INTEGER",
    "assigned_team_id": "INTEGER",
}

ENRICHMENT_LEAD_COLUMNS = {
    "linkedin_url": "VARCHAR(300)",
    "company_website": "VARCHAR(200)",
    "employee_count": "INTEGER",
    "email_verification_status": "VARCHAR(40)",
    "social_profiles_json": "JSON",
}

ENRICHMENT_CONTACT_COLUMNS = {
    "company_name": "VARCHAR(180)",
    "company_website": "VARCHAR(200)",
    "industry": "VARCHAR(120)",
    "employee_count": "INTEGER",
    "email_verification_status": "VARCHAR(40)",
    "social_profiles_json": "JSON",
}

PRODUCT_PHASE3_COLUMNS = {
    "product_code": "VARCHAR(80)",
    "unit_of_measure": "VARCHAR(40)",
    "list_price": "NUMERIC(12, 2)",
    "cost_price": "NUMERIC(12, 2)",
    "active": "BOOLEAN",
}

QUOTATION_PHASE3_COLUMNS = {
    "account_id": "INTEGER",
    "owner_id": "INTEGER",
    "quote_date": "DATE",
    "valid_until": "DATE",
    "approval_status": "VARCHAR(30)",
    "discount_total": "NUMERIC(12, 2)",
    "tax_total": "NUMERIC(12, 2)",
    "grand_total": "NUMERIC(12, 2)",
    "estimated_cost": "NUMERIC(12, 2)",
    "expected_margin": "NUMERIC(12, 2)",
    "margin_percentage": "NUMERIC(8, 2)",
    "version_number": "INTEGER",
    "terms_and_conditions": "TEXT",
    "approved_by": "INTEGER",
    "approved_at": "DATETIME",
    "sent_at": "DATETIME",
    "accepted_at": "DATETIME",
    "declined_at": "DATETIME",
    "converted_srm_sales_order_id": "INTEGER",
    "converted_srm_contract_id": "INTEGER",
    "converted_srm_engagement_id": "INTEGER",
}

QUOTATION_ITEM_PHASE3_COLUMNS = {
    "quote_id": "INTEGER",
    "item_type": "VARCHAR(30)",
    "service_id": "INTEGER",
    "discount_type": "VARCHAR(20)",
    "discount_value": "NUMERIC(12, 2)",
    "line_total": "NUMERIC(12, 2)",
    "estimated_cost": "NUMERIC(12, 2)",
    "margin_amount": "NUMERIC(12, 2)",
    "margin_percentage": "NUMERIC(8, 2)",
    "billing_type": "VARCHAR(40)",
}

QUOTE_APPROVAL_PHASE3_COLUMNS = {
    "approver_user_id": "INTEGER",
    "comments": "TEXT",
}

QUOTE_SRM_CONVERSION_LOG_PHASE3_COLUMNS = {
    "message": "TEXT",
}


def ensure_crm_schema(db: Session) -> None:
    """Keep dev databases compatible with CRM models when create_all is used."""
    inspector = inspect(db.bind)
    tables = set(inspector.get_table_names())
    missing_core_tables = [
        table
        for table in (
            CRMAccount.__table__,
            CRMTimelineEvent.__table__,
            CRMLeadConversionLog.__table__,
            CRMService.__table__,
            CRMPriceBook.__table__,
            CRMPriceBookItem.__table__,
            CRMQuoteVersion.__table__,
            CRMQuoteApproval.__table__,
            CRMCPQRule.__table__,
            CRMGuidedSellingFlow.__table__,
            CRMQuoteSRMConversionLog.__table__,
            CRMTerritoryAssignment.__table__,
            CRMSalesTarget.__table__,
            CRMForecastSnapshot.__table__,
            CRMLostReason.__table__,
            CRMSalesPerformanceSnapshot.__table__,
        )
        if table.name not in tables
    ]
    if missing_core_tables:
        CRMAccount.metadata.create_all(bind=db.bind, tables=missing_core_tables)
        inspector = inspect(db.bind)
        tables = set(inspector.get_table_names())
    for table_name in AUDIT_TABLES:
        if table_name not in tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "created_by_user_id" not in columns:
            db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN created_by_user_id INTEGER"))
        if "updated_by_user_id" not in columns:
            db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN updated_by_user_id INTEGER"))
        if "deleted_at" not in columns and table_name not in {"crm_deal_products", "crm_quotation_items", "crm_campaign_leads", "crm_tags"}:
            db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN deleted_at DATETIME"))
        if table_name in {"crm_email_logs", "crm_call_logs", "crm_meetings"} and "owner_user_id" not in columns:
            db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN owner_user_id INTEGER"))
        if table_name == "crm_email_logs":
            for column_name, column_type in EMAIL_LOG_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_email_logs ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_email_logs SET status = COALESCE(status, 'sent')"))
            db.execute(text("UPDATE crm_email_logs SET entity_type = 'lead', entity_id = lead_id WHERE entity_type IS NULL AND lead_id IS NOT NULL"))
            db.execute(text("UPDATE crm_email_logs SET entity_type = 'contact', entity_id = contact_id WHERE entity_type IS NULL AND contact_id IS NOT NULL"))
            db.execute(text("UPDATE crm_email_logs SET entity_type = 'account', entity_id = company_id WHERE entity_type IS NULL AND company_id IS NOT NULL"))
            db.execute(text("UPDATE crm_email_logs SET entity_type = 'deal', entity_id = deal_id WHERE entity_type IS NULL AND deal_id IS NOT NULL"))
        if table_name == "crm_messages":
            for column_name, column_type in MESSAGE_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_messages ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_meetings":
            for column_name, column_type in MEETING_SYNC_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_meetings ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_meetings SET sync_status = COALESCE(sync_status, 'not_synced')"))
        if table_name == "crm_leads":
            for column_name, column_type in LEAD_SCORE_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_leads ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            for column_name, column_type in ENRICHMENT_LEAD_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_leads ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_leads SET lead_score = COALESCE(lead_score, 0)"))
            db.execute(text("UPDATE crm_leads SET lead_score_label = COALESCE(lead_score_label, rating, 'Cold')"))
            db.execute(text("UPDATE crm_leads SET lead_score_mode = COALESCE(lead_score_mode, 'automatic')"))
        if table_name == "crm_contacts":
            for column_name, column_type in ENRICHMENT_CONTACT_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_contacts ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_products":
            for column_name, column_type in PRODUCT_PHASE3_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_products ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_products SET product_code = COALESCE(product_code, sku)"))
            db.execute(text("UPDATE crm_products SET list_price = COALESCE(list_price, unit_price, 0)"))
            db.execute(text("UPDATE crm_products SET cost_price = COALESCE(cost_price, 0)"))
            db.execute(text("UPDATE crm_products SET active = COALESCE(active, CASE WHEN LOWER(COALESCE(status, 'active')) IN ('active', 'available') THEN 1 ELSE 0 END)"))
        if table_name == "crm_quotations":
            for column_name, column_type in QUOTATION_PHASE3_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_quotations ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_quotations SET account_id = COALESCE(account_id, company_id)"))
            db.execute(text("UPDATE crm_quotations SET owner_id = COALESCE(owner_id, owner_user_id)"))
            db.execute(text("UPDATE crm_quotations SET quote_date = COALESCE(quote_date, issue_date)"))
            db.execute(text("UPDATE crm_quotations SET valid_until = COALESCE(valid_until, expiry_date)"))
            db.execute(text("UPDATE crm_quotations SET approval_status = COALESCE(approval_status, CASE WHEN LOWER(COALESCE(status, 'draft')) IN ('approved', 'sent', 'accepted') THEN 'approved' ELSE 'not_submitted' END)"))
            db.execute(text("UPDATE crm_quotations SET discount_total = COALESCE(discount_total, discount_amount, 0)"))
            db.execute(text("UPDATE crm_quotations SET tax_total = COALESCE(tax_total, tax_amount, 0)"))
            db.execute(text("UPDATE crm_quotations SET grand_total = COALESCE(grand_total, total_amount, 0)"))
            db.execute(text("UPDATE crm_quotations SET estimated_cost = COALESCE(estimated_cost, 0)"))
            db.execute(text("UPDATE crm_quotations SET expected_margin = COALESCE(expected_margin, grand_total - estimated_cost, 0)"))
            db.execute(text("UPDATE crm_quotations SET version_number = COALESCE(version_number, 1)"))
            db.execute(text("UPDATE crm_quotations SET terms_and_conditions = COALESCE(terms_and_conditions, terms)"))
        if table_name == "crm_quotation_items":
            for column_name, column_type in QUOTATION_ITEM_PHASE3_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_quotation_items ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_quotation_items SET quote_id = COALESCE(quote_id, quotation_id)"))
            db.execute(text("UPDATE crm_quotation_items SET item_type = COALESCE(item_type, CASE WHEN product_id IS NULL THEN 'service' ELSE 'product' END)"))
            db.execute(text("UPDATE crm_quotation_items SET discount_type = COALESCE(discount_type, 'amount')"))
            db.execute(text("UPDATE crm_quotation_items SET discount_value = COALESCE(discount_value, discount_amount, 0)"))
            db.execute(text("UPDATE crm_quotation_items SET line_total = COALESCE(line_total, total_amount, 0)"))
            db.execute(text("UPDATE crm_quotation_items SET estimated_cost = COALESCE(estimated_cost, 0)"))
            db.execute(text("UPDATE crm_quotation_items SET margin_amount = COALESCE(margin_amount, line_total - estimated_cost, 0)"))
            db.execute(text("UPDATE crm_quotation_items SET billing_type = COALESCE(billing_type, 'fixed')"))
        if table_name == "crm_quote_approvals":
            for column_name, column_type in QUOTE_APPROVAL_PHASE3_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_quote_approvals ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_quote_srm_conversion_logs":
            for column_name, column_type in QUOTE_SRM_CONVERSION_LOG_PHASE3_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_quote_srm_conversion_logs ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_custom_fields":
            for column_name, column_type in CUSTOM_FIELD_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_custom_fields ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_custom_fields SET field_name = COALESCE(field_name, label)"))
            db.execute(text("UPDATE crm_custom_fields SET is_unique = COALESCE(is_unique, 0)"))
            db.execute(text("UPDATE crm_custom_fields SET is_visible = COALESCE(is_visible, 1)"))
            db.execute(text("UPDATE crm_custom_fields SET is_filterable = COALESCE(is_filterable, 0)"))
        if table_name == "crm_deals":
            for column_name, column_type in DEAL_REPORT_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_deals ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_deals SET lost_reason = COALESCE(lost_reason, loss_reason)"))
            db.execute(text("UPDATE crm_deals SET source = COALESCE(source, lead_source)"))
        if table_name in {"crm_leads", "crm_companies", "crm_contacts", "crm_deals", "crm_quotations", "crm_activities", "crm_tasks"}:
            for column_name, column_type in CRM_SCOPE_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_territories":
            for column_name, column_type in TERRITORY_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_territories ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_territories SET priority = COALESCE(priority, 100)"))
            db.execute(text("UPDATE crm_territories SET is_active = COALESCE(is_active, CASE WHEN status = 'Active' THEN 1 ELSE 0 END)"))
            db.execute(text("UPDATE crm_territories SET active = COALESCE(active, is_active, CASE WHEN status = 'Active' THEN 1 ELSE 0 END)"))
        if table_name == "crm_pipelines":
            for column_name, column_type in PIPELINE_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_pipelines ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_pipelines SET active = COALESCE(active, CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)"))
        if table_name in {"crm_leads", "crm_companies", "crm_deals"}:
            for column_name, column_type in TERRITORY_RECORD_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_pipeline_stages":
            for column_name, column_type in PIPELINE_STAGE_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_pipeline_stages ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_pipeline_stages SET order_index = COALESCE(order_index, position, 0)"))
            db.execute(text("UPDATE crm_pipeline_stages SET stage_type = CASE WHEN COALESCE(is_won, 0) = 1 THEN 'won' WHEN COALESCE(is_lost, 0) = 1 THEN 'lost' ELSE COALESCE(stage_type, 'open') END"))
            db.execute(text("UPDATE crm_pipeline_stages SET active = COALESCE(active, CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)"))
        if table_name == "crm_activities":
            for column_name, column_type in ACTIVITY_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE crm_activities ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
            db.execute(text("UPDATE crm_activities SET title = subject WHERE title IS NULL AND subject IS NOT NULL"))
            db.execute(text("UPDATE crm_activities SET body = description WHERE body IS NULL AND description IS NOT NULL"))
            db.execute(text("UPDATE crm_activities SET activity_date = COALESCE(due_date, completed_at, created_at) WHERE activity_date IS NULL"))
            db.execute(text("UPDATE crm_activities SET entity_type = 'lead', entity_id = lead_id WHERE entity_type IS NULL AND lead_id IS NOT NULL"))
            db.execute(text("UPDATE crm_activities SET entity_type = 'contact', entity_id = contact_id WHERE entity_type IS NULL AND contact_id IS NOT NULL"))
            db.execute(text("UPDATE crm_activities SET entity_type = 'account', entity_id = company_id WHERE entity_type IS NULL AND company_id IS NOT NULL"))
            db.execute(text("UPDATE crm_activities SET entity_type = 'deal', entity_id = deal_id WHERE entity_type IS NULL AND deal_id IS NOT NULL"))
        if "organization_id" in columns:
            db.execute(text(f"UPDATE {table_name} SET organization_id = 1 WHERE organization_id IS NULL"))
    db.commit()
