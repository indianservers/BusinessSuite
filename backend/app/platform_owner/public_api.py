"""Private applicant/staff links, not customer or platform administrator sessions."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.core.security import get_password_hash
from app.platform_owner import service as s
from app.platform_owner.models import PlatformAdmin, PlatformRecord, PlatformSignupRequest, PlatformTenant, PlatformSession
from app.platform_owner.session import get_platform_db

router = APIRouter(prefix="/platform", tags=["Private platform invitation links"])


class PublicAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(max_length=40)
    values: dict = Field(default_factory=dict)


def limit(db, request):
    from app.core.middleware.audit import client_addresses
    from app.core.request_limits import consume
    retry = consume(db, [("platform-private-link:"+str(client_addresses(request)[0]), 30, 900)])
    db.commit()
    if retry: raise HTTPException(429, "Too many attempts; try again later", headers={"Retry-After": str(retry)})


@router.get("/public/{token}")
def preview(token: str, request: Request, db: Session = Depends(get_platform_db)):
    if len(token) > 100: raise HTTPException(404, "Invalid link")
    row = s.public_record(db, token)
    result = {"kind": row.kind, "title": row.title, "expires_at": row.expires_at}
    if row.kind in {"tracking", "correction"}:
        signup = db.get(PlatformSignupRequest, row.signup_id)
        if not signup or signup.deleted_at: raise HTTPException(404, "Request no longer available")
        if row.data.get("recipient") and row.data["recipient"].lower()!=signup.email.lower():
            raise HTTPException(404,"This link is no longer valid. Request a fresh link using your current application email.")
        result["status"] = signup.status
        result["applicant"] = signup.company_name or signup.name
        result.update({"reference":f"BS-{signup.id:06d}","email":signup.email,"modules":signup.requested_modules,
            "submitted_at":signup.created_at,"last_checked_at":s.now(),"support_url":"/help",
            "review_target_hours":s.settings_for(db)["sla_hours"],
            "elapsed_business_hours":round(s.business_hours_between(signup.created_at,s.now(),s.settings_for(db)),1)})
        from app.platform_owner.models import PlatformEvent
        safe_actions={"signup.received":"Submitted","signup.under_review":"Under review","signup.information_requested":"Action needed",
            "signup.corrected_by_applicant":"Corrections received","signup.approved":"Approved","signup.rejected":"Decision made","signup.withdrawn_by_applicant":"Withdrawn"}
        result["timeline"]=[{"label":safe_actions[e.action],"at":e.created_at} for e in db.query(PlatformEvent).filter_by(entity="signup",entity_id=signup.id).order_by(PlatformEvent.id) if e.action in safe_actions]
        if row.kind == "tracking":
            result["message"] = "Waiting for approval. You can access your workspace once your application is approved." if signup.status in s.REVIEWABLE else "Your application has been " + signup.status.replace("_", " ") + "."
            if signup.status == "approved":
                from app.core.config import settings
                from app.platform_owner.models import PlatformTenantDatabase
                placement = db.query(PlatformTenantDatabase).filter_by(signup_id=signup.id, status="ready").first()
                result["login_url"] = settings.FRONTEND_PUBLIC_URL.rstrip("/") + "/login" + ("?tenant=" + placement.workspace_code if placement else "")
                result["message"]="Your application is approved. Continue with Google using your application email, or request a fresh email password setup link below."
            elif signup.status=="awaiting_applicant":
                correction=db.query(PlatformRecord).filter_by(signup_id=signup.id,kind="correction",state="pending").order_by(PlatformRecord.id.desc()).first()
                result["message"]="We need a few details before completing your review. Open the correction link in your latest email."
            elif signup.status=="rejected":
                result["message"]=signup.workflow.get("applicant_message") or "We cannot approve this request at this time. Contact Help & support to discuss your options."
            elif signup.status=="withdrawn":
                result["message"]="You withdrew this application. Contact support if you want to apply again."
        if row.kind == "correction":
            result["fields"] = {k: getattr(signup,k) for k in row.data.get("fields",["name", "company_name", "email", "phone", "notes"]) if k!="company_name" or signup.applicant_type=="company"}
            result["instructions"]=row.data.get("instructions",{})
            result["message"] = row.data.get("message", "")
    elif row.kind in {"staff_invitation", "password_reset"}:
        result["email"] = row.data["recipient"]
    elif row.kind in {"transfer_consent", "support_consent"}:
        tenant = db.get(PlatformTenant, row.tenant_id)
        result["customer"] = tenant.name if tenant else ""
        result["message"] = row.data.get("reason", "Confirm the requested company administrator change")
    else: raise HTTPException(404, "Unknown private link")
    return result


@router.post("/public/{token}")
def submit(token: str, data: PublicAction, request: Request, db: Session = Depends(get_platform_db), business: Session = Depends(get_db)):
    limit(db, request)
    row = s.public_record(db, token)
    if row.kind == "tracking":
        signup = db.query(PlatformSignupRequest).filter_by(id=row.signup_id).with_for_update().first()
        if not signup or signup.deleted_at or row.data.get("recipient",signup.email).lower()!=signup.email.lower():
            raise HTTPException(404,"This application link is no longer valid")
        from app.platform_owner.signup_journey import mail
        if data.action=="password_link" and signup.status=="approved":
            from app.core.request_limits import consume
            retry=consume(db,[(f"signup-password-link:{signup.id}",3,3600)])
            db.commit()
            if retry:raise HTTPException(429,"Please wait before requesting another link",headers={"Retry-After":str(retry)})
            from app.platform_owner.signup_journey import business_for
            from app.api.v1.auth import _hash_reset_token
            from app.models.user import User
            from app.core.config import settings
            import secrets
            with business_for(db,business,signup) as target:
                user=target.get(User,signup.user_id)
                if not user or user.email.lower()!=signup.email.lower():raise HTTPException(409,"Contact support to reconcile this account")
                raw=secrets.token_urlsafe(40)
                user.password_reset_token,user.password_reset_expires=_hash_reset_token(raw),s.now()+timedelta(hours=48)
                target.commit()
            from app.platform_owner.models import PlatformTenantDatabase
            placement=db.query(PlatformTenantDatabase).filter_by(signup_id=signup.id,status="ready").first()
            url=settings.FRONTEND_PUBLIC_URL.rstrip("/")+"/invite-access?token="+raw+("&tenant="+placement.workspace_code if placement else "")
            mail(db,signup,"Set your BestERP password",f"Set your password once using this private link (48 hours):\n{url}",f"password-link:{signup.id}:{s.digest(raw)}")
        elif data.action=="withdraw":
            if signup.status not in s.REVIEWABLE: raise HTTPException(409, "Review is already complete")
            signup.status, signup.version = "withdrawn", signup.version+1
            s.event(db, None, "signup.withdrawn_by_applicant", "signup", signup.id)
            mail(db,signup,"Your BestERP application was withdrawn","Your withdrawal has been recorded. No business access has been granted. Contact support if you want to apply again.",f"withdrawn:{signup.id}:{signup.version}")
        else:raise HTTPException(422,"This action is not available for the current application status")
    elif row.kind == "correction":
        signup = db.query(PlatformSignupRequest).filter_by(id=row.signup_id).with_for_update().first()
        if not signup or signup.status != "awaiting_applicant": raise HTTPException(409, "Corrections are no longer requested")
        values = data.values
        if set(values)-set(row.data.get("fields",["name", "company_name", "email", "phone", "notes"])): raise HTTPException(422, "Only the requested correction fields can be changed")
        before = s.encode(signup)
        from app.access.signup import SignupInput
        try:
            checked = SignupInput(applicant_type=signup.applicant_type, name=values.get("name",signup.name),
                company_name=values.get("company_name",signup.company_name), email=values.get("email",signup.email),
                phone=values.get("phone",signup.phone), phone_country_code=signup.phone_country_code,
                notes=values.get("notes",signup.notes or ""), requested_modules=signup.requested_modules, consent=True)
        except ValidationError:
            raise HTTPException(422,"Please check the applicant name, company, email and phone fields") from None
        if db.query(PlatformSignupRequest.id).filter(PlatformSignupRequest.email == checked.email, PlatformSignupRequest.id != signup.id).first():
            raise HTTPException(409, "That email is already used by another request")
        if "email" in values and checked.email!=signup.email:
            signup.workflow={**signup.workflow,"email_verified":False}
        for key in values: setattr(signup,key,getattr(checked,key))
        signup.status, signup.version, row.state = "under_review", signup.version+1, "completed"
        row.token_hash=None
        s.event(db, None, "signup.corrected_by_applicant", "signup", signup.id, before=before, after=s.encode(signup))
    elif row.kind in {"staff_invitation", "password_reset"}:
        password = str(data.values.get("password", ""))
        if not 12 <= len(password) or len(password.encode()) > 72: raise HTTPException(422, "Use a password with at least 12 characters and no more than 72 UTF-8 bytes")
        email = row.data["recipient"].lower()
        admin = db.query(PlatformAdmin).filter_by(email=email).with_for_update().first()
        if row.kind == "staff_invitation":
            if admin: raise HTTPException(409, "This staff account already exists")
            admin = PlatformAdmin(email=email, name=row.data["name"], role=row.data["role"], permissions=row.data.get("permissions", []),
                assigned_only=row.data.get("assigned_only",False), hashed_password=get_password_hash(password))
            db.add(admin); db.flush()
            s.event(db, admin, "staff.invitation_accepted", "staff", admin.id)
        else:
            if not admin or not admin.is_active: raise HTTPException(404, "This account is unavailable")
            admin.hashed_password, admin.token_version = get_password_hash(password), admin.token_version+1
            db.query(PlatformSession).filter_by(admin_id=admin.id).update({"status":"revoked"})
            s.event(db, admin, "staff.password_reset", "staff", admin.id)
        row.state, row.token_hash = "completed", None
    elif row.kind == "support_consent":
        if data.action not in {"approve", "decline"}: raise HTTPException(422, "Approve or decline this request")
        row.state = "approved" if data.action == "approve" else "declined"
        if row.state == "approved":
            row.expires_at = s.now()+timedelta(hours=row.data["hours"])
            db.add(PlatformRecord(kind="support", title=row.data["reason"][:180], owner_id=row.owner_id, tenant_id=row.tenant_id,
                state="authorized", expires_at=row.expires_at, data={"consent_id": row.id, "body": row.data["reason"],
                "scope": "Platform customer configuration and aggregate diagnostics only. No business record or impersonation access."}))
        s.event(db, None, "support.customer_"+row.state, "tenant", row.tenant_id)
    elif row.kind == "transfer_consent":
        if data.action != "approve": raise HTTPException(422, "Confirm to continue the transfer")
        parent = db.query(PlatformRecord).filter_by(id=row.data["parent_id"], kind="admin_transfer").with_for_update().first()
        if not parent or parent.state != "pending": raise HTTPException(409, "Transfer no longer pending")
        parent.data = {**parent.data, row.data["party"]+"_confirmed": True}
        row.state = "completed"
        if parent.data["old_confirmed"] and parent.data["new_confirmed"]:
            tenant = db.query(PlatformTenant).filter_by(id=parent.tenant_id).with_for_update().one()
            from app.platform_owner.bridge import transfer_admin
            url = transfer_admin(business, tenant, parent.data["old_email"], parent.data["new_email"])
            tenant.admin_email, parent.state = parent.data["new_email"], "completed"
            s.local_mail(db, tenant.admin_email, "Activate your transferred company admin account", url, tenant_id=tenant.id)
            s.event(db, None, "tenant.admin_transferred", "tenant", tenant.id, after={"new_email":tenant.admin_email})
    else: raise HTTPException(422, "Unsupported private link operation")
    db.commit()
    return {"message": "Your response has been saved.", "kind": row.kind}


class ResetInput(BaseModel):
    email: EmailStr


@router.post("/password-reset")
def password_reset(data: ResetInput, request: Request, db: Session = Depends(get_platform_db)):
    limit(db, request)
    admin = db.query(PlatformAdmin).filter_by(email=str(data.email).lower(), is_active=True).first()
    if admin:
        s.issue_link(db,"password_reset","Reset your Indian Servers platform password",admin.email, hours=1)
        db.commit()
    return {"message": "If this platform account exists, a reset link has been prepared in the local outbox."}
