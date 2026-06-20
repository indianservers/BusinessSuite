from datetime import date
from sqlalchemy.orm import Session
from app.core.security import get_password_hash
from app.models.user import User, Role, Permission, UserSession, MFAMethod, LoginAttempt
from app.models.target import FeatureCatalog, FeaturePlan, IndustryTarget
from app.models.company import Branch, Company, Department, Designation
from app.models.employee import Employee
from app.models.leave import LeaveType
from app.models.sso import SSOProvider, SSOSession  # noqa: F401


SYSTEM_PERMISSIONS = [
    # Company
    ("company_view", "View company settings", "company"),
    ("company_manage", "Manage company settings", "company"),
    # Employees
    ("employee_view", "View employees", "employee"),
    ("employee_sensitive_view", "View sensitive employee personal, bank, and statutory fields", "employee"),
    ("employee_create", "Create employees", "employee"),
    ("employee_update", "Update employees", "employee"),
    ("employee_delete", "Delete employees", "employee"),
    # Attendance
    ("attendance_view", "View attendance", "attendance"),
    ("attendance_manage", "Manage attendance", "attendance"),
    # Leave
    ("leave_view", "View leave requests", "leave"),
    ("leave_apply", "Apply for leave", "leave"),
    ("leave_approve", "Approve leave requests", "leave"),
    ("leave_manage", "Manage leave types and balances", "leave"),
    # Payroll
    ("payroll_view", "View payroll", "payroll"),
    ("payroll_run", "Run payroll", "payroll"),
    ("payroll_approve", "Approve payroll", "payroll"),
    # Recruitment
    ("recruitment_view", "View recruitment", "recruitment"),
    ("recruitment_manage", "Manage recruitment", "recruitment"),
    # Performance
    ("performance_view", "View performance reviews", "performance"),
    ("performance_manage", "Manage performance reviews", "performance"),
    # Helpdesk
    ("helpdesk_view", "View helpdesk tickets", "helpdesk"),
    ("helpdesk_manage", "Manage helpdesk tickets", "helpdesk"),
    # Reports
    ("reports_view", "View reports", "reports"),
    ("reports_manage", "Manage report builder definitions", "reports"),
    # Settings / platform
    ("settings_view", "View platform settings", "settings"),
    ("settings_manage", "Manage platform settings", "settings"),
    # Workflow
    ("workflow_view", "View workflow inbox", "workflow"),
    ("approval_os_view", "View centralized approval operating system", "approval_os"),
    ("approval_os_create", "Create centralized approval requests", "approval_os"),
    ("approval_os_admin", "Administer centralized approvals, escalations, and audit", "approval_os"),
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
    # Notifications
    ("notification_view", "View notification inbox", "notification"),
    ("notification_manage", "Manage notifications and delivery hooks", "notification"),
    # Employee import/export
    ("employee_import", "Import employees in bulk", "employee"),
    ("employee_export", "Export employees", "employee"),
    # Timesheets
    ("timesheet_view", "View projects and timesheets", "timesheet"),
    ("timesheet_manage", "Manage project master data", "timesheet"),
    ("timesheet_approve", "Approve submitted timesheets", "timesheet"),
    # Targets
    ("targets_view", "View target markets and feature plans", "targets"),
    ("targets_manage", "Manage target markets and feature plans", "targets"),
    # Assets
    ("asset_view", "View assets", "asset"),
    ("asset_manage", "Manage assets", "asset"),
    # Exit
    ("exit_view", "View exit records", "exit"),
    ("exit_manage", "Manage exit process", "exit"),
    # AI
    ("ai_assistant", "Use AI assistant", "ai"),
    # CRM
    ("crm_view", "View CRM records and dashboards", "crm"),
    ("crm_manage", "Manage CRM records", "crm"),
    ("crm_pipeline_manage", "Manage CRM pipelines and deals", "crm"),
    ("crm_support_manage", "Manage CRM support tickets", "crm"),
    ("crm_marketing_manage", "Manage CRM campaigns", "crm"),
    ("crm_admin", "Manage CRM settings and admin areas", "crm"),
    # Project Management
    ("pms_view", "View project management records", "project_management"),
    ("pms_manage_projects", "Manage projects and members", "project_management"),
    ("pms_manage_tasks", "Manage tasks, boards, and milestones", "project_management"),
    ("pms_time_manage", "Manage time logs and approvals", "project_management"),
    ("pms_client_portal", "Access project client portal", "project_management"),
    ("pms_admin", "Manage project settings and admin areas", "project_management"),
    # Sales & Inventory Management
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
    # Finance & Accounting Management
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
    ("fam_import_manage", "Upload, validate, and post FAM imports", "fam"),
    ("fam_export_view", "Generate and download permission-filtered FAM exports", "fam"),
    ("fam_integrity_view", "Run FAM data integrity checks", "fam"),
    ("fam_period_close_manage", "Run FAM period close checks and lock periods", "fam"),
    ("fam_ai_accounting_use", "Use audited FAM accounting AI assistance", "fam"),
    ("fam_final_certification_view", "View FAM final certification readiness", "fam"),
]

SYSTEM_ROLES = [
    {
        "name": "super_admin",
        "description": "Full system access",
        "permissions": [p[0] for p in SYSTEM_PERMISSIONS],
    },
    {
        "name": "hr_manager",
        "description": "HR Manager with full HR access",
        "permissions": [
            "company_view", "employee_view", "employee_create", "employee_update",
            "employee_sensitive_view", "employee_import", "employee_export",
            "attendance_view", "attendance_manage", "leave_view", "leave_approve", "leave_manage",
            "payroll_view", "payroll_run", "recruitment_view", "recruitment_manage",
            "performance_view", "performance_manage", "helpdesk_view", "helpdesk_manage",
            "reports_view", "reports_manage", "settings_view", "settings_manage",
            "asset_view", "asset_manage", "exit_view", "exit_manage", "ai_assistant",
            "timesheet_view", "timesheet_manage", "timesheet_approve",
            "targets_view", "targets_manage", "workflow_view", "approval_os_view", "approval_os_create", "approval_os_admin",
            "notification_view", "notification_manage",
        ],
    },
    {
        "name": "ceo",
        "description": "Executive leadership dashboard access",
        "permissions": [
            "company_view", "employee_view", "attendance_view", "leave_view",
            "payroll_view", "recruitment_view", "performance_view", "reports_view",
            "timesheet_view",
            "targets_view", "workflow_view", "approval_os_view", "notification_view", "ai_assistant",
        ],
    },
    {
        "name": "manager",
        "description": "Department manager",
        "permissions": [
            "employee_view", "attendance_view", "leave_view", "leave_approve",
            "payroll_view", "performance_view", "performance_manage", "helpdesk_view",
            "reports_view", "ai_assistant",
            "timesheet_view", "timesheet_approve",
            "targets_view", "workflow_view", "approval_os_view",
            "notification_view",
        ],
    },
    {
        "name": "employee",
        "description": "Regular employee - self-service only",
        "permissions": [
            "attendance_view", "leave_view", "leave_apply", "payroll_view",
            "performance_view", "helpdesk_view", "ai_assistant",
            "timesheet_view",
            "targets_view", "workflow_view", "approval_os_view",
            "notification_view",
        ],
    },
    {
        "name": "crm_super_admin",
        "description": "CRM platform super admin",
        "permissions": ["crm_view", "crm_manage", "crm_pipeline_manage", "crm_support_manage", "crm_marketing_manage", "crm_admin", "reports_view", "settings_view", "approval_os_view", "approval_os_create", "approval_os_admin", "automation_view", "automation_manage", "automation_execute", "automation_logs_view", "automation_approval_view", "automation_approval_manage", "automation_approval_decide", "automation_webhook_manage", "customization_view", "customization_manage", "customization_modules_manage", "customization_fields_manage", "customization_layouts_manage", "customization_views_manage", "customization_validation_manage", "customization_buttons_manage", "communication_view", "communication_email_send", "communication_templates_manage", "communication_webforms_manage", "communication_campaigns_view", "communication_campaigns_manage", "communication_campaigns_send", "communication_consents_manage", "communication_logs_view", "analytics_view", "analytics_manage", "analytics_report_builder", "analytics_export", "analytics_schedule", "analytics_financial_view", "analytics_profitability_view", "analytics_admin"],
    },
    {
        "name": "crm_org_admin",
        "description": "CRM organization admin",
        "permissions": ["crm_view", "crm_manage", "crm_pipeline_manage", "crm_support_manage", "crm_marketing_manage", "crm_admin", "reports_view", "settings_view", "approval_os_view", "approval_os_create", "approval_os_admin", "automation_view", "automation_manage", "automation_execute", "automation_logs_view", "automation_approval_view", "automation_approval_manage", "automation_approval_decide", "automation_webhook_manage", "customization_view", "customization_manage", "customization_modules_manage", "customization_fields_manage", "customization_layouts_manage", "customization_views_manage", "customization_validation_manage", "customization_buttons_manage", "communication_view", "communication_email_send", "communication_templates_manage", "communication_webforms_manage", "communication_campaigns_view", "communication_campaigns_manage", "communication_campaigns_send", "communication_consents_manage", "communication_logs_view", "analytics_view", "analytics_manage", "analytics_report_builder", "analytics_export", "analytics_schedule", "analytics_financial_view", "analytics_profitability_view", "analytics_admin"],
    },
    {
        "name": "crm_sales_manager",
        "description": "CRM sales manager",
        "permissions": ["crm_view", "crm_manage", "crm_pipeline_manage", "reports_view", "notification_view", "approval_os_view", "automation_view", "automation_approval_view", "automation_approval_decide", "communication_view", "communication_email_send", "communication_campaigns_view", "analytics_view", "analytics_report_builder", "analytics_export"],
    },
    {
        "name": "crm_sales_executive",
        "description": "CRM sales executive",
        "permissions": ["crm_view", "crm_manage", "crm_pipeline_manage", "notification_view", "automation_execute", "automation_approval_view", "communication_view", "communication_email_send", "analytics_view"],
    },
    {
        "name": "crm_support_agent",
        "description": "CRM support agent",
        "permissions": ["crm_view", "crm_support_manage", "notification_view"],
    },
    {
        "name": "crm_marketing_user",
        "description": "CRM marketing user",
        "permissions": ["crm_view", "crm_marketing_manage", "notification_view", "communication_view", "communication_templates_manage", "communication_webforms_manage", "communication_campaigns_view", "communication_campaigns_manage", "communication_campaigns_send", "communication_logs_view"],
    },
    {
        "name": "crm_viewer",
        "description": "CRM read-only viewer",
        "permissions": ["crm_view", "reports_view", "communication_view", "analytics_view"],
    },
    {
        "name": "pms_super_admin",
        "description": "Project management platform super admin",
        "permissions": ["pms_view", "pms_manage_projects", "pms_manage_tasks", "pms_time_manage", "pms_client_portal", "pms_admin", "reports_view", "settings_view", "approval_os_view", "approval_os_create", "approval_os_admin"],
    },
    {
        "name": "pms_org_admin",
        "description": "Project management organization admin",
        "permissions": ["pms_view", "pms_manage_projects", "pms_manage_tasks", "pms_time_manage", "pms_client_portal", "pms_admin", "reports_view", "settings_view", "approval_os_view", "approval_os_create", "approval_os_admin"],
    },
    {
        "name": "pms_project_manager",
        "description": "Project manager",
        "permissions": ["pms_view", "pms_manage_projects", "pms_manage_tasks", "pms_time_manage", "reports_view", "notification_view", "approval_os_view"],
    },
    {
        "name": "pms_team_member",
        "description": "Project team member",
        "permissions": ["pms_view", "pms_manage_tasks", "pms_time_manage", "notification_view"],
    },
    {
        "name": "pms_client",
        "description": "Project client portal user",
        "permissions": ["pms_view", "pms_client_portal", "notification_view"],
    },
    {
        "name": "pms_viewer",
        "description": "Project management read-only viewer",
        "permissions": ["pms_view", "reports_view"],
    },
    {
        "name": "srm_admin",
        "description": "SRM administrator",
        "permissions": ["srm_view", "srm_manage", "srm_admin", "srm_invoice_view", "srm_invoice_create", "srm_invoice_approve", "srm_collection_view", "srm_collection_create", "srm_profitability_view", "srm_settings_manage", "reports_view", "approval_os_view", "approval_os_create", "approval_os_admin", "notification_view"],
    },
    {
        "name": "srm_sales_manager",
        "description": "Sales manager with team sales and revenue visibility",
        "permissions": ["srm_view", "srm_manage", "srm_invoice_view", "srm_collection_view", "srm_profitability_view", "reports_view", "approval_os_view", "notification_view"],
    },
    {
        "name": "srm_sales_executive",
        "description": "Sales executive with assigned SRM records",
        "permissions": ["srm_view", "srm_manage", "notification_view"],
    },
    {
        "name": "srm_finance_manager",
        "description": "Finance manager for invoices and receipts",
        "permissions": ["srm_view", "srm_invoice_view", "srm_invoice_create", "srm_invoice_approve", "srm_collection_view", "srm_collection_create", "srm_profitability_view", "reports_view", "approval_os_view", "notification_view", "automation_approval_view", "automation_approval_decide"],
    },
    {
        "name": "srm_revenue_manager",
        "description": "Revenue manager for recognition and profitability",
        "permissions": ["srm_view", "srm_invoice_view", "srm_profitability_view", "reports_view", "notification_view"],
    },
    {
        "name": "srm_collection_executive",
        "description": "Collection executive for receipts and reminders",
        "permissions": ["srm_collection_view", "srm_collection_create", "notification_view"],
    },
    {
        "name": "srm_business_owner",
        "description": "Business owner dashboards and reports",
        "permissions": ["srm_view", "srm_invoice_view", "srm_collection_view", "srm_profitability_view", "reports_view", "approval_os_view", "notification_view"],
    },
    {
        "name": "srm_viewer",
        "description": "SRM read-only viewer",
        "permissions": ["srm_view", "srm_invoice_view", "srm_collection_view", "reports_view"],
    },
    {
        "name": "fam_admin",
        "description": "FAM administrator",
        "permissions": ["fam_view", "fam_manage", "fam_admin", "fam_settings_manage", "fam_chart_view", "fam_chart_manage", "fam_opening_balance_view", "fam_opening_balance_manage", "fam_cost_center_manage", "fam_branch_manage", "fam_audit_view", "fam_vouchers_view", "fam_vouchers_create", "fam_vouchers_post", "fam_vouchers_cancel", "fam_vouchers_reverse", "fam_voucher_types_manage", "fam_ledger_entries_view", "fam_day_book_view", "fam_parties_view", "fam_parties_manage", "fam_ar_view", "fam_ar_manage", "fam_ap_view", "fam_ap_manage", "fam_bill_allocation_manage", "fam_party_statement_view", "fam_srm_integration_view", "fam_srm_posting_manage", "fam_posting_rules_manage", "fam_posting_jobs_retry", "fam_accounting_status_view", "fam_banking_view", "fam_banking_manage", "fam_bank_statement_import", "fam_bank_reconcile", "fam_cash_book_view", "fam_bank_book_view", "fam_gst_view", "fam_gst_reconciliation_view", "fam_purchase_view", "fam_purchase_manage", "fam_expense_view", "fam_expense_manage", "fam_tds_view", "fam_tds_manage", "fam_vendor_payment_manage", "fam_inventory_view", "fam_inventory_manage", "fam_stock_post", "fam_stock_adjust", "fam_stock_transfer", "fam_inventory_valuation_view", "fam_cogs_post", "fam_inventory_reports_view", "fam_inventory_ai_use", "fam_inventory_reconciliation_view", "fam_inventory_gl_post", "fam_inventory_stock_reserve", "fam_inventory_stock_adjust", "fam_inventory_audit_view", "fam_inventory_accounting_view", "fam_inventory_accounting_manage", "fam_inventory_post_accounting", "fam_inventory_cogs_post", "fam_inventory_reconciliation_manage", "fam_inventory_adjustment_post", "fam_grni_view", "fam_grni_manage", "reports_view", "notification_view"],
    },
    {
        "name": "accountant",
        "description": "FAM accountant",
        "permissions": ["fam_view", "fam_manage", "fam_chart_view", "fam_chart_manage", "fam_opening_balance_view", "fam_opening_balance_manage", "fam_cost_center_manage", "fam_branch_manage", "fam_vouchers_view", "fam_vouchers_create", "fam_vouchers_post", "fam_ledger_entries_view", "fam_day_book_view", "fam_parties_view", "fam_parties_manage", "fam_ar_view", "fam_ar_manage", "fam_ap_view", "fam_ap_manage", "fam_bill_allocation_manage", "fam_party_statement_view", "fam_srm_integration_view", "fam_srm_posting_manage", "fam_posting_jobs_retry", "fam_accounting_status_view", "fam_banking_view", "fam_banking_manage", "fam_bank_statement_import", "fam_bank_reconcile", "fam_cash_book_view", "fam_bank_book_view", "fam_gst_view", "fam_gst_reconciliation_view", "fam_purchase_view", "fam_purchase_manage", "fam_expense_view", "fam_expense_manage", "fam_tds_view", "fam_tds_manage", "fam_vendor_payment_manage", "fam_inventory_view", "fam_inventory_manage", "fam_stock_post", "fam_stock_adjust", "fam_stock_transfer", "fam_inventory_valuation_view", "fam_cogs_post", "fam_inventory_reports_view", "fam_inventory_ai_use", "fam_inventory_reconciliation_view", "fam_inventory_gl_post", "fam_inventory_stock_reserve", "fam_inventory_stock_adjust", "fam_inventory_audit_view", "fam_inventory_accounting_view", "fam_inventory_accounting_manage", "fam_inventory_post_accounting", "fam_inventory_cogs_post", "fam_inventory_reconciliation_manage", "fam_inventory_adjustment_post", "fam_grni_view", "fam_grni_manage", "reports_view", "notification_view"],
    },
    {
        "name": "finance_manager",
        "description": "FAM finance manager",
        "permissions": ["fam_view", "fam_manage", "fam_chart_view", "fam_chart_manage", "fam_opening_balance_view", "fam_opening_balance_manage", "fam_cost_center_manage", "fam_branch_manage", "fam_audit_view", "fam_vouchers_view", "fam_vouchers_create", "fam_vouchers_post", "fam_vouchers_cancel", "fam_vouchers_reverse", "fam_voucher_types_manage", "fam_ledger_entries_view", "fam_day_book_view", "fam_parties_view", "fam_parties_manage", "fam_ar_view", "fam_ar_manage", "fam_ap_view", "fam_ap_manage", "fam_bill_allocation_manage", "fam_party_statement_view", "fam_srm_integration_view", "fam_srm_posting_manage", "fam_posting_rules_manage", "fam_posting_jobs_retry", "fam_accounting_status_view", "fam_banking_view", "fam_banking_manage", "fam_bank_statement_import", "fam_bank_reconcile", "fam_cash_book_view", "fam_bank_book_view", "fam_gst_view", "fam_gst_reconciliation_view", "fam_purchase_view", "fam_purchase_manage", "fam_expense_view", "fam_expense_manage", "fam_tds_view", "fam_tds_manage", "fam_vendor_payment_manage", "fam_inventory_view", "fam_inventory_manage", "fam_stock_post", "fam_stock_adjust", "fam_stock_transfer", "fam_inventory_valuation_view", "fam_cogs_post", "fam_inventory_reports_view", "fam_inventory_ai_use", "fam_inventory_reconciliation_view", "fam_inventory_gl_post", "fam_inventory_stock_reserve", "fam_inventory_stock_adjust", "fam_inventory_audit_view", "fam_inventory_accounting_view", "fam_inventory_accounting_manage", "fam_inventory_post_accounting", "fam_inventory_cogs_post", "fam_inventory_reconciliation_manage", "fam_inventory_adjustment_post", "fam_grni_view", "fam_grni_manage", "reports_view", "notification_view"],
    },
    {
        "name": "auditor",
        "description": "FAM read-only auditor",
        "permissions": ["fam_view", "fam_chart_view", "fam_opening_balance_view", "fam_audit_view", "fam_vouchers_view", "fam_ledger_entries_view", "fam_day_book_view", "fam_parties_view", "fam_ar_view", "fam_ap_view", "fam_party_statement_view", "fam_srm_integration_view", "fam_accounting_status_view", "fam_banking_view", "fam_cash_book_view", "fam_bank_book_view", "fam_gst_view", "fam_gst_reconciliation_view", "fam_purchase_view", "fam_expense_view", "fam_tds_view", "reports_view"],
    },
    {
        "name": "business_owner",
        "description": "FAM business owner read-only dashboard access",
        "permissions": ["fam_view", "fam_chart_view", "fam_opening_balance_view", "fam_vouchers_view", "fam_ledger_entries_view", "fam_day_book_view", "fam_parties_view", "fam_ar_view", "fam_ap_view", "fam_party_statement_view", "fam_banking_view", "fam_cash_book_view", "fam_bank_book_view", "fam_gst_view", "fam_gst_reconciliation_view", "fam_purchase_view", "fam_expense_view", "fam_tds_view", "reports_view"],
    },
    {
        "name": "fam_viewer",
        "description": "FAM read-only viewer",
        "permissions": ["fam_view", "fam_chart_view", "fam_opening_balance_view", "fam_vouchers_view", "fam_ledger_entries_view", "fam_day_book_view", "fam_parties_view", "fam_ar_view", "fam_ap_view", "fam_party_statement_view", "fam_banking_view", "fam_cash_book_view", "fam_bank_book_view", "fam_gst_view", "fam_gst_reconciliation_view", "fam_purchase_view", "fam_expense_view", "fam_tds_view", "reports_view"],
    },
    {
        "name": "non_fam_employee",
        "description": "Employee without FAM access",
        "permissions": ["notification_view"],
    },
]

AI_ROLE_PERMISSION_ADDITIONS = {
    "crm_super_admin": ["ai_view", "ai_use", "ai_manage_prompts", "ai_agent_actions", "ai_action_log_view", "admin_security_view", "admin_security_manage", "admin_profiles_manage", "admin_roles_manage", "admin_field_security_manage", "admin_record_sharing_manage", "admin_import_manage", "admin_duplicates_manage", "admin_audit_view", "admin_export_control_manage", "admin_compliance_manage", "portal_manage", "developer_view", "developer_manage", "marketplace_view", "marketplace_manage", "sandbox_view", "sandbox_manage", "tenant_view", "tenant_admin"],
    "crm_org_admin": ["ai_view", "ai_use", "ai_manage_prompts", "ai_agent_actions", "ai_action_log_view", "admin_security_view", "admin_profiles_manage", "admin_roles_manage", "admin_field_security_manage", "admin_record_sharing_manage", "admin_import_manage", "admin_duplicates_manage", "admin_audit_view", "admin_export_control_manage", "admin_compliance_manage", "portal_manage", "developer_view", "developer_manage", "marketplace_view", "marketplace_manage", "sandbox_view", "sandbox_manage", "tenant_view", "tenant_admin"],
    "crm_sales_manager": ["ai_view", "ai_use", "ai_agent_actions", "ai_action_log_view"],
    "crm_sales_executive": ["ai_view", "ai_use", "ai_agent_actions"],
    "crm_viewer": ["ai_view"],
    "pms_super_admin": ["ai_view", "ai_use", "ai_agent_actions", "ai_action_log_view"],
    "pms_org_admin": ["ai_view", "ai_use", "ai_agent_actions", "ai_action_log_view"],
    "pms_project_manager": ["ai_view", "ai_use", "ai_agent_actions"],
    "pms_team_member": ["ai_view", "ai_use"],
    "srm_admin": ["ai_view", "ai_use", "ai_manage_prompts", "ai_agent_actions", "ai_action_log_view"],
    "srm_sales_manager": ["ai_view", "ai_use", "ai_agent_actions"],
    "srm_sales_executive": ["ai_view", "ai_use"],
    "srm_finance_manager": ["ai_view", "ai_use", "ai_agent_actions", "ai_action_log_view"],
    "srm_revenue_manager": ["ai_view", "ai_use"],
    "srm_collection_executive": ["ai_view", "ai_use", "ai_agent_actions"],
    "srm_business_owner": ["ai_view", "ai_use", "ai_action_log_view"],
    "srm_viewer": ["ai_view"],
    "fam_admin": ["ai_view", "ai_use", "ai_action_log_view"],
    "accountant": ["ai_view", "ai_use"],
    "finance_manager": ["ai_view", "ai_use", "ai_action_log_view"],
    "auditor": ["ai_view"],
    "business_owner": ["ai_view", "ai_use"],
    "fam_viewer": ["ai_view"],
    "ceo": ["ai_view", "ai_use", "ai_action_log_view", "admin_security_view", "admin_audit_view", "portal_manage", "developer_view", "marketplace_view", "sandbox_view", "tenant_view"],
}


DEMO_USERS = [
    {
        "email": "admin@aihrms.com",
        "password": "Admin@123456",
        "role": "super_admin",
        "is_superuser": True,
    },
    {
        "email": "hr@aihrms.com",
        "password": "HR@123456",
        "role": "hr_manager",
        "is_superuser": False,
    },
    {
        "email": "manager@aihrms.com",
        "password": "Manager@123456",
        "role": "manager",
        "is_superuser": False,
    },
    {
        "email": "employee@aihrms.com",
        "password": "Employee@123456",
        "role": "employee",
        "is_superuser": False,
    },
    {
        "email": "admin@vyaparacrm.com",
        "password": "Password@123",
        "role": "crm_org_admin",
        "is_superuser": False,
    },
    {
        "email": "manager@vyaparacrm.com",
        "password": "Password@123",
        "role": "crm_sales_manager",
        "is_superuser": False,
    },
    {
        "email": "executive@vyaparacrm.com",
        "password": "Password@123",
        "role": "crm_sales_executive",
        "is_superuser": False,
    },
    {
        "email": "support@vyaparacrm.com",
        "password": "Password@123",
        "role": "crm_support_agent",
        "is_superuser": False,
    },
    {
        "email": "marketing@vyaparacrm.com",
        "password": "Password@123",
        "role": "crm_marketing_user",
        "is_superuser": False,
    },
    {
        "email": "admin@karyaflow.com",
        "password": "Password@123",
        "role": "pms_org_admin",
        "is_superuser": False,
    },
    {
        "email": "manager@karyaflow.com",
        "password": "Password@123",
        "role": "pms_project_manager",
        "is_superuser": False,
    },
    {
        "email": "member@karyaflow.com",
        "password": "Password@123",
        "role": "pms_team_member",
        "is_superuser": False,
    },
    {
        "email": "client@karyaflow.com",
        "password": "Password@123",
        "role": "pms_client",
        "is_superuser": False,
    },
    {
        "email": "admin@srmflow.com",
        "password": "Password@123",
        "role": "srm_admin",
        "is_superuser": False,
    },
    {
        "email": "sales.manager@srmflow.com",
        "password": "Password@123",
        "role": "srm_sales_manager",
        "is_superuser": False,
    },
    {
        "email": "sales.executive@srmflow.com",
        "password": "Password@123",
        "role": "srm_sales_executive",
        "is_superuser": False,
    },
    {
        "email": "finance@srmflow.com",
        "password": "Password@123",
        "role": "srm_finance_manager",
        "is_superuser": False,
    },
    {
        "email": "collections@srmflow.com",
        "password": "Password@123",
        "role": "srm_collection_executive",
        "is_superuser": False,
    },
    {
        "email": "owner@srmflow.com",
        "password": "Password@123",
        "role": "srm_business_owner",
        "is_superuser": False,
    },
    {
        "email": "admin@financeflow.com",
        "password": "Password@123",
        "role": "fam_admin",
        "is_superuser": False,
    },
    {
        "email": "accountant@financeflow.com",
        "password": "Password@123",
        "role": "accountant",
        "is_superuser": False,
    },
    {
        "email": "finance.manager@financeflow.com",
        "password": "Password@123",
        "role": "finance_manager",
        "is_superuser": False,
    },
    {
        "email": "auditor@financeflow.com",
        "password": "Password@123",
        "role": "auditor",
        "is_superuser": False,
    },
    {
        "email": "viewer@financeflow.com",
        "password": "Password@123",
        "role": "fam_viewer",
        "is_superuser": False,
    },
]

DEFAULT_LEAVE_TYPES = [
    {
        "name": "Casual Leave",
        "code": "CL",
        "description": "Short planned or unplanned personal leave.",
        "days_allowed": 12,
        "accrual_frequency": "monthly",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "All",
        "applicable_from_months": 0,
        "half_day_allowed": True,
        "color": "#2563EB",
    },
    {
        "name": "Sick Leave",
        "code": "SL",
        "description": "Medical leave for illness or recovery.",
        "days_allowed": 12,
        "accrual_frequency": "monthly",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "All",
        "applicable_from_months": 0,
        "half_day_allowed": True,
        "color": "#16A34A",
    },
    {
        "name": "Earned Leave",
        "code": "EL",
        "description": "Privilege leave accrued for longer planned absence.",
        "days_allowed": 15,
        "accrual_frequency": "monthly",
        "carry_forward": True,
        "carry_forward_limit": 30,
        "encashable": True,
        "applicable_gender": "All",
        "applicable_from_months": 3,
        "half_day_allowed": True,
        "color": "#7C3AED",
    },
    {
        "name": "Maternity Leave",
        "code": "ML",
        "description": "Statutory maternity leave for eligible employees.",
        "days_allowed": 182,
        "accrual_frequency": "annual",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "Female",
        "applicable_from_months": 0,
        "half_day_allowed": False,
        "color": "#DB2777",
    },
    {
        "name": "Paternity Leave",
        "code": "PL",
        "description": "Leave for new fathers around childbirth or adoption.",
        "days_allowed": 5,
        "accrual_frequency": "annual",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "Male",
        "applicable_from_months": 0,
        "half_day_allowed": False,
        "color": "#0EA5E9",
    },
    {
        "name": "Compensatory Off",
        "code": "CO",
        "description": "Time off granted against approved extra work.",
        "days_allowed": 0,
        "accrual_frequency": "annual",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "All",
        "applicable_from_months": 0,
        "half_day_allowed": True,
        "color": "#F97316",
    },
    {
        "name": "Loss of Pay",
        "code": "LOP",
        "description": "Unpaid leave when paid balance is unavailable or not applicable.",
        "days_allowed": 0,
        "accrual_frequency": "annual",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "All",
        "applicable_from_months": 0,
        "half_day_allowed": True,
        "color": "#64748B",
    },
    {
        "name": "Bereavement Leave",
        "code": "BL",
        "description": "Leave for loss in immediate family.",
        "days_allowed": 3,
        "accrual_frequency": "annual",
        "carry_forward": False,
        "carry_forward_limit": 0,
        "encashable": False,
        "applicable_gender": "All",
        "applicable_from_months": 0,
        "half_day_allowed": False,
        "color": "#334155",
    },
]


INDUSTRY_TARGETS = [
    {
        "name": "Technology & Services",
        "slug": "technology-services",
        "headline": "Powerful HCM for technology and white collar services companies.",
        "description": "Employee experience, skills, projects, performance, helpdesk, payroll, and analytics built for fast-moving services teams.",
        "icon": "cpu",
        "color": "blue",
        "sort_order": 10,
    },
    {
        "name": "Pharma & Manufacturing",
        "slug": "pharma-manufacturing",
        "headline": "HR and payroll for blue-collar and white-collar workforces.",
        "description": "Shift rosters, overtime, statutory compliance, attendance, safety notes, document control, and approvals for regulated operations.",
        "icon": "factory",
        "color": "green",
        "sort_order": 20,
    },
    {
        "name": "Banks & Financial Services",
        "slug": "banks-financial-services",
        "headline": "Complete HCM and payroll where compliance and audit are mandatory.",
        "description": "RBAC, audit logs, maker-checker approvals, document evidence, payroll locks, and robust reporting for financial institutions.",
        "icon": "landmark",
        "color": "violet",
        "sort_order": 30,
    },
    {
        "name": "Retail & Other Industries",
        "slug": "retail-other-industries",
        "headline": "One HR platform for distributed stores and field teams.",
        "description": "Mobile-first self-service, geo attendance, store staffing, leave, helpdesk, and instant updates from anywhere.",
        "icon": "store",
        "color": "amber",
        "sort_order": 40,
    },
]

FEATURE_PLANS = [
    {
        "code": "essential",
        "name": "Essential Automation",
        "tagline": "Core HRMS automation for every domain.",
        "strength": "A complete hire-to-retire operating base for HR, employees, managers, and finance.",
        "sort_order": 10,
        "features": {
            "Core HR": [
                "Company and legal entity setup", "Branch, location, department, cost center, and designation hierarchy",
                "Employee master record", "Dynamic employee profiles", "Employee lifecycle status tracking",
                "Probation and confirmation tracking", "Reporting manager mapping", "Organization chart",
                "Employee directory", "Custom employee fields", "Bulk employee import", "Employee ID sequencing",
                "Role based access control", "Permission templates", "Employee timeline", "Audit trail baseline",
            ],
            "Time and Attendance": [
                "Leave types and policies", "Leave balance accruals", "Leave application workflow",
                "Leave approval workflow", "Holiday calendar", "Attendance check-in and check-out",
                "Daily attendance register", "Shift setup", "Grace minutes", "Monthly attendance summary",
                "Attendance regularization", "Team attendance view", "Late coming and early leaving flags",
            ],
            "Payroll and Expense": [
                "Salary components", "Salary structures", "Employee salary assignment",
                "Monthly payroll run", "Payroll approval", "Payslip generation", "Basic deductions",
                "Statutory identifiers", "Reimbursement capture", "Payroll reports",
            ],
            "Recruitment": [
                "Job requisitions", "Job openings", "Candidate database", "Candidate stages",
                "Resume upload", "Interview scheduling", "Interview feedback", "Offer creation",
            ],
            "Onboarding": [
                "Onboarding templates", "New hire onboarding tasks", "Policy acknowledgements",
                "Joining document collection", "Welcome checklist",
            ],
            "Documents": [
                "Document templates", "Employee document repository", "Generated letters",
                "Policy library", "Document expiry tracking", "Document verification status",
            ],
            "Performance": [
                "Appraisal cycles", "Individual goals", "Goal progress tracking",
                "Performance reviews", "Reviewer assignment", "Rating capture",
            ],
            "Employee Self Service": [
                "Email login", "Employee profile self-service", "Leave self-service",
                "Attendance self-service", "Payslip self-service", "Document self-service",
                "Notification inbox",
            ],
            "Helpdesk": [
                "Helpdesk categories", "Employee tickets", "Ticket assignment",
                "Ticket status workflow", "Ticket replies", "AI suggested helpdesk reply",
            ],
            "Reports and Analytics": [
                "Headcount dashboard", "Department headcount report", "Attendance trend report",
                "Leave trend report", "Payroll summary report", "Recruitment funnel report",
            ],
        },
    },
    {
        "code": "strength",
        "name": "Strength",
        "tagline": "Advanced automation for distributed and regulated workforces.",
        "strength": "All Essential features plus deeper workforce management, compliance, employee service, and operational analytics.",
        "sort_order": 20,
        "features": {
            "Core HR": [
                "Multi-company tenant model", "Business unit hierarchy", "Grade and band management",
                "Position management", "Job profile library", "Delegation of authority",
                "Maker-checker employee changes", "Configurable approval chains", "Advanced audit logs",
                "Data retention rules", "Employee data completeness score", "HR operations calendar",
            ],
            "Workforce Management": [
                "Advanced shift roster", "Rotational shifts", "Split shifts", "Weekly offs",
                "Shift swaps", "Roster publishing", "Overtime calculation", "Comp-off rules",
                "Selfie attendance", "Geo-fenced attendance", "Continuous field location punching",
                "Biometric device integration", "Timesheets", "Project time capture",
            ],
            "Payroll and Compliance": [
                "Payroll lock and unlock", "Payroll variance checks", "AI payroll anomaly detection",
                "Loans and salary advances", "Perks and benefits", "Gratuity tracking",
                "Bonus and incentives", "Full and final settlement", "Accounting integration",
                "Country and state compliance profiles", "Tax declaration and proof collection",
            ],
            "Recruitment and Talent Acquisition": [
                "Hiring plans", "Job approval workflow", "Career site readiness", "Candidate source tracking",
                "Resume parsing", "Interview panel management", "Evaluation scorecards",
                "Offer approval workflow", "Offer letter templates", "Candidate conversion to employee",
            ],
            "Learning and Development": [
                "Course catalog", "Training calendar", "Learning assignments", "Training attendance",
                "Certification tracking", "Skill gap mapping", "Manager nominated learning",
            ],
            "Employee Service Delivery": [
                "HR case management", "SLA tracking", "Knowledge base", "Employee query management",
                "Internal comments", "Escalation rules", "Canned responses",
            ],
            "Assets and Travel": [
                "Asset categories", "Asset inventory", "Asset assignment", "Asset return workflow",
                "Asset condition tracking", "Travel requests", "Travel approvals", "Travel expense linkage",
            ],
            "Employee Experience": [
                "Announcements", "Polls", "Pulse surveys", "Public praise", "Recognition badges",
                "Employee social wall", "Company values tagging", "Birthday and work anniversary moments",
            ],
            "Security and Identity": [
                "Single sign-on", "Mobile OTP login", "MFA readiness", "IP restrictions",
                "Device/session tracking", "Privilege review", "Sensitive field masking",
            ],
            "Reports and Analytics": [
                "People analytics", "Attrition risk analysis", "Absence analytics",
                "Payroll variance dashboard", "Compliance dashboard", "Manager dashboards",
                "Custom report filters", "Scheduled reports",
            ],
        },
    },
    {
        "code": "growth",
        "name": "Growth",
        "tagline": "Talent, skills, culture, and business performance management.",
        "strength": "All Strength features plus strategic workforce planning, talent development, compensation, and skills intelligence.",
        "sort_order": 30,
        "features": {
            "Workflow Automation": [
                "No-code workflow builder", "Workflow triggers", "Conditional approvals",
                "Parallel approvals", "Escalation matrix", "Task automation", "Notification automation",
                "Form builder", "Custom objects", "Custom report builder",
            ],
            "Workforce Planning": [
                "Headcount planning", "Position budget", "Workforce scenarios", "Open role forecasting",
                "Attrition impact planning", "Internal mobility planning", "Succession bench strength",
            ],
            "Business Performance": [
                "Company goals and OKRs", "Department goals", "Individual goals",
                "Goal alignment map", "Goal check-ins", "Goal insights", "Core values",
                "Business review dashboards", "KPI ownership", "Performance calibration",
            ],
            "Employee Performance": [
                "Continuous feedback", "One-on-one meetings", "360 degree feedback",
                "Self-appraisals", "Manager appraisals", "Peer reviews", "Performance review templates",
                "Promotion recommendations", "Performance improvement plans", "Performance insights",
                "Nine-box talent grid", "Succession planning", "Career pathing",
            ],
            "Skills and Learning Intelligence": [
                "Skills library", "Competency framework", "Role skill requirements",
                "Employee skill matrix", "Skill endorsements", "Skill proficiency history",
                "Skill analytics", "Learning recommendations", "Internal opportunity marketplace",
            ],
            "Compensation Management": [
                "Compensation bands", "Salary review cycles", "Merit increase planning",
                "Bonus planning", "Equity grant tracking", "Compensation budgets",
                "Pay equity analysis", "Manager compensation worksheets",
            ],
            "Engagement and Culture": [
                "Engagement surveys", "Anonymous feedback", "eNPS", "Sentiment trends",
                "Recognition programs", "Awards marketplace", "Culture analytics",
            ],
            "AI and Copilot": [
                "HR assistant", "Policy Q&A", "Resume parser", "Attrition predictor",
                "Payroll anomaly detector", "Helpdesk reply generator", "Employee profile summaries",
                "Goal writing assistant", "Review summary assistant",
            ],
            "Integrations": [
                "Open API", "Webhook events", "Accounting connector", "Email connector",
                "Calendar connector", "ATS connector", "LMS connector", "Biometric connector",
                "Document e-sign connector", "Data import and export jobs",
            ],
        },
    },
    {
        "code": "global-enterprise",
        "name": "Global Enterprise",
        "tagline": "Mega-suite readiness for any industry and country.",
        "strength": "Enterprise governance, localization, domain-specific workforce rules, and platform extensibility.",
        "sort_order": 40,
        "features": {
            "Global Core HR": [
                "Multi-country worker records", "Multiple worker types", "Contingent workforce",
                "Global addresses and identifiers", "Localization packs", "Country-specific documents",
                "Legal entity transfers", "Global mobility", "Visa and immigration tracking",
            ],
            "Benefits and Wellbeing": [
                "Benefits plans", "Benefit eligibility rules", "Benefit enrollment",
                "Insurance dependents", "Wellness programs", "Health checks", "Employee assistance programs",
                "Wellbeing analytics",
            ],
            "Industrial Workforce": [
                "Factory line staffing", "Production shift handover", "Safety incidents",
                "PPE issuance", "Medical fitness", "Training compliance", "Contract labor attendance",
                "Union agreement rules",
            ],
            "Retail and Field Workforce": [
                "Store staffing", "Area manager hierarchy", "Field route plans", "Beat plans",
                "Geo attendance", "Offline attendance capture", "Mobile task lists", "Store transfer workflow",
            ],
            "BFSI and Regulated Workforce": [
                "Maker-checker approvals", "Segregation of duties", "Fit and proper checks",
                "Regulatory certification", "Policy attestations", "Payroll and document lock",
                "Investigation case files", "Evidence retention",
            ],
            "Healthcare Workforce": [
                "Clinical credentialing", "License expiry", "Duty roster", "On-call scheduling",
                "Department privileges", "Vaccination records", "Occupational health tracking",
            ],
            "Education Workforce": [
                "Academic departments", "Faculty workload", "Course allocation", "Research profile",
                "Publication records", "Grant participation", "Academic calendar alignment",
            ],
            "Platform Governance": [
                "Tenant configuration", "Feature flags", "Domain feature packs", "Data residency settings",
                "Consent management", "Privacy requests", "Legal hold", "Field-level audit",
                "Data quality rules", "Master data governance",
            ],
            "Advanced Analytics": [
                "Workforce data lake", "Metric definitions", "Dashboard builder", "Predictive workforce models",
                "Cost analytics", "Productivity analytics", "Diversity analytics", "Compliance analytics",
            ],
        },
    },
]


def init_db(db: Session) -> None:
    # Create permissions
    perm_map = {}
    for name, description, module in SYSTEM_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=description, module=module)
            db.add(perm)
            db.flush()
        perm_map[name] = perm

    # Create roles
    role_map = {}
    for role_data in SYSTEM_ROLES:
        role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not role:
            role = Role(name=role_data["name"], description=role_data["description"], is_system=True)
            db.add(role)
            db.flush()
        role.permissions = [perm_map[p] for p in role_data["permissions"] if p in perm_map]
        for permission_name in AI_ROLE_PERMISSION_ADDITIONS.get(role_data["name"], []):
            permission = perm_map.get(permission_name)
            if permission and permission not in role.permissions:
                role.permissions.append(permission)
        role_map[role_data["name"]] = role

    db.commit()

    # Seed common leave types for a realistic starting policy.
    for item in DEFAULT_LEAVE_TYPES:
        leave_type = db.query(LeaveType).filter(LeaveType.code == item["code"]).first()
        if not leave_type:
            db.add(LeaveType(**item))
        else:
            for key, value in item.items():
                setattr(leave_type, key, value)

    db.commit()

    # Seed target markets and feature plans
    for item in INDUSTRY_TARGETS:
        target = db.query(IndustryTarget).filter(IndustryTarget.slug == item["slug"]).first()
        if not target:
            db.add(IndustryTarget(**item))

    for plan_data in FEATURE_PLANS:
        features = plan_data.pop("features")
        plan = db.query(FeaturePlan).filter(FeaturePlan.code == plan_data["code"]).first()
        if not plan:
            plan = FeaturePlan(**plan_data)
            db.add(plan)
            db.flush()
        else:
            for key, value in plan_data.items():
                setattr(plan, key, value)
        order = 0
        for module, names in features.items():
            for name in names:
                exists = (
                    db.query(FeatureCatalog)
                    .filter(FeatureCatalog.plan_id == plan.id, FeatureCatalog.module == module, FeatureCatalog.name == name)
                    .first()
                )
                if not exists:
                    db.add(
                        FeatureCatalog(
                            plan_id=plan.id,
                            module=module,
                            name=name,
                            sort_order=order,
                            is_highlight=name in {"Payroll Automation", "People Analytics", "Performance Reviews", "Geo Fencing"},
                        )
                    )
                order += 1
        plan_data["features"] = features

    db.commit()

    # Demo organization used by seeded role logins.
    company = db.query(Company).filter(Company.name == "Demo Company").first()
    if not company:
        company = Company(name="Demo Company", legal_name="Demo Company Pvt Ltd")
        db.add(company)
        db.flush()
    company_id = company.id

    branch = db.query(Branch).filter(Branch.company_id == company_id, Branch.name == "Head Office").first()
    if not branch:
        branch = Branch(name="Head Office", code="HO", company_id=company_id, city="Bengaluru", state="Karnataka")
        db.add(branch)
        db.flush()
    branch_id = branch.id

    department = db.query(Department).filter(Department.branch_id == branch_id, Department.name == "People Operations").first()
    if not department:
        department = Department(name="People Operations", code="HR", branch_id=branch_id)
        db.add(department)
        db.flush()
    department_id = department.id

    designation = db.query(Designation).filter(Designation.department_id == department_id, Designation.name == "HRMS User").first()
    if not designation:
        designation = Designation(name="HRMS User", code="USER", department_id=department_id)
        db.add(designation)
        db.flush()
    designation_id = designation.id

    # Seed role-based demo users: Admin, HR, Manager, and Employee.
    seeded_user_ids = {}
    for item in DEMO_USERS:
        user = db.query(User).filter(User.email == item["email"]).first()
        if not user:
            user = User(
                email=item["email"],
                hashed_password=get_password_hash(item["password"]),
                is_active=True,
                is_superuser=item["is_superuser"],
                role_id=role_map[item["role"]].id,
            )
            db.add(user)
            db.flush()
        else:
            user.hashed_password = get_password_hash(item["password"])
            user.role_id = role_map[item["role"]].id
            user.is_superuser = item["is_superuser"]
            user.is_active = True
            user.password_reset_token = None
            user.password_reset_expires = None
            user.mfa_enabled = False
            user.mfa_enforced_at = None
            user.sso_provider_id = None
            db.query(UserSession).filter(UserSession.user_id == user.id).delete(synchronize_session=False)
            db.query(MFAMethod).filter(MFAMethod.user_id == user.id).delete(synchronize_session=False)
            db.query(LoginAttempt).filter(LoginAttempt.user_id == user.id).delete(synchronize_session=False)
            db.query(LoginAttempt).filter(LoginAttempt.email == item["email"]).delete(synchronize_session=False)
        seeded_user_ids[item["role"]] = user.id
    db.commit()

    from app.module_registry import is_app_enabled

    if is_app_enabled("crm"):
        from app.apps.crm.schema import ensure_crm_schema
        from app.apps.crm.seed import seed_crm_demo_data

        ensure_crm_schema(db)
        seed_crm_demo_data(db, organization_id=company_id)

    manager_employee = db.query(Employee).filter(Employee.employee_id == "DEMO-MGR-001").first()
    if not manager_employee:
        manager_employee = Employee(
            employee_id="DEMO-MGR-001",
            first_name="Maya",
            last_name="Manager",
            personal_email="manager@aihrms.com",
            date_of_joining=date(2024, 1, 1),
            user_id=seeded_user_ids["manager"],
            branch_id=branch_id,
            department_id=department_id,
            designation_id=designation_id,
            status="Active",
        )
        db.add(manager_employee)
        db.flush()

    employee = db.query(Employee).filter(Employee.employee_id == "DEMO-EMP-001").first()
    if not employee:
        employee = Employee(
            employee_id="DEMO-EMP-001",
            first_name="Esha",
            last_name="Employee",
            personal_email="employee@aihrms.com",
            date_of_joining=date(2024, 2, 1),
            user_id=seeded_user_ids["employee"],
            branch_id=branch_id,
            department_id=department_id,
            designation_id=designation_id,
            reporting_manager_id=manager_employee.id,
            status="Active",
        )
        db.add(employee)

    db.commit()









