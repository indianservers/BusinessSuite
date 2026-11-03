"""Fine-grained keys already enforced by CRM's entity APIs."""
CRM_FEATURE_GROUPS = (
    "leads", "contacts", "accounts", "deals", "activities", "pipeline",
    "targets", "territory", "forecast", "sales_performance", "products",
    "quotes", "price_books", "cpq",
)
CRM_FEATURE_PERMISSIONS = [
    (f"crm_{group}_{action}", f"CRM {group.replace('_', ' ')}: {action}", "crm")
    for group in CRM_FEATURE_GROUPS for action in ("view", "manage")
] + [
    ("crm_quotes_approve", "CRM quotes: approve", "crm"),
    ("crm_quotes_send", "CRM quotes: send", "crm"),
    ("crm_quotes_convert_to_srm", "CRM quotes: convert to sales order", "crm"),
]


def expand_crm_features(permissions):
    """Represent native broad CRM rights as a ceiling for narrower branch keys."""
    names = set(permissions)
    if "crm_admin" in names:
        names.update(name for name, _, _ in CRM_FEATURE_PERMISSIONS)
    elif "crm_manage" in names:
        names.update(f"crm_{group}_{action}" for group in CRM_FEATURE_GROUPS for action in ("view", "manage"))
    elif "crm_view" in names:
        names.update(f"crm_{group}_view" for group in CRM_FEATURE_GROUPS)
    return sorted(names)
