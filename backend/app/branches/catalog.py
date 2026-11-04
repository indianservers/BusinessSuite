"""Explicit shared catalogues; everything else is branch-private by default."""
from sqlalchemy import String, cast, literal, func
from app.core.tenant_boundary import GLOBAL_CATALOGUES, INTERNAL_TABLES, ACTOR_FIELDS

# Existing company/module authorization continues to protect these definitions.
# Transactional tables must never be added merely to make a screen work.
SHARED = GLOBAL_CATALOGUES | INTERNAL_TABLES | frozenset({
    # Company-admin storage configuration and locator index. Native record
    # permissions still authorize file contents through signed attachment links.
    "file_storage_connections", "file_storage_policies", "file_storage_oauth_states", "file_storage_objects",
    "companies", "suite_access_memberships", "suite_access_policies", "suite_access_roles",
    "suite_access_templates", "suite_access_audit", "suite_branch_policies", "suite_branch_grants",
    "suite_accounting_branch_map", "suite_branch_ownership", "suite_branch_audit",
    "suite_branch_record_shares", "suite_branch_lifecycle",
    # Personal reminder configuration is user-scoped by its API, not a branch transaction.
    "service_follow_up_preferences",
    # Company appearance and shared policy definitions are configuration, not branch transactions.
    "suite_service_policies",
    # Account authorization is company-level configuration. Conversations,
    # messages and receipts remain private business activity with branch ownership.
    "suite_whatsapp_connections", "suite_whatsapp_onboarding",
    "communication_customer_settings",
    "communication_customer_email_connections",
    "users", "user_sessions", "mfa_methods", "trusted_devices", "login_attempts",
    "common_people", "common_profiles", "sso_providers", "sso_domains",
    "crm_products", "crm_services", "srm_products", "shared_catalog_details", "shared_catalog_links",
    "crm_pipelines", "crm_pipeline_stages", "crm_lead_scoring_rules", "crm_lost_reasons",
    "crm_price_books", "crm_price_book_items", "crm_cpq_rules", "crm_custom_fields",
    "crm_email_templates", "crm_message_templates", "crm_guided_selling_flows",
    "fam_company_financial_settings", "fam_financial_years", "fam_accounting_periods",
    "fam_ledger_groups", "fam_voucher_types", "fam_payment_modes",
    "fam_tax_registrations", "fam_gst_rates", "fam_hsn_sac_codes", "fam_tds_sections",
    "fam_tds_rates", "fam_units_of_measure", "fam_stock_groups", "fam_posting_rules",
    "srm_settings", "srm_tax_rates", "srm_units_of_measure", "srm_product_categories",
    # Definitions/toggles are company-wide; their events, results and
    # transactions remain private. These rows do not contain business activity.
    "feature_catalog", "bos_enabled_modules", "bos_integration_rules", "bos_posting_rules",
    "metric_definitions", "business_number_sequences", "tax_declaration_categories",
    "leave_types", "power_apps_environments",
    # Company-wide singleton switches/plans, never branch business activity.
    # Their APIs retain AI-admin/global-configuration permission checks.
    "ai_security_settings", "tenant_subscriptions", "crm_lead_management_config",
    # Provider credentials follow company/user/workspace scope_key authorization,
    # not transaction branch ownership. Tenant and provider API checks still apply.
    "ai_operator_providers",
})

# These links describe ownership, not actors, approvers, or a user assignment.
# Other relationships are still checked on write but never infer ownership.
PARENT_FIELDS = frozenset({
    "employee_id", "department_id", "project_id", "workspace_id", "task_id", "note_id",
    "folder_id", "file_id", "comment_id", "lead_id", "deal_id", "quotation_id", "quote_id",
    "invoice_id", "voucher_id", "sales_order_id", "receipt_id", "purchase_bill_id",
    "warehouse_id", "stock_movement_id", "transfer_id", "notification_id", "reminder_id",
    "conversation_id", "ticket_id", "request_id", "application_id", "submission_id",
    "batch_id", "engagement_id", "contract_id", "billing_plan_id", "order_id", "job_id",
    "crm_deal_id", "crm_quote_id", "crm_company_id", "crm_contact_id", "customer_id",
})
INFERRED = {"crm_deal_id": "crm_deals", "crm_quote_id": "crm_quotations",
            "crm_company_id": "crm_companies", "crm_contact_id": "crm_contacts"}


def polymorphic_parents(table, values, tables):
    # Audit snapshots intentionally outlive the referenced record.
    if "audit" in table.name or table.name.endswith("timeline_events") or table.name == 'bos_lifecycle_events':
        # Lifecycle evidence also records skipped/failed attempts against IDs
        # that never existed. It is a branch-owned snapshot, not a live link.
        return
    module = str(values.get("module") or values.get("source_module") or "").lower()
    crm = table.name.startswith("crm_") or module == "crm"
    pms = table.name.startswith("pms_") or module in {"pms", "project_management"}
    aliases = {"lead": "crm_leads", "deal": "crm_deals", "contact": "crm_contacts", "company": "crm_companies", "account": "crm_companies", "quotation": "crm_quotations"} if crm else {}
    if crm: aliases["task"] = "crm_tasks"
    if pms: aliases.update(project="pms_projects", task="pms_tasks", workspace="pms_workspaces", note="pms_notes")
    for type_name, id_name in (("entity_type", "entity_id"), ("entity", "record_id"), ("related_entity_type", "related_entity_id"), ("related_type", "related_id")):
        value = values.get(id_name)
        kind = str(values.get(type_name) or "").lower().removesuffix("s")
        name = aliases.get(kind)
        if name in tables and value is not None:
            yield tables[name], str(value)


def key_expression(table):
    keys = list(table.primary_key.columns)
    if len(keys) == 1:
        return cast(keys[0], String)
    encoded = [cast(func.length(cast(key, String)), String) + literal(":") + cast(key, String) for key in keys]
    expression = encoded[0]
    for part in encoded[1:]:
        expression = expression + literal(":") + part
    return expression


def resource_key(table, values):
    parts = [str(values[column.name]) for column in table.primary_key.columns]
    return parts[0] if len(parts) == 1 else ":".join(f"{len(value)}:{value}" for value in parts)


def parents(table, tables):
    for column in table.c:
        if column.name in ACTOR_FIELDS or column.name in {"branch_id", "user_id"}:
            continue
        if column.name in {"manager_employee_id", "head_employee_id", "reporting_manager_id", "reviewer_employee_id", "owner_employee_id"}:
            continue
        targets = [(fk.column.table, fk.column) for fk in column.foreign_keys]
        if not targets and column.name in INFERRED and INFERRED[column.name] in tables:
            parent = tables[INFERRED[column.name]]
            targets = [(parent, parent.c.id)]
        for parent, key in targets:
            if parent.name != table.name and parent.name not in SHARED:
                yield column, parent, key


def inventory(metadata):
    result = []
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        links = [f"{column.name}->{parent.name}.{key.name}" for column, parent, key in parents(table, metadata.tables)]
        result.append({"table": table.name, "category": "shared" if table.name in SHARED else "direct" if "branch_id" in table.c or table.name in {"branches", "fam_branches"} else "inherited" if links else "owned-root",
                       "primary_key": [c.name for c in table.primary_key], "ownership_parents": links})
    return result
