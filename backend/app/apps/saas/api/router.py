from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.apps.crm.models import CRMDeal, CRMLead, CRMQuotation
from app.apps.project_management.models import PMSProject
from app.apps.saas.models import (
    DeveloperAPIKey,
    DeveloperAPILog,
    DeveloperWebhook,
    DeveloperWebhookDelivery,
    MarketplaceApp,
    MarketplaceInstall,
    MobileSalesVisitCheckIn,
    PortalAccessGrant,
    PortalActivityLog,
    PortalCustomerLink,
    PortalPartnerLink,
    PortalRole,
    PortalSession,
    PortalUser,
    SandboxCopyJob,
    SandboxEnvironment,
    TenantCompanySetting,
    TenantFeatureFlag,
    TenantSubscription,
    TenantSubscriptionPlan,
    TenantUsageMetric,
)
from app.apps.saas.schemas import (
    APIKeyPayload,
    CheckInPayload,
    CompanySettingsPayload,
    FeatureFlagPayload,
    MarketplaceAppPayload,
    PartnerLeadPayload,
    PortalInvitePayload,
    PortalUserPayload,
    SandboxPayload,
    SubscriptionPayload,
    SubscriptionPlanPayload,
    WebhookPayload,
)
from app.apps.srm.models import SRMEngagement, SRMInvoice, SRMSalesOrder
from app.core.deps import RequirePermission, get_current_user, get_db
from app.core.security import get_password_hash
from app.models.user import User


router = APIRouter(tags=["SaaS Packaging"])

EDITION_FEATURES = {
    "starter": {"crm_core"},
    "professional": {"crm_core", "crm_quotes", "basic_automation"},
    "enterprise": {"crm_core", "crm_quotes", "basic_automation", "srm", "pms", "advanced_analytics", "security"},
    "ultimate": {"crm_core", "crm_quotes", "basic_automation", "srm", "pms", "advanced_analytics", "security", "ai", "portals", "developer_hub", "marketplace", "sandbox"},
}


def _serialize(item) -> dict[str, Any] | None:
    if item is None:
        return None
    data: dict[str, Any] = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        if column.name in {"key_hash", "secret_hash", "password_hash", "session_token_hash"}:
            continue
        data[column.name] = value
    return data


def _items(rows) -> dict[str, Any]:
    rows = list(rows)
    return {"items": [_serialize(row) for row in rows], "total": len(rows)}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _portal_log(db: Session, portal_user: PortalUser, event_type: str, resource_type: str | None = None, resource_id: int | None = None, detail: dict[str, Any] | None = None) -> None:
    db.add(PortalActivityLog(portal_user_id=portal_user.id, portal_type=portal_user.portal_type, event_type=event_type, resource_type=resource_type, resource_id=resource_id, detail_json=detail or {}))


def _developer_log(db: Session, user: User, endpoint: str, method: str, status_code: int, api_key: DeveloperAPIKey | None = None) -> None:
    db.add(DeveloperAPILog(api_key_id=api_key.id if api_key else None, key_prefix=api_key.key_prefix if api_key else None, endpoint=endpoint, method=method, status_code=status_code, actor_user_id=user.id))


def _ensure_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Webhook target URL must be absolute HTTPS.")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(status_code=422, detail="Developer webhooks cannot target localhost.")
    return url


def _portal_session(db: Session, token: str | None, expected_type: str) -> PortalUser:
    if not token:
        raise HTTPException(status_code=403, detail="Portal session required")
    session = db.query(PortalSession).filter(PortalSession.session_token_hash == _hash(token), PortalSession.status == "active").first()
    now = datetime.now(timezone.utc)
    if not session or (session.expires_at and session.expires_at.replace(tzinfo=timezone.utc) < now):
        raise HTTPException(status_code=403, detail="Portal session invalid")
    user = db.query(PortalUser).filter(PortalUser.id == session.portal_user_id, PortalUser.status == "active", PortalUser.portal_type == expected_type).first()
    if not user:
        raise HTTPException(status_code=403, detail="Portal user not allowed")
    session.last_seen_at = now
    return user


def _customer_user(db: Session = Depends(get_db), x_portal_session: str | None = Header(default=None, alias="X-Portal-Session")) -> PortalUser:
    return _portal_session(db, x_portal_session, "customer")


def _partner_user(db: Session = Depends(get_db), x_portal_session: str | None = Header(default=None, alias="X-Portal-Session")) -> PortalUser:
    return _portal_session(db, x_portal_session, "partner")


def _customer_ids(db: Session, user: PortalUser) -> list[int]:
    return [row.customer_id for row in db.query(PortalCustomerLink).filter(PortalCustomerLink.portal_user_id == user.id, PortalCustomerLink.active.is_(True)).all()]


def _partner_ids(db: Session, user: PortalUser) -> list[int]:
    return [row.partner_id for row in db.query(PortalPartnerLink).filter(PortalPartnerLink.portal_user_id == user.id, PortalPartnerLink.active.is_(True)).all()]


def _ensure_default_plans(db: Session) -> None:
    for code, features in EDITION_FEATURES.items():
        if not db.query(TenantSubscriptionPlan).filter(TenantSubscriptionPlan.code == code).first():
            db.add(TenantSubscriptionPlan(code=code, name=code.title(), features_json=sorted(features), active=True))
    db.flush()
    if not db.query(TenantSubscription).first():
        ultimate = db.query(TenantSubscriptionPlan).filter(TenantSubscriptionPlan.code == "ultimate").first()
        db.add(TenantSubscription(plan_id=ultimate.id if ultimate else None, edition="ultimate", status="active", admin_override=True))


def _feature_allowed(db: Session, feature_key: str, current_user: User | None = None) -> dict[str, Any]:
    if current_user and current_user.is_superuser:
        return {"allowed": True, "feature_key": feature_key, "source": "superuser"}
    subscription = db.query(TenantSubscription).order_by(TenantSubscription.id.desc()).first()
    if not subscription:
        _ensure_default_plans(db)
        subscription = db.query(TenantSubscription).order_by(TenantSubscription.id.desc()).first()
    if subscription and subscription.admin_override:
        return {"allowed": True, "feature_key": feature_key, "source": "admin_override"}
    flag = db.query(TenantFeatureFlag).filter(TenantFeatureFlag.feature_key == feature_key).first()
    if flag and not flag.enabled:
        return {"allowed": False, "feature_key": feature_key, "message": flag.upgrade_message or "Feature disabled. Upgrade or enable this feature."}
    edition = (subscription.edition if subscription else "ultimate").lower()
    allowed = feature_key in EDITION_FEATURES.get(edition, set())
    return {"allowed": allowed, "feature_key": feature_key, "edition": edition, "message": None if allowed else "This feature requires a higher subscription edition."}


@router.get("/portals/users")
def list_portal_users(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("portal_manage", "tenant_admin"))):
    return _items(db.query(PortalUser).order_by(PortalUser.created_at.desc()).all())


@router.post("/portals/users", status_code=201)
def create_portal_user(data: PortalUserPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("portal_manage", "tenant_admin"))):
    if db.query(PortalUser).filter(PortalUser.email == data.email).first():
        raise HTTPException(status_code=409, detail="Portal user already exists")
    role = db.query(PortalRole).filter(PortalRole.portal_type == data.portal_type).first()
    if not role:
        role = PortalRole(name=f"{data.portal_type.title()} Portal User", portal_type=data.portal_type, permissions_json=["view"])
        db.add(role)
        db.flush()
    user = PortalUser(email=data.email, display_name=data.display_name, portal_type=data.portal_type, role_id=role.id, status="active", created_by=current_user.id)
    db.add(user)
    db.flush()
    if data.portal_type == "customer" and data.customer_id:
        db.add(PortalCustomerLink(portal_user_id=user.id, customer_id=data.customer_id, active=True))
    if data.portal_type == "partner" and data.partner_id:
        db.add(PortalPartnerLink(portal_user_id=user.id, partner_id=data.partner_id, partner_name=data.display_name, active=True))
    _portal_log(db, user, "portal_user_created", "portal_user", user.id)
    db.commit()
    return _serialize(user)


@router.post("/portals/invite", status_code=201)
def invite_portal_user(data: PortalInvitePayload, request: Request, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("portal_manage", "tenant_admin"))):
    created = create_portal_user(PortalUserPayload(**data.model_dump()), db, current_user)
    user = db.query(PortalUser).filter(PortalUser.id == created["id"]).first()
    token = secrets.token_urlsafe(32)
    session = PortalSession(portal_user_id=user.id, session_token_hash=_hash(token), status="active", ip_address=request.client.host if request.client else None, expires_at=datetime.now(timezone.utc) + timedelta(days=14))
    db.add(session)
    user.status = "active"
    _portal_log(db, user, "portal_invite_issued", "portal_user", user.id, {"permissions": data.permissions})
    db.commit()
    return {**_serialize(user), "one_time_session_token": token, "message": "Portal invite created. Token is shown once for testing/onboarding."}


@router.get("/customer-portal/me")
def customer_me(db: Session = Depends(get_db), portal_user: PortalUser = Depends(_customer_user)):
    _portal_log(db, portal_user, "customer_portal_profile_viewed")
    db.commit()
    return {"user": _serialize(portal_user), "customer_ids": _customer_ids(db, portal_user)}


@router.get("/customer-portal/quotes")
def customer_quotes(db: Session = Depends(get_db), portal_user: PortalUser = Depends(_customer_user)):
    customer_ids = _customer_ids(db, portal_user)
    rows = []
    if customer_ids:
        rows = db.query(CRMQuotation).filter(CRMQuotation.account_id.in_(customer_ids)).all() if hasattr(CRMQuotation, "account_id") else []
    _portal_log(db, portal_user, "customer_quotes_viewed", detail={"count": len(rows)})
    db.commit()
    return _items(rows)


@router.post("/customer-portal/quotes/{quote_id}/accept")
def accept_customer_quote(quote_id: int, db: Session = Depends(get_db), portal_user: PortalUser = Depends(_customer_user)):
    customer_ids = _customer_ids(db, portal_user)
    quote = db.query(CRMQuotation).filter(CRMQuotation.id == quote_id).first()
    if not quote or (hasattr(quote, "account_id") and quote.account_id not in customer_ids):
        raise HTTPException(status_code=404, detail="Quote not available in customer portal")
    if hasattr(quote, "status"):
        quote.status = "accepted"
    _portal_log(db, portal_user, "customer_quote_accepted", "quote", quote_id)
    db.commit()
    return {"status": "accepted", "quote_id": quote_id}


@router.get("/customer-portal/invoices")
def customer_invoices(db: Session = Depends(get_db), portal_user: PortalUser = Depends(_customer_user)):
    customer_ids = _customer_ids(db, portal_user)
    rows = db.query(SRMInvoice).filter(SRMInvoice.customer_id.in_(customer_ids)).all() if customer_ids and hasattr(SRMInvoice, "customer_id") else []
    _portal_log(db, portal_user, "customer_invoices_viewed", detail={"count": len(rows)})
    db.commit()
    return _items(rows)


@router.get("/customer-portal/projects")
def customer_projects(db: Session = Depends(get_db), portal_user: PortalUser = Depends(_customer_user)):
    customer_ids = _customer_ids(db, portal_user)
    engagements = db.query(SRMEngagement).filter(SRMEngagement.customer_id.in_(customer_ids)).all() if customer_ids and hasattr(SRMEngagement, "customer_id") else []
    project_ids = [row.pms_project_id for row in engagements if getattr(row, "pms_project_id", None)]
    projects = db.query(PMSProject).filter(PMSProject.id.in_(project_ids)).all() if project_ids else []
    _portal_log(db, portal_user, "customer_projects_viewed", detail={"count": len(projects)})
    db.commit()
    return {"items": [_serialize(item) for item in projects], "total": len(projects), "support_placeholder": "Support cases are not enabled in this deployment."}


@router.get("/partner-portal/leads")
def partner_leads(db: Session = Depends(get_db), portal_user: PortalUser = Depends(_partner_user)):
    partner_ids = _partner_ids(db, portal_user)
    lead_ids = [
        row.resource_id
        for row in db.query(PortalAccessGrant)
        .filter(PortalAccessGrant.portal_user_id == portal_user.id, PortalAccessGrant.resource_type == "partner_lead", PortalAccessGrant.active.is_(True))
        .all()
    ]
    rows = db.query(CRMLead).filter(CRMLead.id.in_(lead_ids)).all() if lead_ids else []
    _portal_log(db, portal_user, "partner_leads_viewed", detail={"count": len(rows)})
    db.commit()
    return _items(rows)


@router.post("/partner-portal/leads", status_code=201)
def submit_partner_lead(data: PartnerLeadPayload, db: Session = Depends(get_db), portal_user: PortalUser = Depends(_partner_user)):
    partner_ids = _partner_ids(db, portal_user)
    if not partner_ids:
        raise HTTPException(status_code=403, detail="Partner link required")
    lead = CRMLead(first_name=data.contact_name, full_name=data.contact_name, company_name=data.company_name, email=data.email, source="Partner Portal", status="New")
    if hasattr(lead, "estimated_value"):
        lead.estimated_value = data.value
    db.add(lead)
    db.flush()
    db.add(PortalAccessGrant(portal_user_id=portal_user.id, resource_type="partner_lead", resource_id=lead.id, permissions_json=["view", "track"]))
    _portal_log(db, portal_user, "partner_lead_submitted", "lead", lead.id, {"value": data.value})
    db.commit()
    db.refresh(lead)
    return _serialize(lead)


@router.get("/partner-portal/dashboard")
def partner_dashboard(db: Session = Depends(get_db), portal_user: PortalUser = Depends(_partner_user)):
    leads = partner_leads(db, portal_user)["items"]
    return {"submitted_leads": len(leads), "open_deals": 0, "commission_status": "placeholder", "message": "Commission tracking placeholder; no fake payouts are generated."}


@router.post("/mobile/check-in", status_code=201)
def mobile_check_in(data: CheckInPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin"))):
    item = MobileSalesVisitCheckIn(**data.model_dump(), created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/mobile/check-in")
def list_mobile_checkins(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin"))):
    return _items(db.query(MobileSalesVisitCheckIn).order_by(MobileSalesVisitCheckIn.created_at.desc()).all())


@router.get("/developer/api-keys")
def list_api_keys(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    return _items(db.query(DeveloperAPIKey).order_by(DeveloperAPIKey.created_at.desc()).all())


@router.post("/developer/api-keys", status_code=201)
def create_api_key(data: APIKeyPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    if not data.scopes:
        raise HTTPException(status_code=422, detail="At least one API key scope is required")
    raw = "bs_" + secrets.token_urlsafe(32)
    item = DeveloperAPIKey(name=data.name, key_prefix=raw[:10], key_hash=_hash(raw), scopes_json=data.scopes, created_by=current_user.id)
    db.add(item)
    db.flush()
    _developer_log(db, current_user, "/api/v1/developer/api-keys", "POST", 201, item)
    db.commit()
    return {**_serialize(item), "api_key": raw, "message": "API key is shown once. Only a hash is stored."}


@router.delete("/developer/api-keys/{key_id}", status_code=204)
def revoke_api_key(key_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    item = db.query(DeveloperAPIKey).filter(DeveloperAPIKey.id == key_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="API key not found")
    item.status = "revoked"
    item.revoked_by = current_user.id
    item.revoked_at = datetime.now(timezone.utc)
    _developer_log(db, current_user, f"/api/v1/developer/api-keys/{key_id}", "DELETE", 204, item)
    db.commit()
    return None


@router.get("/developer/webhooks")
def list_webhooks(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    return _items(db.query(DeveloperWebhook).order_by(DeveloperWebhook.created_at.desc()).all())


@router.post("/developer/webhooks", status_code=201)
def create_webhook(data: WebhookPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    item = DeveloperWebhook(name=data.name, target_url=_ensure_url(data.target_url), events_json=data.events, secret_hash=_hash(data.secret) if data.secret else None, created_by=current_user.id)
    db.add(item)
    db.flush()
    _developer_log(db, current_user, "/api/v1/developer/webhooks", "POST", 201)
    db.commit()
    return _serialize(item)


@router.post("/developer/webhooks/{webhook_id}/test", status_code=201)
def test_webhook(webhook_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    webhook = db.query(DeveloperWebhook).filter(DeveloperWebhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    delivery = DeveloperWebhookDelivery(webhook_id=webhook.id, event_type="developer.test", payload_json={"test": True}, status="queued", attempt_count=0)
    db.add(delivery)
    _developer_log(db, current_user, f"/api/v1/developer/webhooks/{webhook_id}/test", "POST", 201)
    db.commit()
    return _serialize(delivery)


@router.post("/developer/webhooks/{webhook_id}/replay", status_code=201)
def replay_webhook(webhook_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    webhook = db.query(DeveloperWebhook).filter(DeveloperWebhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    delivery = DeveloperWebhookDelivery(webhook_id=webhook.id, event_type="developer.replay", payload_json={"replay": True}, status="queued", attempt_count=0)
    db.add(delivery)
    _developer_log(db, current_user, f"/api/v1/developer/webhooks/{webhook_id}/replay", "POST", 201)
    db.commit()
    return _serialize(delivery)


@router.get("/developer/api-logs")
def api_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("developer_manage", "tenant_admin"))):
    return _items(db.query(DeveloperAPILog).order_by(DeveloperAPILog.created_at.desc()).all())


@router.get("/developer/docs")
def developer_docs(current_user: User = Depends(RequirePermission("developer_view", "developer_manage", "tenant_admin"))):
    return {"title": "Business Suite Developer Hub", "auth": "Bearer token or scoped API key", "rate_limit": "placeholder", "webhook_security": "HTTPS endpoints; optional shared secret hash stored"}


@router.get("/marketplace/apps")
def list_marketplace_apps(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("marketplace_view", "marketplace_manage", "tenant_admin"))):
    return _items(db.query(MarketplaceApp).order_by(MarketplaceApp.created_at.desc()).all())


@router.post("/marketplace/apps", status_code=201)
def create_marketplace_app(data: MarketplaceAppPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("marketplace_manage", "tenant_admin"))):
    item = MarketplaceApp(name=data.name, category=data.category, description=data.description, configuration_schema_json=data.configuration_schema, internal_only=True, created_by=current_user.id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/marketplace/apps/{app_id}/install", status_code=201)
def install_marketplace_app(app_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("marketplace_manage", "tenant_admin"))):
    app = db.query(MarketplaceApp).filter(MarketplaceApp.id == app_id, MarketplaceApp.internal_only.is_(True)).first()
    if not app:
        raise HTTPException(status_code=404, detail="Internal marketplace app not found")
    install = db.query(MarketplaceInstall).filter(MarketplaceInstall.app_id == app.id, MarketplaceInstall.status == "installed").first()
    if not install:
        install = MarketplaceInstall(app_id=app.id, status="installed", installed_by=current_user.id)
        db.add(install)
    db.commit()
    return _serialize(install)


@router.post("/marketplace/apps/{app_id}/uninstall")
def uninstall_marketplace_app(app_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("marketplace_manage", "tenant_admin"))):
    install = db.query(MarketplaceInstall).filter(MarketplaceInstall.app_id == app_id, MarketplaceInstall.status == "installed").first()
    if not install:
        raise HTTPException(status_code=404, detail="Installed app not found")
    install.status = "uninstalled"
    install.uninstalled_at = datetime.now(timezone.utc)
    db.commit()
    return _serialize(install)


@router.get("/marketplace/installed")
def installed_marketplace_apps(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("marketplace_view", "marketplace_manage", "tenant_admin"))):
    return _items(db.query(MarketplaceInstall).order_by(MarketplaceInstall.installed_at.desc()).all())


@router.post("/admin/sandbox/create", status_code=201)
def create_sandbox(data: SandboxPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("sandbox_manage", "tenant_admin"))):
    item = SandboxEnvironment(name=data.name, source_environment="production", status="requested", access_url_placeholder="Sandbox access link is generated by deployment infrastructure.", created_by=current_user.id)
    db.add(item)
    db.flush()
    job = SandboxCopyJob(sandbox_id=item.id, copy_type="metadata_with_limited_sample" if data.copy_sample_data else "metadata", status="queued", detail_json={"production_writes_blocked": True, "sample_data": bool(data.copy_sample_data)})
    db.add(job)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/admin/sandbox")
def list_sandboxes(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("sandbox_view", "sandbox_manage", "tenant_admin"))):
    return _items(db.query(SandboxEnvironment).order_by(SandboxEnvironment.created_at.desc()).all())


@router.post("/admin/sandbox/{sandbox_id}/refresh", status_code=201)
def refresh_sandbox(sandbox_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("sandbox_manage", "tenant_admin"))):
    sandbox = db.query(SandboxEnvironment).filter(SandboxEnvironment.id == sandbox_id).first()
    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    sandbox.status = "refresh_queued"
    sandbox.refreshed_at = datetime.now(timezone.utc)
    job = SandboxCopyJob(sandbox_id=sandbox.id, copy_type="metadata", status="queued", detail_json={"production_writes_blocked": True})
    db.add(job)
    db.commit()
    return _serialize(job)


@router.get("/admin/company-settings")
def get_company_settings(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_view", "tenant_admin"))):
    item = db.query(TenantCompanySetting).first()
    if not item:
        item = TenantCompanySetting()
        db.add(item)
        db.commit()
        db.refresh(item)
    return _serialize(item)


@router.put("/admin/company-settings")
def update_company_settings(data: CompanySettingsPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_admin"))):
    item = db.query(TenantCompanySetting).first() or TenantCompanySetting()
    for key, value in data.model_dump().items():
        mapped = {"tax_defaults": "tax_defaults_json", "business_hours": "business_hours_json", "numbering_settings": "numbering_settings_json"}.get(key, key)
        setattr(item, mapped, value)
    item.updated_by = current_user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/admin/feature-flags")
def list_feature_flags(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_view", "tenant_admin"))):
    return _items(db.query(TenantFeatureFlag).order_by(TenantFeatureFlag.feature_key.asc()).all())


@router.put("/admin/feature-flags")
def upsert_feature_flag(data: FeatureFlagPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_admin"))):
    item = db.query(TenantFeatureFlag).filter(TenantFeatureFlag.feature_key == data.feature_key).first() or TenantFeatureFlag(feature_key=data.feature_key)
    item.enabled = data.enabled
    item.upgrade_message = data.upgrade_message
    item.updated_by = current_user.id
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/admin/subscription-plans")
def list_subscription_plans(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_view", "tenant_admin"))):
    _ensure_default_plans(db)
    db.commit()
    return _items(db.query(TenantSubscriptionPlan).order_by(TenantSubscriptionPlan.id.asc()).all())


@router.post("/admin/subscription-plans", status_code=201)
def create_subscription_plan(data: SubscriptionPlanPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_admin"))):
    if db.query(TenantSubscriptionPlan).filter(TenantSubscriptionPlan.code == data.code).first():
        raise HTTPException(status_code=409, detail="Subscription plan already exists")
    item = TenantSubscriptionPlan(code=data.code, name=data.name, features_json=data.features, active=data.active)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/admin/subscription")
def get_subscription(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_view", "tenant_admin"))):
    _ensure_default_plans(db)
    db.commit()
    return _serialize(db.query(TenantSubscription).order_by(TenantSubscription.id.desc()).first())


@router.put("/admin/subscription")
def update_subscription(data: SubscriptionPayload, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_admin"))):
    _ensure_default_plans(db)
    item = db.query(TenantSubscription).first() or TenantSubscription()
    item.edition = data.edition
    item.plan_id = data.plan_id
    item.status = data.status
    item.admin_override = data.admin_override
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.get("/admin/usage")
def usage_metrics(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("tenant_view", "tenant_admin"))):
    if not db.query(TenantUsageMetric).first():
        db.add_all([
            TenantUsageMetric(metric_key="crm_records", metric_value=db.query(CRMLead).count() + db.query(CRMDeal).count()),
            TenantUsageMetric(metric_key="srm_records", metric_value=db.query(SRMSalesOrder).count() + db.query(SRMInvoice).count()),
            TenantUsageMetric(metric_key="portal_users", metric_value=db.query(PortalUser).count()),
        ])
        db.commit()
    return _items(db.query(TenantUsageMetric).order_by(TenantUsageMetric.metric_key.asc()).all())


@router.get("/admin/feature-gates/{feature_key}")
def check_feature_gate(feature_key: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _feature_allowed(db, feature_key, current_user)
