"""Full-query CRM dashboard aggregates. Lists remain paginated independently."""
from datetime import datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import func,or_
from .queries import business_context,amounts_by_currency,TERMINAL


def period_queries(db,user,period="all"):
    from .registry import crm_query,open_deals
    from app.apps.crm.models import CRMLead,CRMDeal,CRMTask,CRMPipelineStage
    if period not in {"all","month","quarter"}:raise HTTPException(422,"Choose all, month or quarter")
    context=business_context(db,user)
    day=datetime.fromisoformat(context["business_date"]).date()
    start=day.replace(day=1,month=((day.month-1)//3)*3+1 if period=="quarter" else day.month)
    local=ZoneInfo(context["timezone"])
    begin=datetime.combine(start,time.min,tzinfo=local).astimezone(timezone.utc)
    until=datetime.combine(day+timedelta(days=1),time.min,tzinfo=local).astimezone(timezone.utc)
    leads=crm_query(db,user,"leads");deals=crm_query(db,user,"deals");open_query=open_deals(db,user)
    if period!="all":
        leads=leads.filter(CRMLead.created_at>=begin,CRMLead.created_at<until)
        deals=deals.filter(CRMDeal.expected_close_date>=start,CRMDeal.expected_close_date<=day)
        open_query=open_query.filter(CRMDeal.id.in_(deals.with_entities(CRMDeal.id)))
    context={**context,"period":period,"from_date":start.isoformat() if period!="all" else None,"to_date":day.isoformat() if period!="all" else None,"definition":"Leads by creation date; deals by expected close date. Overdue follow-ups cover all current active leads and tasks. Values are grouped by currency without conversion."}
    return leads,deals,open_query,context


def followup_queries(db,user):
    from .registry import crm_query
    from app.apps.crm.models import CRMLead,CRMTask
    now=datetime.now(timezone.utc)
    leads=crm_query(db,user,"leads").filter(CRMLead.is_converted.is_(False),CRMLead.status.notin_(["Converted","Lost","Disqualified","Archived"]),CRMLead.next_follow_up_at<now)
    tasks=crm_query(db,user,"tasks").filter(CRMTask.due_date<now,CRMTask.status.notin_(TERMINAL))
    return leads,tasks


def dashboard_statistics(db,user,period="all"):
    from app.apps.crm.models import CRMLead,CRMDeal,CRMPipelineStage
    leads,deals,open_query,context=period_queries(db,user,period)
    won_stages=db.query(CRMPipelineStage.id).filter(CRMPipelineStage.is_won.is_(True))
    lost_stages=db.query(CRMPipelineStage.id).filter(CRMPipelineStage.is_lost.is_(True))
    won=deals.filter(or_(CRMDeal.status=="Won",CRMDeal.stage_id.in_(won_stages))).count()
    lost=deals.filter(or_(CRMDeal.status=="Lost",CRMDeal.stage_id.in_(lost_stages))).count()
    overdue_leads_query,overdue_tasks_query=followup_queries(db,user)
    overdue_leads,overdue_tasks=overdue_leads_query.count(),overdue_tasks_query.count()
    grouped=leads.with_entities(CRMLead.source,func.count(CRMLead.id)).group_by(CRMLead.source).order_by(CRMLead.source).all()
    return {"leads_created":leads.count(),"open_deals":open_query.count(),"won_deals":won,"lost_deals":lost,
        "win_rate":round(won/(won+lost)*100,2) if won+lost else None,
        "pipeline_by_currency":amounts_by_currency(open_query,CRMDeal.currency,CRMDeal.amount),
        "weighted_by_currency":amounts_by_currency(open_query,CRMDeal.currency,CRMDeal.amount*func.coalesce(CRMDeal.probability,0)/100.0),
        "lead_sources":[{"name":name or "Missing source","value":count,"count":count} for name,count in grouped],
        "overdue_followups":overdue_leads+overdue_tasks,
        "context":context}


def records(db,user,kind,period="all",page=1,page_size=25):
    from sqlalchemy import literal
    from app.apps.crm.models import CRMLead,CRMDeal,CRMTask
    leads,deals,opened,context=period_queries(db,user,period)
    if kind=="leads":query=leads.with_entities(literal("leads").label("entity"),CRMLead.id.label("id"),CRMLead.full_name.label("name"),CRMLead.status.label("status"),CRMLead.next_follow_up_at.label("due"),literal(None).label("currency"),literal(None).label("amount"))
    elif kind=="open-deals":query=opened.with_entities(literal("deals").label("entity"),CRMDeal.id.label("id"),CRMDeal.name.label("name"),CRMDeal.status.label("status"),CRMDeal.expected_close_date.label("due"),CRMDeal.currency.label("currency"),CRMDeal.amount.label("amount"))
    elif kind=="overdue":
        followups,tasks=followup_queries(db,user)
        one=followups.with_entities(literal("leads").label("entity"),CRMLead.id.label("id"),CRMLead.full_name.label("name"),CRMLead.status.label("status"),CRMLead.next_follow_up_at.label("due"),literal(None).label("currency"),literal(None).label("amount"))
        two=tasks.with_entities(literal("tasks").label("entity"),CRMTask.id.label("id"),CRMTask.title.label("name"),CRMTask.status.label("status"),CRMTask.due_date.label("due"),literal(None).label("currency"),literal(None).label("amount"))
        query=one.union_all(two)
    else:raise HTTPException(422,"Choose leads, open-deals or overdue")
    rows=query.subquery();visible=db.query(rows);total=visible.count()
    return {"items":[dict(row._mapping) for row in visible.order_by(rows.c.entity,rows.c.id).offset((page-1)*page_size).limit(page_size).all()],"total":total,"page":page,"pages":(total+page_size-1)//page_size,"context":context,"unit":"Follow-up commitments" if kind=="overdue" else "Unique CRM records"}
