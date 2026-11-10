"""Signup communications, routing and progress. All metadata stays owner-only."""
from datetime import timedelta
from contextlib import nullcontext
from sqlalchemy import func
from app.core.config import settings
from app.platform_owner import service as s
from app.platform_owner.models import PlatformRecord, PlatformAdmin, PlatformSignupRequest, PlatformTenantDatabase

DEFAULTS = {"auto_assign": False, "routing": {}, "reviewer_email": True,
            "trial_start": "approval", "activation_days": 7, "reminder_hours": 24}


def options(db):
    row = db.query(PlatformRecord).filter_by(kind="signup_journey_settings").first()
    return {**DEFAULTS, **(row.data if row else {})}


def mail(db, signup, subject, body, event, recipient=None):
    key = s.digest("signup-mail:" + event)
    existing = db.query(PlatformRecord).filter_by(token_hash=key).first()
    if existing:
        return existing
    row = PlatformRecord(kind="signup_mail", title=subject, signup_id=signup.id,
        state="pending", token_hash=key, data={"recipient": recipient or signup.email,
        "body": body, "event": event, "delivery": "pending", "permission": "signup.review"})
    db.add(row)
    return row


def assign(db, signup):
    config = options(db)
    if not config["auto_assign"] or signup.assigned_to:
        return
    eligible = [a for a in db.query(PlatformAdmin).filter_by(is_active=True)
                if "signup.review" in s.permissions(a)]
    routing = config["routing"]
    preferred = {routing[m] for m in signup.requested_modules if m in routing}
    pool = [a for a in eligible if a.id in preferred] if preferred else eligible
    if pool:
        counts = dict(db.query(PlatformSignupRequest.assigned_to, func.count()).filter(
            PlatformSignupRequest.status.in_(s.REVIEWABLE)).group_by(PlatformSignupRequest.assigned_to))
        signup.assigned_to = min(pool, key=lambda a: (counts.get(a.id, 0), a.id)).id


def receipt(db, signup):
    from app.access.applicant_login import status_link
    url = status_link(db, signup)
    mail(db, signup, "Your BestERP trial request was received",
         f"Application BS-{signup.id:06d}\nApplications: {', '.join(signup.requested_modules)}\n"
         f"We will review your request before granting business access.\nPrivate status link (24 hours):\n{url}\n"
         "You do not need a password while waiting. After approval use the same Google identity or set a password using the invitation email.",
         f"receipt:{signup.id}")
    if options(db)["reviewer_email"]:
        reviewers = db.query(PlatformAdmin).filter_by(is_active=True)
        if signup.assigned_to:
            reviewers = reviewers.filter_by(id=signup.assigned_to)
        for actor in reviewers:
            if "signup.review" in s.permissions(actor) and actor.preferences.get("email_notifications", True):
                mail(db, signup, "New BestERP application needs review",
                     f"Application BS-{signup.id:06d} is ready for review.\n"
                     + settings.FRONTEND_PUBLIC_URL.rstrip("/") + f"/platform/signups?selected={signup.id}",
                     f"reviewer:{signup.id}:{actor.id}", actor.email)


def deliver(db, business, maximum=50):
    """Bridge durable owner mail into the existing provider-aware outbox.

    Business commit comes first; the stable event key makes a crash/retry safe.
    Never automatically retry provider-uncertain or rejected deliveries.
    """
    from app.services.email_dispatch import queue_email
    from app.models.email_outbox import EmailOutbox
    base=db.query(PlatformRecord).filter_by(kind="signup_mail")
    rows = base.filter(PlatformRecord.state.in_(["pending", "queued", "sending"])).order_by(PlatformRecord.id).limit(maximum).all()
    rows += base.filter(PlatformRecord.state.in_(["accepted","reconciliation_required"])).order_by(PlatformRecord.id.desc()).limit(maximum).all()
    for row in rows:
        key = f"platform-signup-mail:{row.id}"
        out = business.query(EmailOutbox).filter_by(event_key=key).first()
        if not out:
            # A correction invitation is no longer useful after review finishes.
            signup = db.get(PlatformSignupRequest, row.signup_id)
            if not signup or signup.deleted_at:
                row.state = "suppressed"
                continue
            if row.data.get("event", "").startswith("correction:") and signup.status != "awaiting_applicant":
                row.state = "suppressed"
                continue
            out = queue_email(business, recipient=row.data["recipient"], subject=row.title,
                body=row.data["body"], module="public_signup", event_key=key)
            business.commit()
        row.state = out.status if out else "failed"
        row.data = {**row.data, "delivery": row.state, "updated_at": s.now().isoformat(),
                    "provider_message_id": out.provider_message_id if out else None}
    db.commit()
    return len(rows)


def business_for(db, business, signup):
    if not settings.TENANT_DATABASES_ENABLED:
        return nullcontext(business)
    from app.db.tenant import lookup_route, tenant_session
    placement = db.query(PlatformTenantDatabase).filter_by(signup_id=signup.id, status="ready").one()
    return tenant_session(lookup_route(placement.workspace_code))


def access_progress(db, business, signup):
    result = {"review_approved": signup.status == "approved", "workspace_ready": bool(signup.company_id),
              "signin_ready": False, "email_status": "not_queued"}
    if not signup.company_id:
        return result
    from app.apps.saas.models import TenantSubscriptionPlan
    from app.models.email_outbox import EmailOutbox
    with business_for(db, business, signup) as target:
        plan = target.query(TenantSubscriptionPlan).filter_by(code=f"platform-signup-{signup.id}").first()
        from app.models.user import User
        from app.apps.saas.models import TenantSubscription
        user=target.get(User,signup.user_id)
        subscription=target.query(TenantSubscription).filter_by(company_id=signup.company_id).first()
        result["activation_completed"] = bool(plan and (plan.config_json or {}).get("platform_provisioning", {}).get("signin_ready"))
        restricted=bool(not user or not user.is_active or (subscription and subscription.status in {"suspended","cancelled","offboarded"}))
        result["account_restricted"]=restricted and result["activation_completed"]
        result["signin_ready"] = result["activation_completed"] and not restricted
        out = target.query(EmailOutbox).filter_by(event_key=f"signup-approved:{signup.id}").first()
        if out:
            result["email_status"] = out.status
            result["email_updated_at"] = out.updated_at.isoformat() if getattr(out, "updated_at", None) else None
        return result


def due_work(db):
    config = options(db)
    for signup in db.query(PlatformSignupRequest).filter(PlatformSignupRequest.status.in_(s.REVIEWABLE), PlatformSignupRequest.deleted_at.is_(None)):
        assign(db, signup)
        age = s.business_hours_between(signup.created_at, s.now(), s.settings_for(db))
        if age <= s.settings_for(db)["sla_hours"] or not config["reviewer_email"]:
            continue
        period = int(age // config["reminder_hours"])
        recipients = db.query(PlatformAdmin).filter_by(is_active=True)
        for actor in recipients:
            if actor.id != signup.assigned_to and actor.role != "owner":
                continue
            if "signup.review" in s.permissions(actor) and actor.preferences.get("email_notifications", True):
                mail(db, signup, "BestERP application review is overdue",
                    f"Application BS-{signup.id:06d} needs attention. Review target: {s.settings_for(db)['sla_hours']} business hours.\n"
                    + settings.FRONTEND_PUBLIC_URL.rstrip("/") + f"/platform/signups?selected={signup.id}",
                    f"overdue:{signup.id}:{period}:{actor.id}", actor.email)
    db.commit()


def start_trial(db, user):
    """Called only while issuing a fully authenticated business session."""
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    from fastapi import HTTPException
    from app.access.models import AccessMembership
    memberships = db.query(AccessMembership.company_id).filter_by(user_id=user.id, active=True, is_admin=True)
    for subscription in db.query(TenantSubscription).filter(TenantSubscription.company_id.in_(memberships)).with_for_update():
        plan = db.get(TenantSubscriptionPlan, subscription.plan_id)
        receipt = (plan.config_json or {}).get("platform_provisioning", {}) if plan else {}
        if receipt.get("user_id") != user.id or not receipt.get("signin_ready"):
            continue
        config = subscription.config_json or {}
        if config.get("pending_activation") and subscription.status == "trial":
            from datetime import datetime
            deadline = s.aware(datetime.fromisoformat(config["activation_deadline"]))
            if s.now() > deadline:
                raise HTTPException(403, "Your activation deadline has passed. Contact support to extend your trial invitation.")
            end = s.now() + timedelta(days=config["trial_days"])
            subscription.config_json = {**config, "pending_activation": False, "trial_started_at": s.now().isoformat(),
                "renewal_at": end.isoformat(), "grace_until": end.isoformat()}
        if not receipt.get("first_login_at"):
            plan.config_json = {**plan.config_json, "platform_provisioning": {**receipt, "first_login_at": s.now().isoformat()}}


def synchronize_logins(db, business):
    from app.apps.saas.models import TenantSubscriptionPlan, TenantSubscription
    from app.platform_owner.models import PlatformTenant, PlatformEvent
    # A durable round-robin cursor prevents older approved customers from
    # starving when more than one batch of new applications arrives.
    cursor=db.query(PlatformRecord).filter_by(kind="signup_sync_cursor").with_for_update().first()
    if not cursor:
        cursor=PlatformRecord(kind="signup_sync_cursor",title="Signup milestone synchronization",state="active",data={"after":0})
        db.add(cursor);db.flush()
    query=db.query(PlatformSignupRequest).filter_by(status="approved").filter(PlatformSignupRequest.deleted_at.is_(None))
    candidates=query.filter(PlatformSignupRequest.id>cursor.data.get("after",0)).order_by(PlatformSignupRequest.id).limit(25).all()
    if not candidates:candidates=query.order_by(PlatformSignupRequest.id).limit(25).all()
    if candidates:cursor.data={"after":candidates[-1].id,"checked_at":s.now().isoformat()}
    for signup in candidates:
        login_recorded=bool(db.query(PlatformEvent.id).filter_by(action="signup.first_login", entity="signup", entity_id=signup.id).first())
        value_recorded=bool(db.query(PlatformEvent.id).filter_by(action="signup.first_value", entity="signup", entity_id=signup.id).first())
        if login_recorded and value_recorded:
            continue
        try:
            with business_for(db, business, signup) as target:
                plan = target.query(TenantSubscriptionPlan).filter_by(code=f"platform-signup-{signup.id}").first()
                receipt = (plan.config_json or {}).get("platform_provisioning", {}) if plan else {}
                if receipt.get("first_login_at"):
                    if not login_recorded:s.event(db, None, "signup.first_login", "signup", signup.id, after={"at": receipt["first_login_at"]})
                    tenant = db.query(PlatformTenant).filter_by(signup_id=signup.id).first()
                    subscription = target.query(TenantSubscription).filter_by(company_id=signup.company_id).first()
                    if tenant and subscription:
                        tenant.config = {**tenant.config, "activated_at": receipt["first_login_at"],
                            "trial_ends_at": subscription.config_json.get("renewal_at", tenant.config.get("trial_ends_at"))}
                    completed = subscription.config_json.get("onboarding", {}) if subscription else {}
                    if completed.get("first_action") and not value_recorded:
                        s.event(db, None, "signup.first_value", "signup", signup.id, after={"source": "customer_checklist"})
        except Exception:
            # One unavailable dedicated database must not stop other mail/routing.
            continue
    db.commit()
