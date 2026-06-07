from sqlalchemy.orm import Session

from app.common.services.identity import SharedIdentityService
from app.core.security import get_password_hash
from app.module_registry import is_app_enabled
from app.models.user import Permission, Role, User


COMMON_PERMISSIONS = [
    ("settings_view", "View platform settings", "settings"),
    ("settings_manage", "Manage platform settings", "settings"),
    ("reports_view", "View reports", "reports"),
    ("workflow_view", "View workflow inbox", "workflow"),
    ("notification_view", "View notification inbox", "notification"),
    ("automation_view", "View Automation Studio rules and blueprints", "automation"),
    ("automation_manage", "Manage Automation Studio rules, blueprints, cadences, and assignments", "automation"),
    ("automation_execute", "Execute and test Automation Studio workflows", "automation"),
    ("automation_logs_view", "View Automation Studio execution logs", "automation"),
    ("automation_approval_view", "View Automation Studio approval requests", "automation"),
    ("automation_approval_manage", "Manage Automation Studio approval rules and requests", "automation"),
    ("automation_approval_decide", "Approve or reject Automation Studio approval requests", "automation"),
    ("automation_webhook_manage", "Manage Automation Studio webhook endpoints", "automation"),
    ("customization_view", "View Customization Studio metadata", "customization"),
    ("customization_manage", "Manage Customization Studio metadata and records", "customization"),
    ("customization_modules_manage", "Manage custom modules", "customization"),
    ("customization_fields_manage", "Manage custom fields, formulas, rollups, and picklists", "customization"),
    ("customization_layouts_manage", "Manage custom layouts", "customization"),
    ("customization_views_manage", "Manage custom list and Kanban views", "customization"),
    ("customization_validation_manage", "Manage custom validation rules", "customization"),
    ("customization_buttons_manage", "Manage custom buttons", "customization"),
    ("communication_view", "View CRM Communication Hub", "communication"),
    ("communication_email_send", "Send individual CRM emails", "communication"),
    ("communication_templates_manage", "Manage communication templates", "communication"),
    ("communication_webforms_manage", "Manage CRM webforms and auto responses", "communication"),
    ("communication_campaigns_view", "View CRM campaigns", "communication"),
    ("communication_campaigns_manage", "Manage CRM campaigns", "communication"),
    ("communication_campaigns_send", "Send CRM campaigns", "communication"),
    ("communication_consents_manage", "Manage communication consent and opt-out", "communication"),
    ("communication_logs_view", "View communication delivery logs", "communication"),
    ("analytics_view", "View analytics reports and dashboards", "analytics"),
    ("analytics_manage", "Manage analytics reports and dashboards", "analytics"),
    ("analytics_report_builder", "Build analytics reports", "analytics"),
    ("analytics_export", "Export analytics reports", "analytics"),
    ("analytics_schedule", "Schedule analytics reports", "analytics"),
    ("analytics_financial_view", "View financial analytics", "analytics"),
    ("analytics_profitability_view", "View profitability analytics", "analytics"),
    ("analytics_admin", "Administer analytics and exports", "analytics"),
    ("ai_view", "View AI Copilot outputs and summaries", "ai"),
    ("ai_use", "Use AI Copilot generation endpoints", "ai"),
    ("ai_manage_settings", "Manage AI provider settings", "ai"),
    ("ai_manage_prompts", "Manage AI prompt templates", "ai"),
    ("ai_agent_actions", "Preview and confirm AI agent actions", "ai"),
    ("ai_action_log_view", "View AI action and run logs", "ai"),
    ("admin_security_view", "View enterprise security and governance settings", "admin_security"),
    ("admin_security_manage", "Manage enterprise security and governance settings", "admin_security"),
    ("admin_profiles_manage", "Manage admin profiles", "admin_security"),
    ("admin_roles_manage", "Manage admin role hierarchy", "admin_security"),
    ("admin_field_security_manage", "Manage field-level security", "admin_security"),
    ("admin_record_sharing_manage", "Manage record and data sharing rules", "admin_security"),
    ("admin_import_manage", "Manage governed imports", "admin_security"),
    ("admin_duplicates_manage", "Manage duplicate rules and merges", "admin_security"),
    ("admin_audit_view", "View enterprise audit logs", "admin_security"),
    ("admin_export_control_manage", "Manage export controls", "admin_security"),
    ("admin_compliance_manage", "Manage compliance and retention settings", "admin_security"),
    ("portal_manage", "Manage secure customer and partner portal access", "portal"),
    ("developer_view", "View Developer Hub documentation and logs", "developer"),
    ("developer_manage", "Manage Developer Hub API keys and webhooks", "developer"),
    ("marketplace_view", "View internal marketplace apps", "marketplace"),
    ("marketplace_manage", "Manage internal marketplace apps and installs", "marketplace"),
    ("sandbox_view", "View sandbox requests and status", "sandbox"),
    ("sandbox_manage", "Create and refresh sandbox environments", "sandbox"),
    ("tenant_view", "View tenant company, subscription, and usage settings", "tenant"),
    ("tenant_admin", "Manage tenant company, subscription, usage, and feature gates", "tenant"),
    ("pms_view", "View project management records", "project_management"),
    ("pms_manage_projects", "Manage projects and members", "project_management"),
    ("pms_manage_tasks", "Manage tasks, boards, and milestones", "project_management"),
    ("pms_time_manage", "Manage time logs and approvals", "project_management"),
    ("pms_client_portal", "Access project client portal", "project_management"),
    ("pms_admin", "Manage project settings and admin areas", "project_management"),
    ("srm_view", "View sales and revenue management records", "srm"),
    ("srm_manage", "Manage SRM sales orders, contracts, engagements, and billing", "srm"),
    ("srm_admin", "Administer SRM settings and lifecycle controls", "srm"),
    ("srm_invoice_view", "View SRM invoices", "srm"),
    ("srm_invoice_create", "Create SRM invoice drafts and invoices", "srm"),
    ("srm_invoice_approve", "Approve SRM invoices and sales orders", "srm"),
    ("srm_collection_view", "View SRM collections and aging", "srm"),
    ("srm_collection_create", "Create SRM receipts, allocations, and reminders", "srm"),
    ("srm_profitability_view", "View SRM profitability", "srm"),
    ("srm_settings_manage", "Manage SRM settings", "srm"),
    ("fam_view", "View FAM dashboards and accounting foundation records", "fam"),
    ("fam_manage", "Manage FAM operational accounting foundation records", "fam"),
    ("fam_admin", "Administer FAM company books, chart, and controls", "fam"),
    ("fam_settings_manage", "Manage FAM company financial settings and years", "fam"),
    ("fam_chart_view", "View FAM chart of accounts and ledgers", "fam"),
    ("fam_chart_manage", "Manage FAM chart of accounts and ledgers", "fam"),
    ("fam_opening_balance_view", "View FAM opening balances", "fam"),
    ("fam_opening_balance_manage", "Manage and post FAM opening balances", "fam"),
    ("fam_cost_center_manage", "Manage FAM cost centers", "fam"),
    ("fam_branch_manage", "Manage FAM branches", "fam"),
    ("fam_audit_view", "View FAM audit logs", "fam"),
    ("fam_vouchers_view", "View FAM vouchers", "fam"),
    ("fam_vouchers_create", "Create and update FAM draft vouchers", "fam"),
    ("fam_vouchers_post", "Post balanced FAM vouchers", "fam"),
    ("fam_vouchers_cancel", "Cancel posted FAM vouchers", "fam"),
    ("fam_vouchers_reverse", "Reverse posted FAM vouchers", "fam"),
    ("fam_voucher_types_manage", "Manage FAM voucher types and numbering", "fam"),
    ("fam_ledger_entries_view", "View FAM immutable ledger entries", "fam"),
    ("fam_day_book_view", "View FAM day book", "fam"),
    ("fam_parties_view", "View FAM customers, vendors, and party ledgers", "fam"),
    ("fam_parties_manage", "Manage FAM customers, vendors, and party ledgers", "fam"),
    ("fam_ar_view", "View FAM accounts receivable", "fam"),
    ("fam_ar_manage", "Manage FAM accounts receivable", "fam"),
    ("fam_ap_view", "View FAM accounts payable", "fam"),
    ("fam_ap_manage", "Manage FAM accounts payable", "fam"),
    ("fam_bill_allocation_manage", "Manage FAM bill allocations", "fam"),
    ("fam_party_statement_view", "View FAM customer/vendor statements", "fam"),
    ("fam_srm_integration_view", "View FAM SRM accounting integration", "fam"),
    ("fam_srm_posting_manage", "Post SRM records into FAM accounting", "fam"),
    ("fam_posting_rules_manage", "Manage FAM posting rules", "fam"),
    ("fam_posting_jobs_retry", "Retry failed FAM posting jobs", "fam"),
    ("fam_accounting_status_view", "View FAM accounting status links", "fam"),
    ("fam_banking_view", "View FAM banking and reconciliation records", "fam"),
    ("fam_banking_manage", "Manage FAM banking masters and accounting actions", "fam"),
    ("fam_bank_statement_import", "Import FAM bank statements", "fam"),
    ("fam_bank_reconcile", "Match and reconcile FAM bank statements", "fam"),
    ("fam_cash_book_view", "View FAM cash book", "fam"),
    ("fam_bank_book_view", "View FAM bank book", "fam"),
    ("fam_gst_view", "View FAM GST settings, registers, and readiness records", "fam"),
    ("fam_gst_manage", "Manage FAM GST registrations, rates, and HSN/SAC masters", "fam"),
    ("fam_gst_return_prepare", "Prepare FAM GSTR-1 and GSTR-3B working records", "fam"),
    ("fam_gst_einvoice_manage", "Manage FAM e-invoice readiness jobs and settings", "fam"),
    ("fam_gst_ewaybill_manage", "Manage FAM e-way bill readiness jobs and settings", "fam"),
    ("fam_gst_reconciliation_view", "View FAM GST reconciliation items", "fam"),
    ("fam_purchase_view", "View FAM purchase bills and purchase registers", "fam"),
    ("fam_purchase_manage", "Manage and post FAM purchase bills", "fam"),
    ("fam_expense_view", "View FAM expense claims and expense registers", "fam"),
    ("fam_expense_manage", "Manage and post FAM expense claims", "fam"),
    ("fam_tds_view", "View FAM TDS sections, transactions, and payable reports", "fam"),
    ("fam_tds_manage", "Manage FAM TDS sections, rates, and deductions", "fam"),
    ("fam_vendor_payment_manage", "Prepare and post FAM vendor payment runs", "fam"),
    ("fam_inventory_view", "View FAM inventory masters and stock balances", "fam"),
    ("fam_inventory_manage", "Manage FAM inventory masters", "fam"),
    ("fam_stock_post", "Post FAM stock movements and opening balances", "fam"),
    ("fam_stock_adjust", "Create and post FAM stock adjustments", "fam"),
    ("fam_stock_transfer", "Create and post FAM stock transfers", "fam"),
    ("fam_inventory_valuation_view", "View FAM inventory valuation and item ledgers", "fam"),
    ("fam_cogs_post", "Post FAM inventory COGS vouchers", "fam"),
    ("fam_inventory_reports_view", "View FAM inventory reports", "fam"),
    ("fam_inventory_ai_use", "Use audited FAM inventory AI insights", "fam"),
    ("fam_inventory_reconciliation_view", "View FAM inventory to GL and SRM reconciliation", "fam"),
    ("fam_inventory_gl_post", "Post FAM inventory GL entries", "fam"),
    ("fam_inventory_stock_reserve", "Reserve and release FAM inventory stock", "fam"),
    ("fam_inventory_stock_adjust", "Control FAM inventory stock adjustment settings", "fam"),
    ("fam_inventory_audit_view", "View FAM inventory audit trail", "fam"),
    ("fam_inventory_accounting_view", "View FAM inventory accounting integration", "fam"),
    ("fam_inventory_accounting_manage", "Manage FAM inventory ledger mappings", "fam"),
    ("fam_inventory_post_accounting", "Post inventory accounting vouchers", "fam"),
    ("fam_inventory_cogs_post", "Post inventory COGS vouchers", "fam"),
    ("fam_inventory_reconciliation_manage", "Manage inventory reconciliation controls", "fam"),
    ("fam_inventory_adjustment_post", "Post inventory adjustment accounting", "fam"),
    ("fam_grni_view", "View GRNI reconciliation", "fam"),
    ("fam_grni_manage", "Manage GRNI accounting", "fam"),
]

COMMON_ROLES = [
    {
        "name": "super_admin",
        "description": "Full system access",
        "permissions": [item[0] for item in COMMON_PERMISSIONS],
    }
]


def init_common_db(db: Session) -> None:
    perm_map = {}
    for name, description, module in COMMON_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=description, module=module)
            db.add(perm)
            db.flush()
        perm_map[name] = perm

    for role_data in COMMON_ROLES:
        role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not role:
            role = Role(name=role_data["name"], description=role_data["description"], is_system=True)
            db.add(role)
            db.flush()
        role.permissions = [perm_map[name] for name in role_data["permissions"] if name in perm_map]

    role = db.query(Role).filter(Role.name == "super_admin").first()
    user = db.query(User).filter(User.email == "admin@platform.local").first()
    if not user and role:
        user = User(
            email="admin@platform.local",
            hashed_password=get_password_hash("Admin@123456"),
            is_active=True,
            is_superuser=True,
            role_id=role.id,
        )
        db.add(user)
        db.flush()

    if user:
        SharedIdentityService.ensure_person_for_user(
            db,
            user,
            display_name="Platform Admin",
            source_module="common",
            source_record_type="user",
            source_record_id=user.id,
        )

    if is_app_enabled("hrms"):
        from app.models.employee import Employee

        employees = db.query(Employee).filter(Employee.user_id.isnot(None), Employee.deleted_at.is_(None)).limit(1000).all()
        for employee in employees:
            SharedIdentityService.sync_from_employee(db, employee)

    db.commit()







