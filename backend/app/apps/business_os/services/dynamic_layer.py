from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    required_modules: tuple[str, ...]
    reason: str


MODULE_WIDGETS = {
    "fam": ["Cash", "Receivables", "Payables", "GST", "Trial Balance", "P&L", "Balance Sheet"],
    "srm_inventory": ["Stock Value", "Low Stock", "COGS", "GRNI", "Valuation", "HSN Summary", "Gross Margin"],
    "crm_srm": ["Pipeline", "Won Deals", "Sales Orders", "Contracts", "Billing Plans", "Invoices", "Collections"],
    "srm_pms": ["Engagements", "Projects", "Milestones", "Timesheets", "Billing Readiness", "Project Profitability"],
    "full": ["Lead-to-Cash", "Procure-to-Pay", "Project-to-Profit", "Inventory-to-Accounting", "Cash Flow", "Business Health Score"],
}

REPORTS = [
    ReportDefinition("lead_to_cash", "Lead-to-Cash", ("crm", "srm"), "Requires CRM plus SRM or FAM invoicing."),
    ReportDefinition("inventory_valuation", "Inventory Valuation", ("srm",), "Requires Sales & Inventory."),
    ReportDefinition("gst_summary", "GST Summary", ("fam",), "Requires FAM / Accounts."),
    ReportDefinition("project_profitability", "Project Profitability", ("project_management",), "Requires PMS."),
    ReportDefinition("cash_collection", "Cash Collection", ("srm",), "Requires SRM or FAM invoicing."),
    ReportDefinition("stock_cogs", "Stock COGS", ("srm", "fam"), "Requires Sales & Inventory + FAM."),
]

ROLE_CATALOG = [
    {"role": "Accounts Admin", "modules": ["fam"], "permissions": ["fam_view", "fam_manage", "fam_admin", "fam_vouchers_post", "fam_gst_view"]},
    {"role": "Sales & Inventory Manager", "modules": ["srm"], "permissions": ["srm_view", "fam_inventory_view", "fam_inventory_manage", "fam_stock_post"]},
    {"role": "CRM Sales Executive", "modules": ["crm"], "permissions": ["crm_view", "crm_leads_manage", "crm_deals_manage"]},
    {"role": "SRM Finance Manager", "modules": ["srm"], "permissions": ["srm_view", "srm_invoice_view", "srm_invoice_create", "srm_collection_view"]},
    {"role": "PMS Project Manager", "modules": ["project_management"], "permissions": ["project_view", "project_manage", "task_manage"]},
    {"role": "Business Owner", "modules": [], "permissions": ["reports_view", "business_os_view"]},
    {"role": "Auditor", "modules": ["fam"], "permissions": ["fam_audit_view", "fam_ledger_entries_view", "reports_view"]},
    {"role": "Viewer", "modules": [], "permissions": ["reports_view"]},
]

AI_TOPICS = {
    "crm": {"pipeline", "lead", "deal", "quote", "customer"},
    "srm": {"sales order", "contract", "billing", "invoice", "collection", "revenue", "stock", "inventory", "warehouse", "grn", "cogs", "hsn"},
    "project_management": {"project", "task", "timesheet", "milestone", "sprint"},
    "fam": {"accounts", "gst", "ledger", "p&l", "profit and loss", "balance sheet", "trial balance", "audit", "cash", "payable", "receivable"},
}


def has(enabled: set[str], *modules: str) -> bool:
    return all(module in enabled for module in modules)


def dashboard_widgets(enabled: set[str]) -> list[dict[str, str]]:
    widgets: list[str] = []
    if enabled == {"fam"}:
        widgets.extend(MODULE_WIDGETS["fam"])
    elif has(enabled, "fam", "srm") and not ({"crm", "project_management"} & enabled):
        widgets.extend(MODULE_WIDGETS["fam"] + MODULE_WIDGETS["srm_inventory"])
    elif has(enabled, "crm", "srm") and "project_management" not in enabled:
        widgets.extend(MODULE_WIDGETS["crm_srm"])
    elif has(enabled, "srm", "project_management") and "crm" not in enabled:
        widgets.extend(MODULE_WIDGETS["srm_pms"])
    elif has(enabled, "fam", "crm", "srm", "project_management"):
        widgets.extend(MODULE_WIDGETS["full"])
    else:
        if "fam" in enabled:
            widgets.extend(MODULE_WIDGETS["fam"])
        if "srm" in enabled:
            widgets.extend(MODULE_WIDGETS["srm_inventory"])
        if has(enabled, "crm", "srm"):
            widgets.extend(MODULE_WIDGETS["crm_srm"])
        if has(enabled, "srm", "project_management"):
            widgets.extend(MODULE_WIDGETS["srm_pms"])
    return [{"title": title, "status": "enabled", "evidence": "Visible because required modules are enabled."} for title in dict.fromkeys(widgets)]


def module_reports(enabled: set[str]) -> list[dict[str, object]]:
    rows = []
    for report in REPORTS:
        required = set(report.required_modules)
        available = required.issubset(enabled)
        if report.key == "lead_to_cash":
            available = {"crm", "srm"}.issubset(enabled) and (("fam" in enabled) or ("srm" in enabled))
        if report.key == "cash_collection":
            available = bool({"srm", "fam"} & enabled)
        missing = sorted(required - enabled)
        rows.append({
            "key": report.key,
            "title": report.title,
            "enabled": available,
            "required_modules": list(report.required_modules),
            "reason": "Available for enabled modules." if available else f"{report.reason} Missing: {', '.join(missing) or 'billing module'}.",
        })
    return rows


def rbac_catalog(enabled: set[str]) -> list[dict[str, object]]:
    rows = []
    for role in ROLE_CATALOG:
        required = set(role["modules"])
        available = required.issubset(enabled)
        permissions = [perm for perm in role["permissions"] if _permission_visible(perm, enabled)]
        if not required:
            available = True
        rows.append({**role, "available": available, "permissions": permissions, "reason": "Role available." if available else f"Enable {', '.join(sorted(required - enabled))} to use this role."})
    return rows


def customer_720_sections(enabled: set[str]) -> list[dict[str, str]]:
    sections = []
    mapping = [
        ("crm", "CRM", "Leads, contacts, companies, deals, quotes and communications."),
        ("srm", "Sales & Inventory", "Sales orders, POS, stock, contracts, billing plans, invoices and collections."),
        ("project_management", "PMS", "Projects, milestones, tasks, timesheets and delivery health."),
        ("fam", "FAM", "Ledger, receivables, payables, GST and audit evidence."),
    ]
    for module, title, description in mapping:
        if module in enabled:
            sections.append({"module": module, "title": title, "description": description})
    return sections


def ai_answer(enabled: set[str], question: str) -> dict[str, object]:
    q = question.lower()
    matched_module = None
    for module, terms in AI_TOPICS.items():
        if any(term in q for term in terms):
            matched_module = module
            break
    if matched_module and matched_module not in enabled:
        labels = {"crm": "CRM", "srm": "Sales & Inventory", "project_management": "PMS", "fam": "FAM"}
        return {
            "allowed": False,
            "module": matched_module,
            "answer": f"{labels.get(matched_module, matched_module)} is not enabled for this company, so I cannot answer that question or expose its data.",
            "evidence": {"enabled_modules": sorted(enabled)},
        }
    if enabled == {"fam"}:
        allowed_terms = AI_TOPICS["fam"]
        if not any(term in q for term in allowed_terms):
            return {
                "allowed": False,
                "module": "unknown",
                "answer": "Only FAM is enabled. I can answer accounts, GST, ledger, P&L, balance sheet and audit questions only.",
                "evidence": {"enabled_modules": sorted(enabled)},
            }
    return {
        "allowed": True,
        "module": matched_module or "business_os",
        "answer": "Module-aware AI check passed. Live answer generation should use only enabled-module context.",
        "evidence": {"enabled_modules": sorted(enabled)},
    }


def _permission_visible(permission: str, enabled: set[str]) -> bool:
    if permission.startswith("fam_inventory"):
        return "srm" in enabled
    if permission.startswith("fam_"):
        return "fam" in enabled
    if permission.startswith("crm_"):
        return "crm" in enabled
    if permission.startswith("srm_"):
        return "srm" in enabled
    if permission.startswith("project_") or permission.startswith("task_"):
        return "project_management" in enabled
    return True
