"""Scoped sales analytics and audited collection planning over existing ledgers."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, RequirePermission
from app.access.catalog import permission_names
from app.services.metrics.queries import business_context
from app.apps.srm.access import sales_order_query, engagement_query, organization_id_for, can_view_all_srm
from app.apps.srm.services.commercial import invoice_query, scoped
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt, SRMReceiptAllocation, SRMRevenueEvent, SRMPOSReturn, SRMInventoryBalance, SRMProduct
from app.apps.srm.commercial_models import SalesTeamAssignment
from app.apps.crm.models import CRMCompany, CRMTeam, CRMQuotation, CRMSalesTarget
from app.models.user import User
from app.models.company import Branch
from app.branches.models import BranchOwnership
from app.shared.models import ServiceEvent
from app.shared.follow_ups import FollowUp

router=APIRouter(prefix="/dashboard-workspace",tags=["Sales dashboard"],dependencies=[Depends(RequirePermission("srm_view","srm_invoice_view","srm_collection_view","srm_admin","srm_profitability_view"))])
SECTIONS=["summary","cash","collections","events","orders","quotations","targets"]
ZERO=Decimal("0")
def dec(value): return Decimal(str(value or 0))
def money(value): return str(dec(value).quantize(Decimal(".01")))
def day(value,zone):
    if not value:return None
    if isinstance(value,datetime):return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).astimezone(ZoneInfo(zone)).date()
    return value
def permitted(user):
    perms=permission_names(user)
    return SECTIONS if user.is_superuser else [s for s in SECTIONS if s not in {"targets","quotations"} or "crm_view" in perms and (s!="targets" or bool(perms & {"srm_profitability_view","srm_admin"}))]
def ownership(db,query,model,user,branch):
    if branch:
        keys=db.query(BranchOwnership.resource_key).filter_by(company_id=organization_id_for(user),resource_table=model.__tablename__,branch_id=branch)
        query=query.filter(cast(model.id,String).in_(keys))
    return query
def sources(db,user,owner=None,team=None,customer=None,branch=None):
    oq=ownership(db,sales_order_query(db,user),SRMSalesOrder,user,branch)
    if owner:oq=oq.filter(SRMSalesOrder.assigned_user_id==owner)
    if customer:oq=oq.filter(SRMSalesOrder.customer_id==customer)
    if team:oq=oq.filter(SRMSalesOrder.id.in_(db.query(SalesTeamAssignment.sales_order_id).filter_by(team_id=team)))
    iq=ownership(db,invoice_query(db,user),SRMInvoice,user,branch)
    if customer:iq=iq.filter(SRMInvoice.customer_id==customer)
    if owner or team:
        visible_orders=oq.with_entities(SRMSalesOrder.id)
        from app.apps.srm.models import SRMEngagement
        visible_engagements=engagement_query(db,user).filter(SRMEngagement.sales_order_id.in_(visible_orders)).with_entities(SRMEngagement.id)
        clauses=[SRMInvoice.sales_order_id.in_(visible_orders),SRMInvoice.engagement_id.in_(visible_engagements)]
        if owner and not team:clauses.append((SRMInvoice.sales_order_id.is_(None)) & (SRMInvoice.created_by==owner))
        iq=iq.filter(or_(*clauses))
    return oq,iq
def row(identity,label,href,**values):return {"id":str(identity),"label":label,"href":href,**values}
def commitment_map(db,user,ids):
    events=db.query(ServiceEvent).filter_by(organization_id=organization_id_for(user),module_key="srm",event_type="dashboard.payment_commitment",entity_type="invoice").filter(ServiceEvent.entity_id.in_(ids)).order_by(ServiceEvent.id).all()
    return {e.entity_id:e.payload_json for e in events}
def groups(records,amount):
    values=defaultdict(lambda:ZERO)
    for r in records:values[r.currency or "Unknown"]+=dec(amount(r))
    return [{"currency":cur,"amount":money(value)} for cur,value in sorted(values.items())]

@router.get("/context")
def context(response:Response,db:Session=Depends(get_db),user=Depends(get_current_user)):
    response.headers["Cache-Control"]="no-store"
    oq,iq=sources(db,user);orders=oq.all();invoices=iq.all()
    owners={o.assigned_user_id for o in orders if o.assigned_user_id}|{i.created_by for i in invoices if i.created_by}
    customers={r.customer_id for r in orders+invoices if r.customer_id}
    teams=db.query(CRMTeam).filter(CRMTeam.id.in_(db.query(SalesTeamAssignment.team_id).filter(SalesTeamAssignment.sales_order_id.in_([o.id for o in orders])))).all()
    keys=[str(o.id) for o in orders]
    branch_ids=db.query(BranchOwnership.branch_id).filter_by(company_id=organization_id_for(user),resource_table=SRMSalesOrder.__tablename__).filter(BranchOwnership.resource_key.in_(keys))
    perms=permission_names(user);actions=(getattr(user,"_suite_grants",None) or {}).get("srm",{}).get("actions")
    create=actions is None or "create" in actions
    return {**business_context(db,user),"sections":permitted(user),"can_create":create and (user.is_superuser or bool(perms & {"srm_manage","srm_admin"})),
        "can_pos":user.is_superuser or bool(perms & {"srm_manage","srm_admin"}),
        "can_plan":(actions is None or "edit" in actions) and (user.is_superuser or bool(perms & {"srm_collection_create","srm_admin"})),
        "owners":[{"id":u.id,"name":u.email} for u in db.query(User).filter(User.id.in_(owners)).all()],
        "teams":[{"id":t.id,"name":t.name} for t in teams],
        "customers":[{"id":c.id,"name":c.name} for c in db.query(CRMCompany).filter(scoped(CRMCompany.organization_id,user),CRMCompany.id.in_(customers)).all()],
        "branches":[{"id":b.id,"name":b.name} for b in db.query(Branch).filter(Branch.company_id==organization_id_for(user),Branch.id.in_(branch_ids)).all()]}

class Commitment(BaseModel):
    model_config=ConfigDict(extra="forbid")
    promised_date:date
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
    next_action:str=Field(min_length=3,max_length=500)
    owner_id:int|None=Field(None,gt=0)

@router.put("/invoices/{identity}/commitment")
def save_commitment(identity:int,data:Commitment,db:Session=Depends(get_db),user=Depends(RequirePermission("srm_collection_create","srm_admin"))):
    invoice=invoice_query(db,user).filter(SRMInvoice.id==identity,SRMInvoice.status.notin_(["draft","cancelled","void"])).with_for_update().first()
    if not invoice:raise HTTPException(404,"Invoice is outside your permitted scope")
    if data.amount>dec(invoice.balance_amount):raise HTTPException(422,"Promise cannot exceed the current outstanding balance")
    if not data.next_action.strip():raise HTTPException(422,"Enter a next action")
    allowed={user.id}|{o.assigned_user_id for o in sales_order_query(db,user).all() if o.assigned_user_id}|{i.created_by for i in invoice_query(db,user).all() if i.created_by}
    if data.owner_id and data.owner_id not in allowed:raise HTTPException(403,"Owner must be a permitted salesperson")
    payload={"promised_date":data.promised_date.isoformat(),"amount":money(data.amount),"next_action":data.next_action.strip(),"owner_id":data.owner_id or user.id,"paid_at_capture":money(invoice.paid_amount)}
    event=ServiceEvent(organization_id=organization_id_for(user),module_key="srm",event_type="dashboard.payment_commitment",entity_type="invoice",entity_id=identity,actor_id=user.id,request_key="payment-promise:"+uuid4().hex,payload_json=payload,status="recorded")
    db.add(event);db.commit()
    return payload

@router.get("/{section}")
def section_data(section:Literal["summary","cash","collections","events","orders","quotations","targets"],response:Response,
    period:Literal["all","today","week","month","3","12","custom"]="month",start_date:date|None=None,end_date:date|None=None,
    owner_id:int|None=Query(None,gt=0),team_id:int|None=Query(None,gt=0),customer_id:int|None=Query(None,gt=0),branch_id:int|None=Query(None,gt=0),
    metric:str|None=Query(None,max_length=60),currency:str|None=Query(None,max_length=10),
    db:Session=Depends(get_db),user=Depends(get_current_user)):
    if section not in permitted(user):raise HTTPException(403,"This dashboard section is outside your permissions")
    response.headers["Cache-Control"]="no-store"
    ctx=business_context(db,user);today=date.fromisoformat(ctx["business_date"])
    end=today
    if period=="custom":
        if not start_date or not end_date or start_date>end_date:raise HTTPException(422,"Choose a valid inclusive custom date range")
        start,end=start_date,end_date
    elif period=="all":start=None
    elif period=="today":start=today
    elif period=="week":start=today-timedelta(days=today.weekday())
    elif period=="month":start=today.replace(day=1)
    else:
        index=today.year*12+today.month-int(period)
        start=date(index//12,index%12+1,1)
    if start and (end-start).days>3660:raise HTTPException(422,"Choose at most ten years per report")
    prior_end=start-timedelta(days=1) if start else None
    prior_start=prior_end-(end-start) if start else None
    def within(value,a=start,b=end):return bool(value and (not a or a<=value) and value<=b)
    oq,iq=sources(db,user,owner_id,team_id,customer_id,branch_id)
    orders=oq.all();all_invoices=iq.filter(SRMInvoice.status.notin_(["draft","cancelled","void"])).all()
    invoices=[i for i in all_invoices if within(i.issue_date)]
    order_map={o.id:o for o in orders};invoice_map={i.id:i for i in invoices}
    rows=[];metrics={};series=[];notes=[]
    if section=="summary":
        previous=[i for i in all_invoices if start and within(i.issue_date,prior_start,prior_end)]
        for key,get in {"invoiced":lambda i:i.total_amount,"collected":lambda i:i.paid_amount,"outstanding":lambda i:i.balance_amount,"overdue":lambda i:max(dec(i.balance_amount),ZERO) if i.due_date and i.due_date<today else ZERO}.items():
            current=groups(invoices,get);old={r['currency']:r['amount'] for r in groups(previous,get)}
            now={r['currency']:r['amount'] for r in current}
            for cur in sorted(set(now)|set(old)):
                gross=sum((dec(i.total_amount) for i in invoices if (i.currency or "Unknown")==cur),ZERO)
                series.append({"metric":key,"currency":cur,"amount":now.get(cur,"0.00"),"previous":old.get(cur,"0.00") if start else None,
                    "collection_percent":round(float(dec(now.get(cur,0))/gross*100),1) if key=="collected" and gross>0 and cur!="Unknown" else None})
        selected=[i for i in invoices if (metric!="collected" or dec(i.paid_amount)>0) and (metric not in {"outstanding","overdue"} or dec(i.balance_amount)>0 and (metric!="overdue" or i.due_date and i.due_date<today))]
        selected.sort(key=lambda i:(i.issue_date or date.min,i.id),reverse=True)
        rows=[row(i.id,i.invoice_number,f"/srm/invoices/{i.id}",currency=i.currency,total=money(i.total_amount),paid=money(i.paid_amount),balance=money(i.balance_amount),issue_date=i.issue_date,due=i.due_date,status=i.status) for i in selected]
        notes=["Invoice issue-date cohorts; collected and outstanding are current balances, not period cash flow. Previous-period balances are also current, not reconstructed historical snapshots.","Gross invoice totals and stored receivables are authoritative. Credits and write-offs already reflected in balances must not be subtracted again."]
    elif section=="cash":
        # Allocations preserve invoice authorization. Unallocated company receipts
        # cannot be safely attributed to a salesperson/team and are omitted.
        allocations=db.query(SRMReceiptAllocation,SRMReceipt).join(SRMReceipt,SRMReceipt.id==SRMReceiptAllocation.receipt_id).filter(scoped(SRMReceipt.organization_id,user),SRMReceiptAllocation.invoice_id.in_([i.id for i in all_invoices]),SRMReceipt.status=="confirmed").all()
        selected=[(a,r) for a,r in allocations if within(r.receipt_date)]
        cash=defaultdict(lambda:ZERO)
        for a,r in selected:
            inv=next(i for i in all_invoices if i.id==a.invoice_id)
            if inv.currency!=r.currency:raise HTTPException(409,"Receipt and invoice currencies disagree; reconcile before reporting")
            cash[r.currency or "Unknown"]+=dec(a.amount)
            rows.append(row(a.id,r.receipt_number,f"/srm/invoices/{a.invoice_id}",currency=r.currency,amount=money(a.amount),date=r.receipt_date,invoice_id=a.invoice_id))
        if can_view_all_srm(user) and not owner_id and not team_id:
            rq=ownership(db,db.query(SRMReceipt).filter(scoped(SRMReceipt.organization_id,user),SRMReceipt.status=="confirmed"),SRMReceipt,user,branch_id)
            if customer_id:rq=rq.filter(SRMReceipt.customer_id==customer_id)
            receipts=[r for r in rq.all() if within(r.receipt_date)]
            cash=defaultdict(lambda:ZERO);rows=[]
            for receipt in receipts:
                cash[receipt.currency or "Unknown"]+=dec(receipt.amount)
                rows.append(row(receipt.id,receipt.receipt_number,"/srm/collections",currency=receipt.currency,amount=money(receipt.amount),date=receipt.receipt_date,unallocated=money(receipt.unallocated_amount)))
            metrics['cash_basis']="Confirmed receipts, including unallocated cash"
        else:metrics['cash_basis']="Confirmed allocations to permitted invoices; unallocated cash cannot be attributed to workforce filters"
        series=[{"currency":cur,"cash_received":money(amount)} for cur,amount in sorted(cash.items())]
        refund_orders=[o.id for o in orders]
        refunds=db.query(SRMPOSReturn).filter(scoped(SRMPOSReturn.organization_id,user),SRMPOSReturn.sales_order_id.in_(refund_orders),SRMPOSReturn.status=="completed",SRMPOSReturn.refund_status=="refunded").all()
        metrics['refunds']=groups([r for r in refunds if within(day(r.created_at,ctx['timezone']))],lambda r:r.refund_amount)
        events=db.query(SRMRevenueEvent).filter(scoped(SRMRevenueEvent.organization_id,user),SRMRevenueEvent.invoice_id.in_([i.id for i in all_invoices]),SRMRevenueEvent.event_type.in_(["credit_note","credit","write_off","refund"])).all()
        metrics['adjustments']=[{"type":kind,"values":groups([e for e in events if e.event_type==kind and within(e.recognized_on)],lambda e:abs(dec(e.amount)))} for kind in sorted({e.event_type for e in events})]
        metrics['unclassified_balance_reduction']=groups(invoices,lambda i:dec(i.total_amount)-dec(i.paid_amount)-dec(i.balance_amount))
        notes=["Cash received = confirmed receipt allocations by receipt date, including payments for older invoices. Unallocated receipts are included in broad authorized views and excluded with workforce filters or restricted ownership because attribution is unavailable.","Completed POS refunds are separate cash outflows. Credit/write-off/refund events are disclosed separately; absence of typed events does not imply zero adjustments. Unclassified balance reductions reconcile gross − paid − outstanding and are not classified as cash."]
    elif section=="collections":
        promises=commitment_map(db,user,list(invoice_map));history=db.query(SRMReceiptAllocation,SRMReceipt).join(SRMReceipt,SRMReceipt.id==SRMReceiptAllocation.receipt_id).filter(SRMReceiptAllocation.invoice_id.in_([i.id for i in all_invoices]),SRMReceipt.status=="confirmed",scoped(SRMReceipt.organization_id,user)).all()
        late=Counter();attempts=Counter()
        all_map={i.id:i for i in all_invoices}
        for a,r in history:
            inv=all_map[a.invoice_id]
            if inv.due_date and r.receipt_date:
                attempts[inv.customer_id]+=1;late[inv.customer_id]+=int(r.receipt_date>inv.due_date)
        followups=db.query(FollowUp).filter(FollowUp.organization_id==organization_id_for(user),FollowUp.invoice_id.in_(list(invoice_map)),FollowUp.status.in_(["Scheduled","Pending","Overdue"])).order_by(FollowUp.due_at).all()
        actions={}
        for f in followups:actions.setdefault(f.invoice_id,f)
        exposure=defaultdict(lambda:ZERO)
        for invoice in invoices:exposure[invoice.currency or 'Unknown']+=max(dec(invoice.balance_amount),ZERO)
        forecast=defaultdict(lambda:{"promised":ZERO,"scenario":ZERO,"base":ZERO,"count":0})
        aging=defaultdict(lambda:defaultdict(lambda:ZERO))
        owner_ids=set()
        for i in invoices:
            balance=dec(i.balance_amount)
            if balance<=0:continue
            days=max((today-i.due_date).days,0) if i.due_date else 0
            bucket="No due date" if not i.due_date else "Current" if i.due_date>=today else "1–30" if days<=30 else "31–60" if days<=60 else "61–90" if days<=90 else "90+"
            cur=i.currency or "Unknown";aging[cur][bucket]+=balance
            promise=promises.get(i.id,{});remaining=max(ZERO,dec(promise.get('amount'))-max(ZERO,dec(i.paid_amount)-dec(promise.get('paid_at_capture'))))
            promised=date.fromisoformat(promise['promised_date']) if promise else None
            broken=bool(promised and promised<today and remaining>0)
            owner=promise.get('owner_id') or (order_map.get(i.sales_order_id).assigned_user_id if i.sales_order_id in order_map else i.created_by)
            if owner:owner_ids.add(owner)
            f=actions.get(i.id);bad_rate=late[i.customer_id]/attempts[i.customer_id] if attempts[i.customer_id] else None
            risk=days*2+(30*bad_rate if bad_rate is not None else 0)+(50 if broken else 0)+float(20*balance/exposure[cur])
            rows.append(row(i.id,i.invoice_number,f"/srm/invoices/{i.id}",currency=cur,total=money(i.total_amount),paid=money(i.paid_amount),balance=money(balance),due=i.due_date,overdue_days=days,aging=bucket,owner_id=owner,next_action=promise.get('next_action') or (f.title if f else "Not scheduled"),promised_date=promised,promised_amount=money(remaining),broken_promise=broken,risk_score=round(risk,1),late_payment_rate=round(100*bad_rate,1) if bad_rate is not None else None,collection_hold=i.collection_hold))
            predicted=forecast[cur];predicted['base']+=balance;predicted['count']+=1
            committed=min(remaining,balance) if promised and today<=promised<=today+timedelta(days=30) and not i.collection_hold else ZERO
            predicted['promised']+=committed
            probability=dec(1-bad_rate) if attempts[i.customer_id]>=3 else Decimal('.5')
            predicted['scenario']+=ZERO if i.collection_hold else committed+((balance-committed)*probability if i.due_date and i.due_date<=today+timedelta(days=30) else ZERO)
        names={u.id:u.email for u in db.query(User).filter(User.id.in_(owner_ids)).all()}
        for r in rows:r['owner']=names.get(r['owner_id'],'Unassigned')
        rows.sort(key=lambda r:(r['currency'],-r['risk_score'],-dec(r['balance'])))
        series=[{"currency":cur,"bucket":bucket,"amount":money(value)} for cur,buckets in sorted(aging.items()) for bucket,value in buckets.items()]
        metrics['forecast']=[{"currency":cur,**{k:money(value) if k!='count' else value for k,value in values.items()},"confidence":"Scenario only — limited evidence" if len(history)<5 else "Historical heuristic — not a probability interval"} for cur,values in sorted(forecast.items())]
        notes=["Current balances for invoices issued in the selected period. Risk score = 2 × overdue days + 30 × historical late-allocation rate + 50 for a broken promise; amounts never rank different currencies against one another.","30-day scenario assumes all in-window payment promises and a residual recovery rate based on at least three historical allocations per customer; otherwise 50%. Residual balances due after the horizon or without a due date contribute zero. Holds contribute zero. Promises are not guarantees. Confidence labels describe evidence, not statistical calibration."]
    elif section=="events":
        events=db.query(SRMRevenueEvent).filter(scoped(SRMRevenueEvent.organization_id,user),SRMRevenueEvent.invoice_id.in_([i.id for i in all_invoices])).all()
        series=[{"date":e.recognized_on,"currency":e.currency or "Unknown","event_type":e.event_type,"amount":money(e.amount)} for e in events if within(e.recognized_on)]
        notes=["Commercial events are separated by type and currency; they are not summed into accounting revenue. Only events linked to authorized invoices are included."]
    elif section=="orders":
        selected=sorted([o for o in orders if within(day(o.created_at,ctx['timezone']))],key=lambda o:(day(o.created_at,ctx['timezone']) or date.min,o.id),reverse=True)
        stage_events=db.query(ServiceEvent).filter_by(organization_id=organization_id_for(user),module_key="srm",event_type="pipeline.stage_entered",entity_type="sales_order").filter(ServiceEvent.entity_id.in_([o.id for o in selected])).order_by(ServiceEvent.id).all()
        stage_entries={event.entity_id:event for event in stage_events}
        balances={}
        for balance in db.query(SRMInventoryBalance).filter(scoped(SRMInventoryBalance.organization_id,user)).all():balances[balance.product_id]=balances.get(balance.product_id,ZERO)+dec(balance.quantity)
        products={p.id:p for p in db.query(SRMProduct).filter(scoped(SRMProduct.organization_id,user)).all()}
        for o in selected:
            age=max((today-day(o.updated_at or o.created_at,ctx['timezone'])).days,0)
            blockers=[];status=(o.status or '').lower();meta=o.metadata_json or {}
            entry=stage_entries.get(o.id)
            stage_age=max((today-day(entry.created_at,ctx['timezone'])).days,0) if entry and entry.payload_json.get('data',{}).get('stage')==o.status else None
            if stage_age is not None and stage_age>=14 and status not in {'closed','cancelled','completed','delivered'}:blockers.append(f'In current status for {stage_age} days')
            if status=='pending_approval':blockers.append('Pending approval')
            if meta.get('credit_hold') is True:blockers.append('Recorded credit hold')
            if status not in {'closed','cancelled','completed','delivered'}:
                for line in o.lines:
                    product=products.get(line.product_id)
                    if product and product.product_type=='stock' and product.track_inventory and product.id not in balances:blockers.append(f'Stock availability not verified: {product.sku}')
                    elif product and product.product_type=='stock' and product.track_inventory and dec(line.quantity)>balances.get(product.id,ZERO):blockers.append(f"Stock shortfall: {product.sku} (on hand {balances.get(product.id,ZERO)}, ordered {line.quantity})")
            if age>=14 and status not in {'closed','cancelled','completed'}:blockers.append(f"No update for {age} days")
            if o.expected_end_date and o.expected_end_date<today and status not in {'closed','cancelled','completed','delivered'}:blockers.append('Delivery date passed')
            invoiced=sum((dec(i.total_amount) for i in all_invoices if i.sales_order_id==o.id and i.currency==o.currency),ZERO)
            unbilled=max(ZERO,dec(o.total_amount)-invoiced) if status in {'delivered','completed','closed'} else ZERO
            if unbilled: blockers.append('Delivered/completed value not fully invoiced')
            rows.append(row(o.id,o.order_number,f"/srm/sales-orders/{o.id}",currency=o.currency,amount=money(o.total_amount),status=o.status,last_updated=day(o.updated_at or o.created_at,ctx['timezone']),inactive_days=age,stage_age_days=stage_age,expected_delivery=o.expected_end_date,blockers=blockers,unbilled=money(unbilled)))
        series=[{"status":key,"count":value} for key,value in sorted(Counter(o.status for o in selected).items())]
        notes=["Stage age uses the latest recorded status-entry event when its destination matches the current status. Otherwise stage age is unknown; a separate signal flags no update for 14 days. Delivery uses the recorded expected end date.","Stock signals compare ordered quantity with permitted on-hand stock; reservations and committed availability are not inferred. Unbilled value compares completed order value with linked non-cancelled invoices in the same currency; it is a review signal, not recognized revenue."]
    else:
        # CRM's own ownership rules apply in addition to tenant/branch boundaries.
        from app.apps.crm.api.router import _apply_record_visibility, _get_resource
        if section=='quotations':
            query=_apply_record_visibility(db.query(CRMQuotation).filter(scoped(CRMQuotation.organization_id,user)),_get_resource('quotations'),user,db)
            if owner_id:query=query.filter(CRMQuotation.owner_user_id==owner_id)
            if team_id:query=query.filter(CRMQuotation.assigned_team_id==team_id)
            if customer_id:query=query.filter(CRMQuotation.company_id==customer_id)
            if branch_id:query=query.filter(CRMQuotation.branch_id==branch_id)
            quotes=[q for q in query.all() if within(q.issue_date) and (q.status or '').lower() not in {'draft','cancelled','void'}]
            converted={o.crm_quote_id for o in orders if o.crm_quote_id and o.status!='cancelled'}
            metrics={'issued':len(quotes),'converted':sum(q.id in converted for q in quotes),'conversion_rate':round(100*sum(q.id in converted for q in quotes)/len(quotes),1) if quotes else None}
            rows=[row(q.id,q.quote_number,f"/crm/quotations?record={q.id}",currency=q.currency,amount=money(q.total_amount),status=q.status,expiry=q.valid_until or q.expiry_date,expiring=bool(q.id not in converted and (q.status or "").lower() not in {"accepted","converted","cancelled","rejected","expired"} and today<=(q.valid_until or q.expiry_date)<=today+timedelta(days=7)),converted=q.id in converted) for q in quotes]
            notes=['Conversion = quotations in the selected issue-date cohort linked to a visible non-cancelled sales order. Unseen orders are not assumed converted. Expiry alerts cover the next seven days.']
        else:
            targets=_apply_record_visibility(db.query(CRMSalesTarget).filter(scoped(CRMSalesTarget.organization_id,user),CRMSalesTarget.deleted_at.is_(None)),_get_resource('sales-targets'),user,db).all()
            team_map={a.sales_order_id:a.team_id for a in db.query(SalesTeamAssignment).filter(SalesTeamAssignment.sales_order_id.in_(list(order_map))).all()}
            for t in targets:
                if start and (t.period_end<start or t.period_start>end):continue
                if owner_id and (t.target_owner_type!='user' or t.target_owner_id!=owner_id):continue
                if team_id and (t.target_owner_type!='team' or t.target_owner_id!=team_id):continue
                # Filtered customer/branch views must not compare a subset to a full target.
                if customer_id or branch_id:continue
                matched=[o for o in orders if o.currency==t.currency and t.period_start<=day(o.created_at,ctx['timezone'])<=t.period_end and o.status in {'confirmed','delivery_in_progress','delivered','completed','closed'} and (o.assigned_user_id==t.target_owner_id if t.target_owner_type=='user' else team_map.get(o.id)==t.target_owner_id if t.target_owner_type=='team' else False)]
                achieved=sum((dec(o.total_amount) for o in matched),ZERO)
                rows.append(row(t.id,f"{t.target_owner_type} #{t.target_owner_id}","/crm/targets",currency=t.currency,target=money(t.target_amount),achieved=money(achieved),attainment=round(float(achieved/dec(t.target_amount)*100),1) if dec(t.target_amount)>0 else None,from_date=t.period_start,to_date=t.period_end))
            notes=['Target attainment uses confirmed/delivery/completed order value over each target’s full period and visible owner/team scope. It does not claim to match a differently defined CRM revenue target. Customer/branch-filtered subsets omit full targets.']
    if currency:rows=[r for r in rows if r.get('currency')==currency]
    total=len(rows)
    return {'section':section,'context':{**ctx,'start_date':start,'end_date':end,'previous_start':prior_start,'previous_end':prior_end},'metrics':metrics,'series':series,'rows':rows[:250],'total_rows':total,'notes':notes}
