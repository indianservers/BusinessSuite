"""Enable approved accounts and release their transactional invitation email."""
from contextlib import nullcontext
from urllib.parse import urlencode

from fastapi import HTTPException
from app.core.config import settings
from app.access.models import AccessMembership, AccessPolicy
from app.models.user import User
from app.models.email_outbox import EmailOutbox
from app.apps.saas.models import TenantSubscriptionPlan


def enable_approved_signup(row, owner_db, business):
    if row.status != "approved":
        raise HTTPException(409, "Signup must be approved before enabling sign-in")
    workspace = None
    context = nullcontext(business)
    if settings.TENANT_DATABASES_ENABLED:
        from app.platform_owner.models import PlatformTenantDatabase
        from app.db.tenant import lookup_route, tenant_session
        placement = owner_db.query(PlatformTenantDatabase).filter_by(signup_id=row.id, status="ready").one()
        workspace = placement.workspace_code
        context = tenant_session(lookup_route(workspace))
    with context as db:
        plan = db.query(TenantSubscriptionPlan).filter_by(code=f"platform-signup-{row.id}").with_for_update().one()
        receipt = (plan.config_json or {}).get("platform_provisioning", {})
        if (receipt.get("user_id"), receipt.get("company_id"), receipt.get("email")) != (row.user_id, row.company_id, row.email):
            raise HTTPException(409, "Approved signup identity does not match its provisioning receipt")
        if receipt.get("signin_ready"):
            return False  # Never reactivate a subsequently suspended account.
        user = db.get(User, row.user_id)
        policy = db.query(AccessPolicy).filter_by(user_id=row.user_id, company_id=row.company_id, status="invited").one_or_none()
        membership = db.query(AccessMembership).filter_by(user_id=row.user_id, company_id=row.company_id, active=True, is_admin=True).first()
        if not user or user.email != row.email or not policy or not membership:
            raise HTTPException(409, "Approved signup account is unavailable for activation")
        user.is_active = True
        policy.status, policy.version = "active", policy.version + 1
        mail = db.query(EmailOutbox).filter_by(event_key=f"signup-approved:{row.id}", status="held_local").one_or_none()
        if mail:
            # Dedicated workspaces need the same routing hint for both login and
            # password setup. Update the held message before making it deliverable.
            if workspace:
                import re
                mail.body = re.sub(r"(/invite-access\?token=[A-Za-z0-9_-]+)(?![A-Za-z0-9_-])", lambda m: m[0] + "&" + urlencode({"tenant": workspace}), mail.body)
                mail.body = mail.body.replace("/login", "/login?" + urlencode({"tenant": workspace}))
            mail.status = "queued"
        plan.config_json = {**plan.config_json, "platform_provisioning": {**receipt, "signin_ready": True}}
        db.commit()
        return True
