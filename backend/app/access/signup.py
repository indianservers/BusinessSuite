"""Public trial requests; only platform administrators can provision a tenant."""
from datetime import datetime, timedelta, timezone
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.deps import get_db
from app.core.security import get_password_hash
from app.models.user import User
from app.models.company import Company, Branch
from app.common.models import CommonPerson
from app.access.models import AccessMembership, AccessPolicy
from app.platform_owner.models import PlatformSignupRequest as SignupRequest, PlatformAudit
from app.platform_owner.session import get_platform_db
from app.platform_owner.auth import current_platform_admin, PlatformLogin, login as platform_login
from app.access.service import validate_grants
from app.access.catalog import catalog, ACTIONS
from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
from app.services.email_dispatch import queue_email
from app.platform_owner import service as owner_service
from app.platform_owner.models import PlatformTenant, PlatformRecord

router = APIRouter(prefix="/auth", tags=["Public signup and trials"])
TRIAL_MODULES = {"hrms": "HRMS", "crm": "CRM", "project_management": "Projects", "srm": "Sales & Inventory", "fam": "Finance & Accounting"}


def available_modules():
    from app.module_registry import get_installed_app_keys
    installed = set(get_installed_app_keys())
    return [{"key": key, "label": label} for key, label in TRIAL_MODULES.items() if key in installed]


class SignupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    applicant_type: Literal["company", "individual"]
    name: str = Field(min_length=2, max_length=150)
    company_name: str | None = Field(default=None, max_length=150)
    email: EmailStr = Field(max_length=100)
    phone: str = Field(min_length=5, max_length=20, pattern=r"^[+0-9() .-]+$")
    phone_country_code: str = Field(default="+91", max_length=5)
    requested_modules: list[str] = Field(min_length=1, max_length=5)
    notes: str = Field(default="", max_length=2000)
    consent: Literal[True]
    website: str = Field(default="", max_length=200)  # Honeypot; never provisions access.
    source: str = Field(default="website", max_length=80)
    campaign: str = Field(default="", max_length=120)
    sample_data_requested: bool = False
    marketing_consent: bool = False
    identity_proof: str = Field(default="", max_length=2000)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()

    @model_validator(mode="after")
    def validate_selection(self):
        if self.applicant_type == "company" and not self.company_name:
            raise ValueError("Company name is required")
        if self.sample_data_requested and self.applicant_type != "company":
            raise ValueError("Sample data is available for company signups only")
        from app.core.input_validation import normalize_phone
        self.phone = normalize_phone(self.phone, self.phone_country_code)[0]
        allowed = {m["key"] for m in available_modules()}
        if not set(self.requested_modules) <= allowed:
            raise ValueError("Choose installed trial modules")
        self.requested_modules = sorted(set(self.requested_modules))
        return self


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)
    trial_days: int = Field(default=14, ge=1, le=90)
    modules: list[str] = Field(default_factory=list, max_length=5)
    seats: int = Field(default=5, ge=1, le=10000)
    storage_mib: int = Field(default=1024, ge=100, le=1048576)
    version: int | None = Field(default=None, ge=1)
    checklist: dict[str, bool] | None = None
    applicant_message: str = Field(default="", max_length=1000)
    trial_start: Literal["approval", "first_login"] = "approval"
    activation_days: int = Field(default=7, ge=1, le=30)


def serialize(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


@router.get("/signup/options")
def signup_options():
    return {"modules": available_modules(), "approval_required": True,
            "trial_start": "Confirmed by the reviewer; shown in your approval email", "policy_version": "2026-11-10"}


class ApplicantEmailInput(BaseModel):
    email: EmailStr = Field(max_length=150)


@router.post("/signup/status-link", status_code=202)
def applicant_email_link(data: ApplicantEmailInput, request: Request,
                         db: Session = Depends(get_platform_db), business: Session = Depends(get_db)):
    from app.core.request_limits import consume
    from app.core.middleware.audit import client_addresses
    from app.access.applicant_login import status_link
    email = str(data.email).lower()
    retry = consume(db, [("applicant-status-ip:" + str(client_addresses(request)[0]), 10, 3600),
                         ("applicant-status-email:" + owner_service.digest(email), 3, 3600)])
    db.commit()
    if retry:
        raise HTTPException(429, "Too many requests. Please try again later.", headers={"Retry-After": str(retry)})
    signup = db.query(SignupRequest).filter(func.lower(SignupRequest.email) == email, SignupRequest.deleted_at.is_(None)).first()
    if signup:
        url = status_link(db, signup)
        db.commit()
        queue_email(business, recipient=email, subject="Your BestERP application status",
            body=f"View your signup application using this private link (valid for 24 hours):\n{url}\n\nWhile your request is being reviewed, you will see Waiting for approval. Business access is granted only after approval.",
            module="public_signup", event_key="applicant-status:" + secrets.token_hex(16))
        business.commit()
    return {"message": "If an application exists for this email, a private status link has been sent."}


@router.post("/signup", status_code=202)
def signup(data: SignupInput, request: Request, db: Session = Depends(get_platform_db)):
    from app.core.request_limits import consume
    from app.core.middleware.audit import client_addresses
    retry = consume(db, [("public-signup:" + str(client_addresses(request)[0]), 10, 3600)])
    db.commit()  # Persist throttles even for duplicate or rejected submissions.
    if retry:
        raise HTTPException(429, "Too many signup attempts. Please try again later.", headers={"Retry-After": str(retry)})
    response = {"message": "Thank you. If eligible, your request will be reviewed and an activation invitation sent after approval. No access is granted before approval."}
    if data.website:
        return response
    if db.query(SignupRequest.id).filter_by(email=data.email).first():
        return response
    verified = False
    if data.identity_proof:
        import jwt
        try:
            proof = jwt.decode(data.identity_proof, settings.PLATFORM_SECRET_KEY, algorithms=["HS256"], issuer="besterp-signup", options={"require":["exp","email","purpose"]})
            if proof["purpose"] != "signup-prefill" or proof["email"].lower() != data.email:
                raise ValueError()
            verified = True
        except (ValueError, jwt.PyJWTError):
            raise HTTPException(422, "Google verification expired or the email changed. Verify again or continue with email.") from None
    signup_row = SignupRequest(**data.model_dump(exclude={"consent", "website", "sample_data_requested", "marketing_consent", "identity_proof"}))
    signup_row.workflow = {"sample_data_requested": data.sample_data_requested, "marketing_consent": data.marketing_consent,
                           "email_verified": verified, "policy_version":"2026-11-10"}
    db.add(signup_row)
    db.flush()
    from app.platform_owner import signup_journey as journey
    journey.assign(db, signup_row)
    journey.receipt(db, signup_row)
    owner_service.event(db, None, "signup.received", "signup", signup_row.id,
                        after={"type": data.applicant_type, "source": data.source})
    if owner_service.settings_for(db)["notify_new_signup"]:
        owner_service.notify(db, "New trial request", data.company_name or data.name, signup_id=signup_row.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # Concurrent duplicate requests receive the same public response.
    return response


@router.get("/signup-requests")
def signup_requests(status: Literal["pending", "approved", "rejected", "all"] = "pending", search: str = Query("", max_length=180), page: int = Query(1, ge=1), actor = Depends(current_platform_admin), db: Session = Depends(get_platform_db)):
    owner_service.require(actor, "signup.read")
    query = owner_service.scoped(db.query(SignupRequest).filter(SignupRequest.deleted_at.is_(None)), actor, SignupRequest)
    if status != "all":
        query = query.filter(SignupRequest.status == status)
    if search:
        query = query.filter(or_(*[column.ilike(f"%{search}%") for column in (SignupRequest.name, SignupRequest.company_name, SignupRequest.email)]))
    total = query.count()
    rows = query.order_by(SignupRequest.id.desc()).offset((page-1)*40).limit(40).all()
    return {"items": [serialize(row) for row in rows], "total": total, "page": page, "modules": available_modules()}


@router.post("/platform/login")
def owner_login(data: PlatformLogin, request: Request, db: Session = Depends(get_platform_db)):
    return platform_login(data, request, db)


@router.get("/platform/me")
def owner_me(actor=Depends(current_platform_admin)):
    return {"email": actor.email, "name": actor.name, "role": actor.role}


@router.post("/signup-requests/{ident}/review")
def review_signup(ident: int, data: ReviewInput, request: Request,
                  actor=Depends(current_platform_admin),
                  db: Session = Depends(get_platform_db), business: Session = Depends(get_db)):
    row = owner_service.signup_for(db, actor, ident, "signup.review", lock=True)
    if data.version is not None and data.version != row.version:
        raise HTTPException(409, "Application changed since you opened it. Reload and review the latest details.")
    if row.status == "approved" and data.decision == "approve":
        from app.access.signup_activation import enable_approved_signup
        if enable_approved_signup(row, db, business):
            return {"request": serialize(row), "delivery": "queued"}
    if row.status not in owner_service.REVIEWABLE:
        raise HTTPException(409, "This signup request has already been reviewed")
    if data.checklist is not None:
        if set(data.checklist) - {"identity", "duplicates", "modules"}:
            raise HTTPException(422, "Unsupported review checklist item")
        row.workflow = {**row.workflow, "checklist": data.checklist}
    if data.decision == "approve" and any(d.get("decision") in {"match", "existing_customer"} for d in row.workflow.get("duplicates", {}).values()):
        raise HTTPException(409, "Resolve this matched application through the existing customer or request; do not create a duplicate workspace.")
    if data.decision == "approve" and owner_service.settings_for(db)["require_checklist"]:
        checks = row.workflow.get("checklist", {})
        if not all(checks.get(key) for key in ["identity", "duplicates", "modules"]):
            raise HTTPException(422, "Complete the identity, duplicate and application review checklist")
    # The owner row stays locked across provisioning. A durable receipt in the
    # business transaction lets retries recover if the second DB commit fails.
    result = {}
    if data.decision == "approve":
        try:
            if settings.TENANT_DATABASES_ENABLED:
                from app.platform_owner.tenant_provisioning import provision_company
                result = provision_company(row,data)
            else:
                result = provision_signup(row, data, business)
        except IntegrityError:
            business.rollback()
            raise HTTPException(409, "Account provisioning changed concurrently. Refresh and review again.") from None
        row.company_id, row.user_id = result["company_id"], result["user_id"]
        row.trial_ends_at = datetime.fromisoformat(result["trial_ends_at"])
        tenant = db.query(PlatformTenant).filter_by(signup_id=row.id).first()
        if not tenant:
            db.add(PlatformTenant(signup_id=row.id, company_id=row.company_id, name=row.company_name or row.name,
                admin_email=row.email, assigned_to=row.assigned_to, config={"modules": data.modules, "seats": data.seats,
                "storage_mib": data.storage_mib, "trial_ends_at": result["trial_ends_at"], "monthly_price_minor": 0,
                "currency": "INR", "activated_at": None, "trial_start":data.trial_start, "trial_days":data.trial_days}))
        db.add(PlatformRecord(kind="provisioning", title=f"Workspace for {row.company_name or row.name}", state="completed",
            owner_id=actor.id, signup_id=row.id, data={"steps": (["Dedicated PostgreSQL database ready", "Database isolation verified"] if result.get("tenant_uuid") else [])+["Workspace created", "Company admin created", "Applications enabled", "Invitation ready"],
            "company_id": row.company_id}))
        if result.get("invitation_url"):
            owner_service.local_mail(db, row.email, "Your Business Suite trial is approved", result["invitation_url"], actor, signup_id=row.id)
            db.add(PlatformRecord(kind="customer_invitation", title="Company admin activation", owner_id=actor.id, signup_id=row.id,
                state="ready_local", expires_at=owner_service.now()+timedelta(hours=48), data={"recipient": row.email, "user_id": row.user_id}))
        for previous_job in db.query(PlatformRecord).filter_by(kind="provisioning", signup_id=row.id, state="failed"):
            previous_job.state = "recovered"
    else:
        receipt = business.query(TenantSubscriptionPlan).filter_by(code=f"platform-signup-{row.id}").first()
        if receipt:
            raise HTTPException(409, "Workspace already provisioned. Retry approval to reconcile this request.")
    row.status = "approved" if data.decision == "approve" else "rejected"
    row.version += 1
    row.reviewed_at, row.reviewed_by, row.review_reason = datetime.now(timezone.utc), actor.id, data.reason
    row.workflow = {**row.workflow, "applicant_message":data.applicant_message,
                    "trial_start":data.trial_start, "trial_days":data.trial_days,
                    "reviewer_name":actor.name}
    if data.decision == "reject":
        from app.platform_owner.signup_journey import mail
        mail(db,row,"Your BestERP trial application decision",data.applicant_message or "Thank you for applying. We cannot approve this request at this time. Contact Help & support if you need assistance.",f"rejected:{row.id}:{row.version}")
    db.add(PlatformAudit(signup_id=row.id, admin_id=actor.id, decision=data.decision, reason=data.reason))
    owner_service.event(db, actor, "signup."+row.status, "signup", row.id, data.reason,
                        after={"status": row.status, "company_id": row.company_id})
    db.commit()
    if data.decision == "approve":
        from app.access.signup_activation import enable_approved_signup
        try:
            enable_approved_signup(row, db, business)
        except Exception:
            business.rollback()
            db.add(PlatformRecord(kind="provisioning",title="Sign-in activation needs recovery",signup_id=row.id,
                state="failed",owner_id=actor.id,data={"phase":"activation","retryable":True,"error":"Approval saved; sign-in activation was interrupted. Use Retry incomplete steps."}))
            db.commit()
            raise HTTPException(503,"Approval was saved. Open access progress and retry incomplete steps.") from None
    return {"request": serialize(row), **{k: v for k, v in result.items() if k in {"invitation_url", "delivery"}}}


def provision_signup(row, data, db, company_id=None):
    code = f"platform-signup-{row.id}"
    receipt = db.query(TenantSubscriptionPlan).filter_by(code=code).first()
    if receipt:
        result = (receipt.config_json or {}).get("platform_provisioning")
        if not result or result.get("email") != row.email:
            raise HTTPException(409, "Provisioning receipt mismatch")
        return {**result, "delivery": "queued"}
    now = datetime.now(timezone.utc)
    allowed = {m["key"] for m in available_modules()}
    selected = sorted(set(data.modules))
    if not selected or not set(selected) <= allowed:
        raise HTTPException(422, "Select at least one installed trial module")
    if db.query(User.id).filter(func.lower(User.email) == row.email).first() or db.query(CommonPerson.id).filter(func.lower(CommonPerson.primary_email) == row.email).first():
        raise HTTPException(409, "This email already belongs to an account. Manage its access through User Access instead.")
    company = Company(name=row.company_name if row.applicant_type == "company" else row.name, email=row.email, phone=row.phone, phone_country_code=row.phone_country_code, is_active=True, country="India", default_currency="INR", default_timezone="Asia/Kolkata", fiscal_year_start_month=4)
    if company_id is not None:company.id=company_id
    db.add(company)
    db.flush()
    branch = Branch(name="Main", code="MAIN", company_id=company.id, organization_id=company.id, is_active=True, email=row.email, created_by=None)
    db.add(branch)
    db.flush()
    from app.branches.models import BranchOwnership
    db.add(BranchOwnership(company_id=company.id, branch_id=branch.id, resource_table="branches", resource_key=str(branch.id), source="approved-public-signup"))
    user = User(email=row.email, hashed_password=get_password_hash(secrets.token_urlsafe(40)), is_active=False, is_superuser=False, person=CommonPerson(organization_id=company.id, primary_email=row.email, display_name=row.name, phone_number=row.phone, phone_number_country_code=row.phone_country_code, status="active"))
    db.add(user)
    db.flush()
    from app.branches.models import BranchPolicy
    db.add(BranchPolicy(user_id=user.id, company_id=company.id, all_branches=True, manage_access=True))
    db.add(AccessMembership(user_id=user.id, company_id=company.id, is_admin=True, active=True))
    from app.shared.starter_values import populate as populate_starter_values
    populate_starter_values(db, company.id, branch.id, set(selected))
    grants = {m["key"]: {"enabled": True, "role": "Workspace Admin", "permissions": [p["name"] for p in m["permissions"]], "actions": list(ACTIONS), "scope": "organization"} for m in catalog(db) if m["key"] in selected}
    if set(grants) != set(selected):
        raise HTTPException(422, "Trial module configuration is unavailable")
    db.add(AccessPolicy(user_id=user.id, company_id=company.id, grants=validate_grants(db, grants, company.id), status="invited", version=1, updated_by=None))
    from zoneinfo import ZoneInfo
    first_login = data.trial_start == "first_login"
    ends = now + timedelta(days=data.activation_days if first_login else data.trial_days)
    ends_label = ends.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")
    plan = TenantSubscriptionPlan(code=code, name="Public Trial", active=True, config_json={"modules": selected, "seats": data.seats, "storage_mib": data.storage_mib,
        "company_signup": row.applicant_type == "company", **({"sample_data_requested": True} if (row.workflow or {}).get("sample_data_requested") else {})})
    db.add(plan)
    db.flush()
    db.add(TenantSubscription(company_id=company.id, plan_id=plan.id, status="trial", admin_override=False, config_json={"enforce": True, "modules": selected, "seats": data.seats, "storage_mib": data.storage_mib, "expiry_policy": "restrict", "renewal_at": ends.isoformat(), "grace_until": ends.isoformat(),
        "trial_start":data.trial_start,"trial_days":data.trial_days,"pending_activation":first_login,"activation_deadline":ends.isoformat() if first_login else None}))
    from app.api.v1.auth import _hash_reset_token
    raw = secrets.token_urlsafe(40)
    user.password_reset_token = _hash_reset_token(raw)
    user.password_reset_expires = now + timedelta(hours=48)
    link = settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/invite-access?token=" + raw
    invitation_mail = queue_email(db, recipient=row.email, subject="Your Business Suite trial is approved", body=f"Your trial workspace is approved. Sign in with Google using the same email address you applied with: {row.email}. No Business Suite password is needed for Google sign-in.\n\nTo sign in with email and password, set your password once using this private link (valid for 48 hours):\n{link}\n\n{f"Your {data.trial_days}-day trial starts at first sign-in. Activate by {ends_label}." if first_login else f"Your trial ends {ends_label}."} You administer only your own workspace. Sign in at {settings.FRONTEND_PUBLIC_URL.rstrip('/')}/login", module="public_signup", organization_id=company.id, event_key=f"signup-approved:{row.id}")
    if invitation_mail is not None:
        if data.applicant_message:
            invitation_mail.body += "\n\nMessage from your reviewer:\n" + data.applicant_message
        invitation_mail.status = "held_local"
    result = {"company_id": company.id, "user_id": user.id, "email": row.email,
              "trial_ends_at": ends.isoformat(), "delivery": "queued"}
    # Receipt contains no activation token. A recovery retry can rely on queued mail.
    plan.config_json = {**plan.config_json, "platform_provisioning": result}
    db.commit()
    return {**result, "invitation_url": link}


from app.access.signup_journey_api import router as journey_public_router
router.include_router(journey_public_router)
