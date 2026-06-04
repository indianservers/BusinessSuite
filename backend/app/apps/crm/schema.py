from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


AUDIT_TABLES = [
    "crm_companies",
    "crm_contacts",
    "crm_leads",
    "crm_lead_scoring_rules",
    "crm_pipelines",
    "crm_pipeline_stages",
    "crm_deals",
    "crm_products",
    "crm_quotations",
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


def ensure_crm_schema(db: Session) -> None:
    """Keep dev databases compatible with CRM models when create_all is used."""
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
        if table_name in {"crm_leads", "crm_companies", "crm_deals"}:
            for column_name, column_type in TERRITORY_RECORD_COLUMNS.items():
                if column_name not in columns:
                    db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
                    columns.add(column_name)
        if table_name == "crm_pipeline_stages" and "organization_id" not in columns:
            db.execute(text("ALTER TABLE crm_pipeline_stages ADD COLUMN organization_id INTEGER"))
            columns.add("organization_id")
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
