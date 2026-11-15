"""General CRM sales process, meeting outcomes and idempotent internal automation."""
from __future__ import annotations
import copy
from datetime import datetime, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.models.user import User
from app.models.notification import Notification
from app.apps.crm.models import CRMLead, CRMMeeting, CRMDeal, CRMCompany, CRMContact, CRMActivity, CRMPipeline, CRMPipelineStage
from app.apps.crm.lead_models import CRMLeadManagementConfig

router = APIRouter()
STAGES = [("Consultation Scheduled", 25), ("Demo Completed", 45), ("Proposal Sent", 60), ("Negotiation", 80), ("Won", 100), ("Lost", 0)]
OUTCOMES = ("Scheduled", "Confirmed", "Attended", "No-show", "Rescheduled")

def lm():
    from app.apps.crm import lead_management
    return lead_management

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Setup(Strict):
    ownerIds: list[int] = Field(min_length=1, max_length=100)
    managerId: int = Field(gt=0)

@router.post("/sales-process/setup")
def setup(payload: Setup, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_admin"))):
    m = lm()
    org = m.core()._organization_id(db, user)
    # Serialize provisioning and assignment cursor changes on the tenant config.
    row = db.query(CRMLeadManagementConfig).filter_by(organization_id=org).with_for_update().first()
    for ident in set(payload.ownerIds + [payload.managerId]):
        m.check_owner(db, user, ident)
    manager = db.get(User, payload.managerId)
    if not m.core()._crm_can_assign_beyond_self(manager):
        raise HTTPException(422, "Choose a sales manager with CRM assignment permission")
    settings = m.config(db, org)
    process = settings.get("salesProcess", {})
    pipeline = db.query(CRMPipeline).filter_by(id=process.get("pipelineId"), organization_id=org, deleted_at=None).first() if process.get("pipelineId") else None
    if not pipeline:
        pipeline = CRMPipeline(organization_id=org, name="Sales Conversion", description="Qualified opportunity through consultation, demo, proposal and closure", active=True, is_default=False, created_by_user_id=user.id)
        db.add(pipeline)
        db.flush()
        for position, (name, probability) in enumerate(STAGES):
            db.add(CRMPipelineStage(organization_id=org, pipeline_id=pipeline.id, name=name, probability=probability, position=position, order_index=position, stage_type=name.lower() if name in {"Won", "Lost"} else "open", is_won=name=="Won", is_lost=name=="Lost", active=True))
    settings["salesProcess"] = {"enabled": True, "pipelineId": pipeline.id, "managerId": payload.managerId}
    settings["assignment"] = {**settings["assignment"], "mode": "round_robin", "ownerIds": list(dict.fromkeys(payload.ownerIds))}
    settings["slaHours"] = 24
    settings["staleDays"] = 7
    if not row:
        row = CRMLeadManagementConfig(organization_id=org)
        db.add(row)
    row.settings_json = settings
    row.updated_by = user.id
    db.commit()
    return {"enabled": True, "pipelineId": pipeline.id}

@router.get("/sales-process")
def process_info(db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "crm_leads_view", "crm_leads_manage"))):
    m = lm()
    m.core()._assert_entity_permission("leads", user, "view")
    config = m.config(db, m.core()._organization_id(db, user))
    return {**config.get("salesProcess", {"enabled": False}), "ownerIds": config["assignment"]["ownerIds"], "stages": [name for name, _ in STAGES]}

class MeetingOutcome(Strict):
    status: Literal["Confirmed", "Attended", "No-show", "Rescheduled", "Cancelled"]
    startAt: datetime | None = None
    outcome: str = Field(default="", max_length=4000)

def meeting_json(item):
    return {key: getattr(item, key) for key in ("id", "lead_id", "title", "status", "start_time", "end_time", "outcome", "description")}

@router.get("/leads/{ident}/meetings")
def meetings(ident: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission(*("crm_view", "crm_manage", "crm_admin", "crm_leads_view", "crm_leads_manage")))):
    lead = lm().lead_record(db, user, ident)
    return [meeting_json(item) for item in db.query(CRMMeeting).filter_by(organization_id=lead.organization_id, lead_id=ident, deleted_at=None).order_by(CRMMeeting.start_time.desc()).all()]

@router.patch("/leads/{ident}/meetings/{meeting_id}")
def meeting_outcome(ident: int, meeting_id: int, payload: MeetingOutcome, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_manage", "crm_admin", "crm_leads_manage"))):
    m = lm()
    lead = m.lead_record(db, user, ident, True, True)
    item = db.query(CRMMeeting).filter_by(id=meeting_id, organization_id=lead.organization_id, lead_id=ident, deleted_at=None).with_for_update().first()
    if not item:
        raise HTTPException(404, "Meeting not found")
    if item.status == payload.status and payload.status != "Rescheduled":
        return meeting_json(item)
    if item.status in {"Attended", "Completed", "No-show", "Rescheduled", "Cancelled"}:
        raise HTTPException(409, "This meeting already has a final outcome")
    if payload.status in {"Attended", "No-show"} and m.dt(item.start_time) > m.now():
        raise HTTPException(422, "Record attendance after the meeting starts")
    if payload.status == "Rescheduled":
        start = m.dt(payload.startAt)
        if not start or start <= m.now():
            raise HTTPException(422, "Choose a future replacement meeting time")
        end = start + (m.dt(item.end_time) - m.dt(item.start_time))
        db.query(User).filter_by(id=item.owner_user_id).with_for_update().first()
        if db.query(CRMMeeting.id).filter(CRMMeeting.organization_id==lead.organization_id, CRMMeeting.owner_user_id==item.owner_user_id, CRMMeeting.id!=item.id, CRMMeeting.deleted_at.is_(None), CRMMeeting.status.in_(["Scheduled", "Confirmed"]), CRMMeeting.start_time < end, CRMMeeting.end_time > start).first():
            raise HTTPException(409, "The owner already has a meeting at this time")
        db.add(CRMMeeting(organization_id=lead.organization_id, owner_user_id=item.owner_user_id, lead_id=ident, deal_id=item.deal_id, title=item.title, description=item.description, start_time=start, end_time=end, status="Scheduled", created_by_user_id=user.id))
        lead.next_follow_up_at = start
    previous = item.status
    item.status = payload.status
    item.outcome = payload.outcome
    item.updated_by_user_id = user.id
    m.event(db, lead, user, "meeting_outcome", f"Meeting {payload.status.lower()}", {"meetingId": item.id, "from": previous, "to": payload.status}, payload.outcome)
    if payload.status == "Attended":
        row = m.state(db, lead)
        row.data_json = {**row.data_json, "lastResponseAt": m.now().isoformat()}
        row.version += 1
        completed_demo(db, lead, user, item)
    db.commit()
    return meeting_json(item)

class NurtureConsent(Strict):
    allowed: bool
    evidence: str = Field(min_length=1, max_length=1000)

    @field_validator("evidence")
    @classmethod
    def evidence_required(cls, value):
        if not value.strip(): raise ValueError("Record permission evidence or a withdrawal reason")
        return value.strip()

@router.get("/leads/{ident}/nurture-consent")
def get_nurture_consent(ident: int, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "crm_leads_view", "crm_leads_manage"))):
    m = lm()
    lead = m.lead_record(db, user, ident)
    row = m.state(db, lead, False)
    return (row.data_json or {}).get("nurtureConsent", {"allowed": False, "evidence": ""}) if row else {"allowed": False, "evidence": ""}

@router.put("/leads/{ident}/nurture-consent")
def nurture_consent(ident: int, payload: NurtureConsent, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_manage", "crm_admin", "crm_leads_manage"))):
    m = lm()
    lead = m.lead_record(db, user, ident, True, True)
    row = m.state(db, lead)
    row.data_json = {**row.data_json, "nurtureConsent": {"allowed": payload.allowed, "evidence": payload.evidence, "recordedAt": m.now().isoformat(), "recordedBy": user.id}}
    row.version += 1
    m.event(db, lead, user, "consent", "Nurture permission recorded" if payload.allowed else "Nurture permission withdrawn")
    db.commit()
    return {"saved": True}

@router.get("/meeting-metrics")
def metrics(search: str = "", stage: str = "", owner: int | None = None, db: Session = Depends(get_db), user: User = Depends(RequirePermission("crm_view", "crm_manage", "crm_admin", "crm_leads_view", "crm_leads_manage"))):
    m = lm()
    query = m.filter_record_type(m.visible_query(db, user), "Lead")
    if search:
        pattern = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        from sqlalchemy import or_
        query = query.filter(or_(CRMLead.full_name.ilike(pattern, escape="\\"), CRMLead.company_name.ilike(pattern, escape="\\"), CRMLead.email.ilike(pattern, escape="\\")))
    if stage: query = query.filter(CRMLead.status == stage)
    if owner: query = query.filter(CRMLead.owner_user_id == owner)
    counts = dict(db.query(CRMMeeting.status, func.count(CRMMeeting.id)).filter(CRMMeeting.lead_id.in_(query.with_entities(CRMLead.id)), CRMMeeting.organization_id==m.core()._organization_id(db, user), CRMMeeting.deleted_at.is_(None)).group_by(CRMMeeting.status).all())
    return {"counts": {name: counts.get(name, 0) + (counts.get("Completed", 0) if name == "Attended" else 0) for name in OUTCOMES}, "definition": "Current meeting statuses across all permitted leads matching search, stage and owner. A rescheduled occurrence retains its outcome and creates a new scheduled occurrence; counts are not a sequential funnel."}

def completed_demo(db, lead, user, meeting):
    m = lm()
    process = m.config(db, lead.organization_id).get("salesProcess", {})
    if not process.get("enabled") or not (meeting.description == "Sales meeting: demo" or "demo" in meeting.title.lower()): return
    # The meeting outcome and generated task commit together. Retrying cannot duplicate it.
    m.task(db, lead, user, "Follow up after completed demo", m.now()+timedelta(days=1), metadata={"salesAutomation": "demo_completed", "meetingId": meeting.id, "dealId": lead.converted_deal_id})
    if lead.converted_deal_id:
        deal = db.query(CRMDeal).filter_by(id=lead.converted_deal_id, organization_id=lead.organization_id, deleted_at=None).first()
        target = db.query(CRMPipelineStage).filter_by(pipeline_id=process["pipelineId"], name="Demo Completed", deleted_at=None).first()
        current = db.get(CRMPipelineStage, deal.stage_id) if deal else None
        if deal and target and deal.pipeline_id==target.pipeline_id and current and current.position < target.position and deal.status == "Open":
            m.core().update_record("deals", deal.id, m.core().CRMRecordPayload(stageId=target.id), db, user)

def deal_changed(db, deal, user, before):
    m = lm()
    process = m.config(db, deal.organization_id).get("salesProcess", {})
    if not process.get("enabled") or deal.pipeline_id != process.get("pipelineId") or before.get("stage_id") == deal.stage_id: return
    stage = db.get(CRMPipelineStage, deal.stage_id)
    if not stage: return
    leads = db.query(CRMLead).filter_by(organization_id=deal.organization_id, converted_deal_id=deal.id, deleted_at=None).all()
    for lead in leads:
        row = m.state(db, lead)
        data = copy.deepcopy(row.data_json)
        if stage.name == "Demo Completed":
            existing = db.query(CRMActivity.id).filter(CRMActivity.organization_id==lead.organization_id, CRMActivity.lead_id==lead.id, CRMActivity.status=="Pending", CRMActivity.metadata_json["salesAutomation"].as_string()=="demo_completed").first()
            if not existing:
                m.task(db, lead, user, "Follow up after completed demo", m.now()+timedelta(days=1), metadata={"salesAutomation":"demo_completed", "dealId":deal.id})
        if stage.name == "Proposal Sent":
            due = m.now()+timedelta(days=2)
            data["proposalReminder"] = {"dueAt": due.isoformat(), "sent": False}
            m.task(db, lead, user, "Follow up on proposal (2 days)", due, metadata={"salesAutomation": "proposal", "dealId": deal.id})
        else:
            data.pop("proposalReminder", None)
        if stage.is_won and deal.company_id:
            company = db.query(CRMCompany).filter_by(id=deal.company_id, organization_id=deal.organization_id).first()
            if company: company.account_type = "Customer"
        if stage.is_won and deal.contact_id:
            contact = db.query(CRMContact).filter_by(id=deal.contact_id, organization_id=deal.organization_id).first()
            if contact:
                contact.lifecycle_stage = "Customer"
                contact.customer_since = contact.customer_since or m.now().date()
                tags = {t.strip() for t in (contact.tags_text or "").split(",") if t.strip()}
                contact.tags_text = ", ".join(sorted((tags - {"Opportunity"}) | {"Customer"}))
        row.data_json = data
        row.version += 1

def sales_reminders(db, org, limit):
    m = lm()
    process = m.config(db, org).get("salesProcess", {})
    if not process.get("enabled"): return 0
    from app.apps.crm.lead_models import CRMLeadOperatingState
    # Stable cycle keys are stored in state; sent flags make repeated cron runs safe.
    rows = db.query(CRMLead, CRMLeadOperatingState).join(CRMLeadOperatingState, (CRMLeadOperatingState.lead_id==CRMLead.id)&(CRMLeadOperatingState.organization_id==org)).filter(CRMLead.organization_id==org, CRMLead.deleted_at.is_(None)).order_by(CRMLead.id).with_for_update(of=CRMLeadOperatingState, skip_locked=True).all()
    sent = 0
    for lead, row in rows:
        if sent >= limit: break
        data = copy.deepcopy(row.data_json or {})
        if data.get("archived"): continue
        deal = db.query(CRMDeal).filter_by(id=lead.converted_deal_id, organization_id=org, deleted_at=None).first() if lead.converted_deal_id else None
        closed = lead.status=="Lost" or (deal and str(deal.status).lower() in {"won", "lost"})
        response = m.dt(data.get("lastResponseAt")) or m.dt(lead.created_at) or m.now()
        checks = []
        cycle = response.isoformat()
        if not closed and m.now() >= response+timedelta(days=7) and data.get("managerAlertCycle") != cycle:
            checks.append(("managerAlertCycle", cycle, process.get("managerId"), "No response for 7 days", "lead_no_response"))
        proposal = data.get("proposalReminder", {})
        if not closed and proposal.get("dueAt") and not proposal.get("sent") and m.now() >= m.dt(proposal["dueAt"]):
            checks.append(("proposalReminder", {**proposal, "sent": True}, lead.owner_user_id, "Proposal follow-up due", "lead_proposal_due"))
        consent = data.get("nurtureConsent", {})
        nurture_anchor = max(response, m.dt(consent.get("recordedAt")) or response)
        nurture_cycle = nurture_anchor.isoformat()
        if consent.get("allowed") is True and not (deal and str(deal.status).lower()=="won") and m.now() >= nurture_anchor+timedelta(days=30) and data.get("nurtureAlertCycle") != nurture_cycle:
            checks.append(("nurtureAlertCycle", nurture_cycle, lead.owner_user_id, "Nurture follow-up due (permission recorded)", "lead_nurture_due"))
        for key, value, recipient_id, title, event_type in checks:
            if sent >= limit: break
            recipient = db.get(User, recipient_id) if recipient_id else None
            if not recipient or not recipient.is_active or m.core()._organization_id(db, recipient)!=org: continue
            if not m.visible_query(db, recipient).filter(CRMLead.id==lead.id).first(): continue
            db.add(Notification(company_id=org, user_id=recipient.id, module="crm", title=title, message=f"{lead.full_name}: {title}", event_type=event_type, action_url=f"/crm/leads?lead={lead.id}"))
            data[key] = value
            sent += 1
        if data != row.data_json:
            row.data_json = data
            row.version += 1
    return sent
