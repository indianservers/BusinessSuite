"""Owner controls for routing, delivery, duplicate adjudication and recovery."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.platform_owner.auth import current_platform_admin
from app.platform_owner.session import get_platform_db
from app.platform_owner.models import PlatformRecord, PlatformAdmin, PlatformEvent, PlatformSignupRequest
from app.platform_owner import service as s
from app.platform_owner import signup_journey as j

router = APIRouter(prefix="/signup-journey")


@router.get("/defaults")
def review_defaults(actor=Depends(current_platform_admin),db:Session=Depends(get_platform_db)):
    s.require(actor,"signup.read")
    config=j.options(db)
    return {"trial_start":config["trial_start"],"activation_days":config["activation_days"]}


class ConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    auto_assign: bool = False
    routing: dict[str, int] = Field(default_factory=dict, max_length=5)
    reviewer_email: bool = True
    trial_start: str = Field(default="approval", pattern="^(approval|first_login)$")
    activation_days: int = Field(default=7, ge=1, le=30)
    reminder_hours: int = Field(default=24, ge=4, le=168)


@router.get("/settings")
def read_settings(actor=Depends(current_platform_admin), db: Session=Depends(get_platform_db)):
    s.require(actor, "settings.manage")
    return j.options(db)


@router.put("/settings")
def save_settings(data: ConfigInput, actor=Depends(current_platform_admin), db: Session=Depends(get_platform_db)):
    s.require(actor, "settings.manage")
    from app.access.signup import available_modules
    if set(data.routing) - {m["key"] for m in available_modules()}:
        raise HTTPException(422, "Choose installed applications for routing")
    for ident in data.routing.values():
        reviewer = db.get(PlatformAdmin, ident)
        if not reviewer or not reviewer.is_active or "signup.review" not in s.permissions(reviewer):
            raise HTTPException(422, "Routing requires an active reviewer")
    row = db.query(PlatformRecord).filter_by(kind="signup_journey_settings").first()
    if not row:
        row = PlatformRecord(kind="signup_journey_settings", title="Signup routing and trial rules", state="active")
        db.add(row)
    old = row.data
    row.data = data.model_dump()
    s.event(db, actor, "signup.settings_changed", before=old, after=row.data)
    db.commit()
    return row.data


@router.get("/{ident}/progress")
def progress(ident:int, actor=Depends(current_platform_admin), db:Session=Depends(get_platform_db), business:Session=Depends(get_db)):
    row = s.signup_for(db, actor, ident)
    result = j.access_progress(db, business, row)
    messages = db.query(PlatformRecord).filter_by(signup_id=ident, kind="signup_mail").order_by(PlatformRecord.id.desc()).limit(20)
    return {**result, "messages": [{"id":m.id,"subject":m.title,"recipient":m.data["recipient"],"status":m.state,"updated_at":m.data.get("updated_at"),"created_at":m.created_at} for m in messages]}


class Action(BaseModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/{ident}/recover")
def recover(ident:int, data:Action, actor=Depends(current_platform_admin), db:Session=Depends(get_platform_db), business:Session=Depends(get_db)):
    row = s.signup_for(db, actor, ident, "signup.review", lock=True)
    if row.version != data.version:
        raise HTTPException(409, "Application changed. Reload before recovery.")
    from app.access.signup_activation import enable_approved_signup
    changed = enable_approved_signup(row, db, business)
    s.event(db,actor,"signup.activation_retried","signup",ident,data.reason,after={"changed":changed})
    db.commit()
    return j.access_progress(db,business,row)


@router.post("/{ident}/resend")
def resend(ident:int, data:Action, actor=Depends(current_platform_admin), db:Session=Depends(get_platform_db), business:Session=Depends(get_db)):
    row = s.signup_for(db,actor,ident,"signup.review",lock=True)
    if row.version != data.version:
        raise HTTPException(409,"Application changed. Reload before sending.")
    from app.access.applicant_login import status_link
    from app.core.request_limits import consume
    retry = consume(db,[(f"signup-resend:{ident}",3,3600)])
    db.commit()
    if retry:
        raise HTTPException(429,"Please wait before resending.",headers={"Retry-After":str(retry)})
    url = status_link(db,row)
    j.mail(db,row,"Your BestERP application: sign-in and next steps",f"View your application and request a fresh password setup link if approved:\n{url}",f"resend:{ident}:{__import__('secrets').token_hex(12)}")
    s.event(db,actor,"signup.message_resent","signup",ident,data.reason)
    db.commit()
    return {"message":"A fresh private application link is queued for email delivery."}


class Duplicate(Action):
    other_id:int = Field(ge=1)
    decision:str = Field(pattern="^(match|not_a_match|existing_customer)$")


@router.post("/{ident}/duplicate")
def duplicate(ident:int,data:Duplicate,actor=Depends(current_platform_admin),db:Session=Depends(get_platform_db)):
    row=s.signup_for(db,actor,ident,"signup.edit",lock=True)
    s.signup_for(db,actor,data.other_id)
    if row.version!=data.version or row.status not in s.REVIEWABLE or ident==data.other_id:
        raise HTTPException(409,"Reload an editable application before resolving duplicates")
    decisions={**(row.workflow or {}).get("duplicates",{}),str(data.other_id):{"decision":data.decision,"reason":data.reason,"reviewer":actor.id}}
    row.workflow={**row.workflow,"duplicates":decisions};row.version+=1
    s.event(db,actor,"signup.duplicate_resolved","signup",ident,data.reason,after={"other_id":data.other_id,"decision":data.decision})
    db.commit();return {"version":row.version,"decisions":decisions}


@router.get("/analytics/funnel")
def analytics(actor=Depends(current_platform_admin),db:Session=Depends(get_platform_db)):
    s.require(actor,"reports.read")
    cutoff=s.now()-timedelta(days=30)
    # Scope every customer count to the actor's visible signup IDs.
    visible=s.scoped(db.query(PlatformSignupRequest),actor,PlatformSignupRequest).filter(PlatformSignupRequest.created_at>=cutoff,PlatformSignupRequest.deleted_at.is_(None)).all()
    ids={r.id for r in visible}
    events=db.query(PlatformEvent).filter(PlatformEvent.entity=="signup",PlatformEvent.entity_id.in_(ids)).all() if ids else []
    counts={k:len({e.entity_id for e in events if e.action=="signup."+k}) for k in ["approved","rejected","first_login","first_value"]}
    counts["submitted"]=len(visible)
    sources={}
    for r in visible:
        sources[r.source]=sources.get(r.source,0)+1
    metrics=db.query(PlatformRecord).filter(PlatformRecord.kind=="signup_metric",PlatformRecord.created_at>=cutoff).all() if actor.role=="owner" else []
    return {"counts":counts,"source_counts":sources,"form_events":{k:sum(m.title==k for m in metrics) for k in ["started","identity_complete","needs_complete","submitted"]},
        "period":"last 30 days by submission cohort","first_value_definition":"Customer marked first useful action complete","privacy":"Coarse opt-in form events; no form answers or email addresses in telemetry"}
