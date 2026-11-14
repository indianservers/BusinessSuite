"""Public organization references using only the current business database."""
import re
from sqlalchemy import select
from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan


def organization_references(db, company_ids):
    # Existing companies without a signup use a separate, collision-free namespace.
    result = {ident: f"ORG-C-{ident}" for ident in company_ids}
    if not result:
        return result
    subscription, plan = TenantSubscription.__table__, TenantSubscriptionPlan.__table__
    rows = db.connection().execute(
        select(subscription.c.company_id, subscription.c.config_json, plan.c.code, plan.c.config_json.label("plan_config"))
        .select_from(subscription.outerjoin(plan, plan.c.id == subscription.c.plan_id))
        .where(subscription.c.company_id.in_(result))
    ).mappings()
    for row in rows:
        ident = row["company_id"]
        reference = (row["config_json"] or {}).get("organization_id")
        if isinstance(reference, str) and re.fullmatch(r"ORG-[0-9]+", reference):
            result[ident] = reference
            continue
        # Older approved signups already retain their signup key in this receipt.
        receipt = (row["plan_config"] or {}).get("platform_provisioning", {})
        match = re.fullmatch(r"platform-signup-([0-9]+)", row["code"] or "")
        if match and receipt.get("company_id") == ident:
            result[ident] = f"ORG-{100000000 + int(match[1])}"
    return result
