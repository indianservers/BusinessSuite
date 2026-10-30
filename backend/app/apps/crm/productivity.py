"""Sales worklists and handovers, always intersected with existing CRM visibility."""
import copy
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.models.user import User
from . import lead_management as lm
from .models import CRMLead, CRMDeal, CRMActivity, CRMTask, CRMQuotation, CRMOwner, CRMTimelineEvent
from .models import CRMPipelineStage,CRMTeam
from .lead_models import CRMLeadOperatingState, CRMLeadManagementConfig

router=APIRouter(prefix="/productivity",tags=["CRM sales productivity"])
OPEN_ACTIVITY={"Pending","To Do","Open","Scheduled","In Progress"}
CLOSED={"lost","won","closed","converted","cancelled","completed","done","rejected","accepted"}
LIMIT=5000
READ=(*lm.ACCESS,"crm_deals_view","crm_deals_manage","crm_contacts_view","crm_accounts_view","crm_activities_view","crm_quotes_view")


class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid")


def rows(db,user,entity,scope="all",lock=False):
    crm=lm.core();crm._assert_entity_permission(entity,user,"view")
    resource=crm._get_resource(entity)
    query=crm._apply_record_visibility(crm._base_query(db,resource,crm._organization_id(db,user)),resource,user,db)
    if scope=="mine" and resource.owner_field:
        query=query.filter(getattr(resource.model,resource.owner_field)==user.id)
    elif scope=="team":
        teamids=crm._crm_user_scope(db,user)["team_ids"]
        if not teamids or not hasattr(resource.model,"assigned_team_id"): query=query.filter(False)
        else: query=query.filter(resource.model.assigned_team_id.in_(teamids))
    if lock: query=query.with_for_update()
    return query


def allowed(user,entity,action):
    try:lm.core()._assert_entity_permission(entity,user,action);return True
    except HTTPException:return False


def communication_history(db,user,entity,ident,organization_id):
    if not user or not (user.is_superuser or lm.core()._crm_permission_names(user).intersection({"communication_view","communication_email_send"})):return []
    from app.apps.communication.models import CommunicationTimelineEvent
    return db.query(CommunicationTimelineEvent).filter_by(organization_id=organization_id,record_type=record_kind(entity),record_id=ident).order_by(CommunicationTimelineEvent.created_at.desc()).limit(100).all()


def safe_rows(db,user,entity,scope):
    return rows(db,user,entity,scope).order_by(lm.core()._get_resource(entity).model.id).limit(LIMIT+1).all() if allowed(user,entity,"view") else []


def record_kind(entity):
    return {"leads":"lead","deals":"deal","contacts":"contact","companies":"company","quotations":"quotation"}.get(entity,entity.rstrip("s"))


@router.get("/home")
def home(scope:Literal["mine","team","all"]="mine",timezone_name:str="Asia/Kolkata",db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    crm=lm.core();org=crm._organization_id(db,user);at=lm.now()
    try: zone=ZoneInfo(timezone_name)
    except (ValueError,ZoneInfoNotFoundError): raise HTTPException(422,"Choose a valid sales worklist time zone")
    local_today=at.astimezone(zone).date()
    collections={e:safe_rows(db,user,e,scope) for e in ("leads","deals","activities","tasks","quotations")}
    if scope=="mine":
        # Delegated follow-ups belong in My Work even when the parent has another owner.
        for entity,field in (("leads","lead_id"),("deals","deal_id")):
            if not allowed(user,entity,"view"):continue
            related={getattr(a,field) for e in ("activities","tasks") for a in collections[e] if a.status in OPEN_ACTIVITY and getattr(a,field)}
            existing={r.id for r in collections[entity]}
            model=crm._get_resource(entity).model
            collections[entity]+=[r for r in rows(db,user,entity).filter(model.id.in_(related-existing)).limit(LIMIT+1)]
    truncated=any(len(v)>LIMIT for v in collections.values())
    collections={e:v[:LIMIT] for e,v in collections.items()}
    states={s.lead_id:s for s in db.query(CRMLeadOperatingState).filter(CRMLeadOperatingState.organization_id==org,CRMLeadOperatingState.lead_id.in_([l.id for l in collections["leads"]]))} if collections["leads"] else {}
    events=db.query(CRMTimelineEvent).filter(CRMTimelineEvent.organization_id==org,CRMTimelineEvent.record_type=="deal",CRMTimelineEvent.record_id.in_([d.id for d in collections["deals"]]),CRMTimelineEvent.event_type.in_(["stage_change","stage_changed","deal_stage_changed","stage_moved","call","meeting","email","note","message"])).order_by(CRMTimelineEvent.occurred_at.desc()).all() if collections["deals"] else []
    entered={};interacted={};zones={}
    for e in events:
        if (e.metadata_json or {}).get("timezone"): zones.setdefault(e.record_id,e.metadata_json["timezone"])
        if e.event_type in {"stage_change","stage_changed","deal_stage_changed","stage_moved"}: entered.setdefault(e.record_id,lm.dt(e.occurred_at))
        else: interacted.setdefault(e.record_id,lm.dt(e.occurred_at))
    lead_list=[];deals=[];quotes=[];contact_next=[];exceptions=[];buckets={k:0 for k in ("overdue","today","tomorrow","unscheduled")}
    tomorrow=local_today+timedelta(days=1)
    settings=lm.config(db,org)
    teams={t.id:t.name for t in db.query(CRMTeam).filter_by(organization_id=org,deleted_at=None,status="Active")}
    routed_teams={o.user_id:teams.get(o.team_id) for o in db.query(CRMOwner).filter(CRMOwner.organization_id==org,CRMOwner.user_id.in_([r.get("ownerId") for r in settings["assignment"].get("rules",[])]),CRMOwner.deleted_at.is_(None))}
    def bucket(due):
        due=lm.dt(due)
        return "unscheduled" if not due else "overdue" if due<at else "today" if due.astimezone(zone).date()==local_today else "tomorrow" if due.astimezone(zone).date()==tomorrow else "later"
    for lead in collections["leads"]:
        state=states.get(lead.id);details=state.data_json if state else {}
        if details.get("archived"):continue
        active=not lead.is_converted and (lead.status or "").lower() not in CLOSED
        due=lm.dt(lead.next_follow_up_at);b=bucket(due)
        reason=[]
        if active:
            if b in buckets:buckets[b]+=1
            if b=="overdue":reason.append(f"Follow-up overdue by {max(1,int((at-due).total_seconds()/3600))} hours")
            elif b=="today":reason.append("Follow-up promised today")
            if not due:reason.append("No next action")
            if not lead.last_contacted_at:reason.append("No contact logged yet")
            if lead.rating=="Hot" or (lead.lead_score or 0)>=70:reason.append("High-priority prospect")
        item={"entity":"leads","id":lead.id,"name":lead.full_name,"email":lead.email,"phone":lead.phone,"phone_country_code":lead.phone_country_code,"source":lead.source or "Missing source","owner_id":lead.owner_user_id,"team_id":lead.assigned_team_id,"status":lead.status,"due":due,"bucket":b,"age_days":max(0,(at-(lm.dt(lead.created_at) or at)).days),"score":lead.lead_score or 0,"importance":lead.rating or "Warm","timezone":details.get("customerTimezone") or "Not recorded","no_next_action":active and not due,"why":reason,"can_edit":allowed(user,"leads","manage"),"version":state.version if state else 0}
        lead_list.append(item)
        suggestion=teams.get(lead.assigned_team_id)
        if not suggestion:
            rule=next((r for r in settings["assignment"].get("rules",[]) if str(getattr(lead,crm._snake(r.get("field","")),"") or "").casefold()==str(r.get("equals","")).casefold()),None)
            suggestion=routed_teams.get(rule.get("ownerId")) if rule else None
        if active:
            contact_next.append({**item,"rank":(1000 if b=="overdue" else 700 if b=="today" else 400 if not due else 0)+(lead.lead_score or 0)})
            if not lead.owner_user_id:exceptions.append({**item,"issue":"Unassigned lead","suggested_team":suggestion or (f"Territory #{lead.territory_id}" if lead.territory_id else "Review territory and source routing")})
            if not due:exceptions.append({**item,"issue":"Missing next action"})
    for deal in collections["deals"]:
        active=(deal.status or "").lower() not in CLOSED;last=interacted.get(deal.id) or lm.dt(deal.last_activity_at or deal.created_at) or at
        age=max(0,(at-last).days);due=lm.dt(deal.next_follow_up_at);b=bucket(due)
        why=[]
        if active and b in buckets:buckets[b]+=1
        if active and b=="overdue":why.append("Deal follow-up overdue")
        if active and age>=settings["staleDays"]:why.append(f"No interaction recorded for {age} days")
        if active and not due:why.append("No next action")
        item={"entity":"deals","id":deal.id,"name":deal.name,"owner_id":deal.owner_user_id,"status":deal.status,"timezone":zones.get(deal.id,"Not recorded"),"currency":deal.currency or "INR","amount":str(deal.amount or 0),"stage_id":deal.stage_id,"stage_age_days":max(0,(at-(entered.get(deal.id) or lm.dt(deal.created_at) or at)).days),"last_interaction":interacted.get(deal.id) or deal.last_activity_at,"due":due,"bucket":b,"why":why,"no_next_action":active and not due,"can_edit":allowed(user,"deals","manage")}
        deals.append(item)
        if active and why:
            contact_next.append({**item,"rank":900 if b=="overdue" else 350})
            for issue in why:exceptions.append({**item,"issue":issue})
    for quote in collections["quotations"]:
        item={"entity":"quotations","id":quote.id,"name":quote.quote_number,"owner_id":quote.owner_user_id,"status":quote.status,"currency":quote.currency,"amount":str(quote.grand_total or quote.total_amount or 0),"due":quote.expiry_date,"approval_status":quote.approval_status,"version":quote.version_number,"sent_at":quote.sent_at}
        quotes.append(item)
        if quote.expiry_date and quote.expiry_date<local_today and (quote.status or "").lower() not in CLOSED:exceptions.append({**item,"issue":"Overdue quotation"})
    owners={i.owner_user_id for v in collections.values() for i in v if i.owner_user_id}
    names={p.id:(p.person.display_name if p.person else p.email) for p in db.query(User).filter(User.id.in_(owners))} if owners else {}
    for items in (lead_list,deals,quotes,contact_next,exceptions):
        for item in items:item["owner_name"]=names.get(item["owner_id"],"Unassigned")
    worklist_limit=500
    truncated=truncated or any(len(items)>worklist_limit for items in (lead_list,deals,quotes,exceptions,collections["tasks"],collections["activities"]))
    return {"worklist_limit":worklist_limit,"organization_id":org,"scope":scope,"scope_label":{"mine":"My Records","team":"My Team’s Records","all":"All Permitted Records"}[scope],"refreshed_at":at,"period":"Current open work; archived leads and deleted records excluded","truncated":truncated,"limit_per_type":LIMIT,"buckets":buckets,"leads":lead_list[:worklist_limit],"deals":deals[:worklist_limit],"quotations":quotes[:worklist_limit],"next_contacts":sorted(contact_next,key=lambda i:(-i["rank"],str(i.get("due") or ""),i["id"]))[:30],"exceptions":exceptions[:worklist_limit],"tasks":[{"id":t.id,"title":t.title,"status":t.status,"due_date":t.due_date,"lead_id":t.lead_id,"deal_id":t.deal_id} for t in collections["tasks"][:worklist_limit] if t.status in OPEN_ACTIVITY],"activities":[{"id":a.id,"title":a.title,"subject":a.subject,"status":a.status,"due_date":a.due_date,"lead_id":a.lead_id,"deal_id":a.deal_id} for a in collections["activities"][:worklist_limit] if a.status in OPEN_ACTIVITY],"can_assign":crm._crm_can_assign_beyond_self(user),"team_available":bool(crm._crm_user_scope(db,user)["team_ids"])}


@router.get("/search")
def search(q:str=Query(min_length=2,max_length=150),scope:Literal["mine","team","all"]="all",db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    found=[];crm=lm.core();term="%"+q.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
    for entity in ("leads","contacts","companies","deals","quotations"):
        if not allowed(user,entity,"view"):continue
        resource=crm._get_resource(entity)
        query=rows(db,user,entity,scope).filter(or_(*[getattr(resource.model,f).ilike(term,escape="\\") for f in resource.search]))
        for item in query.order_by(resource.model.id.desc()).limit(12):
            if entity=="leads":
                state=lm.state(db,item,False)
                if state and state.data_json.get("archived"):continue
            found.append({"entity":entity,"id":item.id,"name":getattr(item,"full_name",None) or getattr(item,"name",None) or getattr(item,"quote_number",None),"email":getattr(item,"email",None),"phone":getattr(item,"phone",None),"status":getattr(item,"status",None)})
    return {"items":found,"scope":scope,"limit_per_type":12,"includes_archived":False}


@router.get("/duplicate-check")
def duplicate_check(email:str="",phone:str="",phone_country_code:str="",db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.ACCESS))):
    if len(email)>150 or len(phone)>40:raise HTTPException(422,"Contact details are too long")
    matches=lm.duplicates(db,lm.core()._organization_id(db,user),{"email":email,"phone":phone,"phone_country_code":phone_country_code}) if email.strip() or phone.strip() else []
    visible=lm.visible_query(db,user).filter(CRMLead.id.in_(matches)).all() if matches else []
    return {"matched":bool(matches),"items":[{"id":m.id,"name":m.full_name,"email":m.email,"phone":m.phone,"status":m.status} for m in visible],"message":"A matching lead exists. Review the existing record before creating another." if matches else "No matching email or phone found in this organization"}



class Handover(Strict):
    from_user_id:int
    to_user_id:int
    reason:str=Field(min_length=3,max_length=1000)
    preview_version:str|None=None


def handover_data(db,user,data,lock=False):
    crm=lm.core();org=crm._organization_id(db,user)
    if not crm._crm_can_assign_beyond_self(user):raise HTTPException(403,"CRM assignment authority is required")
    if data.from_user_id==data.to_user_id:raise HTTPException(422,"Choose a different replacement salesperson")
    lm.check_owner(db,user,data.to_user_id)
    groups={}
    for entity in ("leads","deals","activities","tasks"):
        crm._assert_entity_permission(entity,user,"manage")
        query=rows(db,user,entity,lock=lock).filter(crm._get_resource(entity).model.owner_user_id==data.from_user_id)
        if entity in {"activities","tasks"}:query=query.filter(crm._get_resource(entity).model.status.in_(OPEN_ACTIVITY))
        else:query=query.filter(func.lower(crm._get_resource(entity).model.status).notin_(CLOSED))
        records=query.order_by(crm._get_resource(entity).model.id).limit(LIMIT+1).all()
        if len(records)>LIMIT:raise HTTPException(422,"This handover exceeds 5,000 records per type; narrow the scope first")
        if entity=="leads":records=[r for r in records if not r.is_converted and not (lm.state(db,r,False) and lm.state(db,r,False).data_json.get("archived"))]
        groups[entity]=records
    stamp={e:[(r.id,r.owner_user_id,str(r.updated_at),lm.state(db,r,False).version if e=="leads" and lm.state(db,r,False) else None) for r in v] for e,v in groups.items()}
    token=hashlib.sha256(json.dumps({"org":org,"actor":user.id,"from":data.from_user_id,"to":data.to_user_id,"reason":data.reason,"rows":stamp},sort_keys=True).encode()).hexdigest()
    return groups,token


@router.post("/handover/preview")
def preview_handover(data:Handover,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.WRITE))):
    groups,token=handover_data(db,user,data)
    loads={e:rows(db,user,e).filter(lm.core()._get_resource(e).model.owner_user_id==data.to_user_id).count() for e in groups}
    return {"organization_id":lm.core()._organization_id(db,user),"scope":"All permitted open records; excluded records outside your scope are not transferred","counts":{e:len(v) for e,v in groups.items()},"replacement_workload":loads,"items":{e:[{"id":r.id,"name":getattr(r,"full_name",None) or getattr(r,"name",None) or getattr(r,"title",None) or getattr(r,"subject",None)} for r in v] for e,v in groups.items()},"version":token}


@router.post("/handover/apply")
def apply_handover(data:Handover,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.WRITE))):
    if not data.reason.strip() or len(data.reason.strip())<3:raise HTTPException(422,"Explain the reassignment")
    groups,token=handover_data(db,user,data,True)
    if token!=data.preview_version:raise HTTPException(409,"Work or handover choices changed. Review a fresh preview before applying")
    for entity,records in groups.items():
        for record in records:
            before=record.owner_user_id;record.owner_user_id=data.to_user_id;record.updated_by_user_id=user.id;record.updated_at=lm.now()
            if entity=="leads":
                state=lm.state(db,record);state.data_json={**state.data_json,"assignmentReason":data.reason};state.version+=1
                lm.event(db,record,user,"assignment","Ownership transferred",{"previousOwnerId":before,"ownerId":data.to_user_id,"reason":data.reason},data.reason)
            else:lm.core()._create_timeline_activity(db,organization_id=record.organization_id,entity_type=record_kind(entity),entity_id=record.id,activity_type="ownership_handover",title="Ownership transferred",body=data.reason,user_id=user.id,metadata={"previousOwnerId":before,"ownerId":data.to_user_id,"reason":data.reason})
    db.commit()
    return {"message":"Permitted open CRM work transferred together","transferred":{e:len(v) for e,v in groups.items()}}


class LogInteraction(Strict):
    entity:Literal["leads","deals"]
    record_id:int
    channel:Literal["call","meeting"]="call"
    outcome:Literal["Connected","No Answer","Callback Requested","Not Interested"]
    notes:str=Field(default="",max_length=4000)
    next_follow_up:datetime|None=None
    no_next_reason:str=Field(default="",max_length=1000)
    timezone:str=Field(default="Asia/Kolkata",max_length=60)
    complete_activity_id:int|None=None


@router.post("/interaction")
def interaction(data:LogInteraction,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.WRITE,"crm_deals_manage"))):
    try:ZoneInfo(data.timezone)
    except (ValueError,ZoneInfoNotFoundError):raise HTTPException(422,"Choose a valid customer time zone")
    if data.next_follow_up and lm.dt(data.next_follow_up)<=lm.now():raise HTTPException(422,"Choose a future follow-up time")
    if not data.next_follow_up and len(data.no_next_reason.strip())<3:raise HTTPException(422,"Schedule the next follow-up or explain why no next action is needed")
    crm=lm.core();crm._assert_entity_permission(data.entity,user,"manage")
    resource=crm._get_resource(data.entity);record=rows(db,user,data.entity,lock=True).filter(resource.model.id==data.record_id).first()
    if not record:raise HTTPException(404,"Record not found in your permitted scope")
    activity=None
    if data.complete_activity_id:
        activity=rows(db,user,"activities",lock=True).filter(CRMActivity.id==data.complete_activity_id).first()
        field="lead_id" if data.entity=="leads" else "deal_id"
        if not activity or getattr(activity,field)!=record.id or activity.status not in OPEN_ACTIVITY:raise HTTPException(409,"The follow-up changed or is outside this record; refresh before completing")
    metadata={"outcome":data.outcome,"timezone":data.timezone,"previousCommitment":str(record.next_follow_up_at) if record.next_follow_up_at else None,"nextFollowUp":data.next_follow_up.isoformat() if data.next_follow_up else None,"noNextActionReason":data.no_next_reason}
    body=f"{data.outcome}\n{data.notes}".strip()
    crm._create_timeline_activity(db,organization_id=record.organization_id,entity_type=record_kind(data.entity),entity_id=record.id,activity_type=data.channel,title=f"{data.channel.title()}: {data.outcome}",body=body,user_id=user.id,metadata=metadata)
    if activity:activity.status="Completed";activity.completed_at=lm.now();activity.outcome=body
    if data.next_follow_up:
        field="lead_id" if data.entity=="leads" else "deal_id"
        db.add(CRMActivity(organization_id=record.organization_id,owner_user_id=record.owner_user_id or user.id,entity_type=record_kind(data.entity),entity_id=record.id,**{field:record.id},activity_type="call",title="Next follow-up: "+data.outcome,subject="Next follow-up: "+data.outcome,status="Pending",due_date=lm.dt(data.next_follow_up),activity_date=lm.dt(data.next_follow_up),metadata_json={"timezone":data.timezone},branch_id=record.branch_id,department_id=record.department_id,assigned_team_id=record.assigned_team_id,created_by_user_id=user.id))
    record.next_follow_up_at=lm.dt(data.next_follow_up);record.updated_at=lm.now();record.updated_by_user_id=user.id
    if data.entity=="leads":
        state=lm.state(db,record);details={**state.data_json,"customerTimezone":data.timezone,"lastActivityAt":lm.now().isoformat(),"enquiryPending":False};details.setdefault("firstContactAt",lm.now().isoformat())
        if data.outcome in {"Connected","Callback Requested","Not Interested"}:lm.stop_sequence(db,record,details,"Customer response recorded")
        state.data_json=details;state.version+=1;record.last_contacted_at=lm.now()
        lm.refresh_next_follow_up(db,record)
    else:
        record.last_activity_at=lm.now()
        db.flush()
        pending=db.query(CRMActivity).filter(CRMActivity.organization_id==record.organization_id,CRMActivity.deal_id==record.id,CRMActivity.status.in_(OPEN_ACTIVITY),CRMActivity.due_date.isnot(None)).order_by(CRMActivity.due_date,CRMActivity.id).first()
        record.next_follow_up_at=pending.due_date if pending else None
    db.commit()
    return {"message":"Outcome and next action saved together"}


class Reschedule(Strict):
    due_at:datetime
    reason:str=Field(min_length=3,max_length=1000)


@router.post("/activities/{ident}/reschedule")
def reschedule(ident:int,data:Reschedule,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.WRITE))):
    lm.core()._assert_entity_permission("activities",user,"manage")
    item=rows(db,user,"activities",lock=True).filter(CRMActivity.id==ident).first()
    if not item or item.status not in OPEN_ACTIVITY:raise HTTPException(409,"Follow-up is no longer pending or is outside your scope")
    if lm.dt(data.due_at)<=lm.now() or len(data.reason.strip())<3:raise HTTPException(422,"Choose a future date and explain the reschedule")
    old=item.due_date;item.due_date=item.activity_date=lm.dt(data.due_at)
    item.metadata_json={**(item.metadata_json or {}),"commitmentHistory":[*((item.metadata_json or {}).get("commitmentHistory",[])),{"previous":str(old),"new":data.due_at.isoformat(),"reason":data.reason,"actor":user.id,"at":lm.now().isoformat()}]}
    if item.lead_id:
        lead=lm.lead_record(db,user,item.lead_id,True,True);lm.refresh_next_follow_up(db,lead);s=lm.state(db,lead);s.version+=1
        lm.event(db,lead,user,"follow_up_rescheduled","Follow-up rescheduled",{"previous":str(old),"new":data.due_at.isoformat(),"reason":data.reason},data.reason)
    elif item.deal_id:
        deal=rows(db,user,"deals",lock=True).filter(CRMDeal.id==item.deal_id).first()
        if not deal:raise HTTPException(403,"Deal is outside your scope")
        lm.core()._assert_entity_permission("deals",user,"manage");deal.next_follow_up_at=lm.dt(data.due_at)
    db.commit();return {"message":"Rescheduled; previous commitment retained in history"}


class SharedView(Strict):
    name:str=Field(min_length=1,max_length=80)
    search:str=Field(default="",max_length=150)
    stage:str=Field(default="",max_length=60)
    owner:str=Field(default="",max_length=20)
    queue:str=Field(default="all",max_length=30)
    view:Literal["table","board","followups"]="table"


@router.get("/shared-views")
def shared_views(db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.ACCESS))):
    config=db.get(CRMLeadManagementConfig,lm.core()._organization_id(db,user))
    return {"items":(config.settings_json or {}).get("productivityViews",[]) if config else [],"can_share":lm.core()._crm_can_assign_beyond_self(user)}


@router.post("/shared-views")
def save_shared_view(data:SharedView,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.WRITE))):
    if not lm.core()._crm_can_assign_beyond_self(user):raise HTTPException(403,"Sales manager or Admin authority is required to publish shared views")
    if not data.name.strip():raise HTTPException(422,"Name the shared view")
    row=db.query(CRMLeadManagementConfig).filter_by(organization_id=lm.core()._organization_id(db,user)).with_for_update().first()
    if not row:row=CRMLeadManagementConfig(organization_id=lm.core()._organization_id(db,user),settings_json={});db.add(row)
    views=(row.settings_json or {}).get("productivityViews",[])
    if any(v["name"].casefold()==data.name.strip().casefold() for v in views):raise HTTPException(409,"A shared view with that name already exists")
    if len(views)>=50:raise HTTPException(422,"This organization already has 50 shared views")
    row.settings_json={**(row.settings_json or {}),"productivityViews":[*views,{**data.model_dump(),"name":data.name.strip()}]};row.updated_by=user.id
    db.commit();return {"message":"Shared view saved; record permissions still apply"}


def stage_requirements(db,deal,stage,values=None):
    values=values or {}
    settings=lm.config(db,deal.organization_id).get("dealStageGuidance",{}).get(str(stage.id),{})
    required=[f for f in settings.get("required",[]) if f in {"company_id","contact_id","amount","expected_close_date","next_follow_up_at","lead_source"}]
    missing=[f for f in required if values.get(f,getattr(deal,f,None)) in (None,"",0)]
    if stage.is_lost or (stage.stage_type or "").lower()=="lost":
        if len(str(values.get("lost_reason",deal.lost_reason or deal.loss_reason or "")).strip())<5:missing.append("lost_reason")
    return {"required":required,"missing":missing,"recommended_actions":settings.get("actions") or "Log the latest conversation, confirm the customer decision and agree the next action.","completion_criteria":settings.get("completion") or ("Record a meaningful loss reason" if stage.is_lost else "Resolve entry requirements and obtain any required approvals before moving")}


@router.get("/deals/{ident}/stages")
def deal_stage_plan(ident:int,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*READ))):
    record=rows(db,user,"deals").filter(CRMDeal.id==ident).first()
    if not record:raise HTTPException(404,"Deal not found in your permitted scope")
    stages=db.query(CRMPipelineStage).filter_by(pipeline_id=record.pipeline_id,organization_id=record.organization_id,deleted_at=None).order_by(CRMPipelineStage.position).all()
    return {"current_stage_id":record.stage_id,"values":{f:str(getattr(record,f) or "") for f in ("company_id","contact_id","amount","expected_close_date","next_follow_up_at","lead_source")},"stages":[{"id":s.id,"name":s.name,"is_won":s.is_won,"is_lost":s.is_lost,"probability":s.probability,**stage_requirements(db,record,s)} for s in stages]}


class StageMove(Strict):
    stage_id:int
    corrections:dict=Field(default_factory=dict)
    lost_reason:str=Field(default="",max_length=1000)
    reactivate_at:datetime|None=None


@router.post("/deals/{ident}/transition")
def transition_deal(ident:int,data:StageMove,db:Session=Depends(get_db),user:User=Depends(RequirePermission(*lm.WRITE,"crm_deals_manage"))):
    crm=lm.core();crm._assert_entity_permission("deals",user,"manage")
    record=rows(db,user,"deals",lock=True).filter(CRMDeal.id==ident).first()
    if not record:raise HTTPException(404,"Deal not found in your permitted scope")
    stage=db.query(CRMPipelineStage).filter_by(id=data.stage_id,pipeline_id=record.pipeline_id,organization_id=record.organization_id,deleted_at=None).first()
    if not stage:raise HTTPException(422,"Stage must belong to this deal's pipeline")
    permitted={"company_id","contact_id","amount","expected_close_date","next_follow_up_at","lead_source"}
    if set(data.corrections)-permitted:raise HTTPException(422,"Unsupported correction fields")
    values={**data.corrections,"stage_id":stage.id,"probability":stage.probability}
    if stage.is_lost or (stage.stage_type or "").lower()=="lost":values.update(status="Lost",lost_reason=data.lost_reason)
    elif stage.is_won or (stage.stage_type or "").lower()=="won":values["status"]="Won"
    else:values["status"]="Open"
    plan=stage_requirements(db,record,stage,values)
    if plan["missing"]:raise HTTPException(422,{"message":"Resolve the stage entry requirements","missingFields":plan["missing"]})
    if data.reactivate_at and (values["status"]!="Lost" or lm.dt(data.reactivate_at)<=lm.now()):raise HTTPException(422,"Reactivation review must be a future date for a lost deal")
    for field,entity in (("contact_id","contacts"),("company_id","companies")):
        if values.get(field) and int(values[field])!=getattr(record,field):crm._assert_record_visible(db,crm._get_resource(entity),int(values[field]),record.organization_id,user)
    if data.reactivate_at:
        # Included in the same transaction as the established update service's commit.
        db.add(CRMTask(organization_id=record.organization_id,owner_user_id=record.owner_user_id or user.id,deal_id=record.id,title="Review lost opportunity for reactivation",due_date=lm.dt(data.reactivate_at),status="To Do",description=data.lost_reason,created_by_user_id=user.id,branch_id=record.branch_id,department_id=record.department_id,assigned_team_id=record.assigned_team_id))
    result=crm.update_record("deals",ident,crm.CRMRecordPayload(**values),db,user)
    return result
