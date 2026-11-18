"""Bounded, authorized waitlist and atomic recurring prebookings; no billing."""
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from app.core.deps import get_db, get_current_user
from app.apps.srm.industry_api import (BaseInput, Strict, AppointmentInput, context, query, get, out, create,
    existing, revision, save, available, appointment_operation, require_pack_operation, for_record_read)
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.services.commercial import customer, lock_tenant
from app.apps.srm.service_checkout_options import service_options, validate_prebooking

router=APIRouter(prefix='/srm/industry/prebooking-workflows',tags=['Shared prebooking workflows'])

class WaitlistInput(BaseInput):
    customer_id:int=Field(gt=0)
    service_id:int=Field(gt=0)
    from_date:date
    until_date:date
    timezone:str
    window_from:time=time(9)
    window_until:time=time(17)
    employee_id:int|None=Field(None,gt=0)
    resource_ids:list[int]=Field(default_factory=list,max_length=9)
    flexible_employee:bool=True
    flexible_resources:bool=True
    notes:str=Field(default='',max_length=1000)
    @model_validator(mode='after')
    def valid(self):
        try:zone=ZoneInfo(self.timezone)
        except Exception:raise ValueError('Choose a valid waitlist timezone')
        today=datetime.now(zone).date()
        if not today<=self.from_date<=self.until_date<=today+timedelta(days=90):raise ValueError('Choose a waitlist range within the next 90 days')
        if self.window_from.utcoffset() is not None or self.window_until.utcoffset() is not None or self.window_until<=self.window_from:raise ValueError('Choose a local time window with end after start')
        if not self.flexible_employee and not self.employee_id:raise ValueError('Choose an employee or allow any qualified employee')
        if len(set(self.resource_ids))!=len(self.resource_ids):raise ValueError('Select each resource once')
        return self

class SeriesInput(BaseInput):
    base:AppointmentInput
    starts_at:list[datetime]=Field(min_length=1,max_length=12)
    included:list[int]|None=Field(None,min_length=1,max_length=12)
    @model_validator(mode='after')
    def valid(self):
        if self.base.booking is None:raise ValueError('A recurring booking needs an authoritative service selection')
        if any(at.utcoffset() is None for at in self.starts_at):raise ValueError('Every occurrence needs a timezone offset')
        if self.starts_at!=sorted(set(self.starts_at)):raise ValueError('Occurrence starts must be unique and ascending')
        now=datetime.now(timezone.utc)
        if any(not now<at<=now+timedelta(days=90) for at in self.starts_at):raise ValueError('Occurrences must be in the next 90 days')
        if any(b<a+timedelta(minutes=self.base.duration_minutes) for a,b in zip(self.starts_at,self.starts_at[1:])):raise ValueError('Occurrences cannot overlap each other')
        if self.included is not None and (len(set(self.included))!=len(self.included) or any(i<0 or i>=len(self.starts_at) for i in self.included)):raise ValueError('Choose valid occurrence indices')
        return self

class ExpectedRevision(Strict):
    expected_revision:int=Field(ge=1)

def authority(db,actor,write=False):
    branch=context(db,actor,write,appointments=True)
    if write:require_pack_operation(db,actor,'appointments.schedule','reservations.schedule')
    else:for_record_read(db,actor,'appointment')
    return branch

def own(db,actor,branch,ident,kind):
    row=get(db,actor,branch,ident,kind)
    if row.created_by!=actor.id:raise HTTPException(404,'Prebooking workflow not found')
    return row

def series_result(db,actor,branch,row):
    return {'id':row.id,'state':'confirmed','appointments':[out(get(db,actor,branch,i,'appointment',lock=False),db,actor) for i in row.data['appointment_ids']]}

def occurrence(data,index):
    at=data.starts_at[index]
    item=data.base.model_copy(deep=True)
    item.request_id=uuid5(data.request_id,f'occurrence:{index}')
    item.starts_at=at
    item.booking.starts_at=at
    return item

def preview_series(data,db,actor):
    branch=authority(db,actor,True)
    results=[]
    for index,at in enumerate(data.starts_at):
        item=occurrence(data,index)
        try:
            validate_prebooking(db,actor,item)
            available(db,actor,branch,at,item.duration_minutes,item.resource_ids,lock=False)
            results.append({'index':index,'starts_at':at,'available':True})
        except HTTPException as error:
            if error.status_code not in (409,422):raise
            results.append({'index':index,'starts_at':at,'available':False,'reason':str(error.detail)})
    return {'occurrences':results,'checked_at':datetime.now(timezone.utc),'notice':'Preview only. Selected occurrences are revalidated and reserved atomically on confirmation.'}

def commit_series(data,db,actor):
    branch=authority(db,actor,True)
    lock_tenant(db,actor)
    prior=existing(db,actor,branch,data,'prebooking_series')
    if prior:
        if prior.created_by!=actor.id:raise HTTPException(404,'Prebooking workflow not found')
        return series_result(db,actor,branch,prior)
    indices=data.included if data.included is not None else list(range(len(data.starts_at)))
    try:
        for i in indices:
            item=occurrence(data,i)
            validate_prebooking(db,actor,item)
            available(db,actor,branch,item.starts_at,item.duration_minutes,item.resource_ids)
        children=[appointment_operation(occurrence(data,i),db,actor,commit=False)['id'] for i in indices]
        parent=create(db,actor,branch,'prebooking_series',data,record_data={'appointment_ids':children},customer_id=data.base.customer_id)
        parent.status='confirmed'
        db.commit()
        return series_result(db,actor,branch,parent)
    except Exception:
        db.rollback()
        raise

def save_waitlist(data,db,actor):
    branch=authority(db,actor,True)
    lock_tenant(db,actor)
    prior=existing(db,actor,branch,data,'prebooking_waitlist')
    if prior:
        if prior.created_by!=actor.id:raise HTTPException(404,'Prebooking workflow not found')
        return out(prior,db,actor)
    buyer=customer(db,data.customer_id,actor)
    options=service_options(db,actor,data.service_id,employee_id=data.employee_id)
    if not options['policy'] or not options['policy']['active']:raise HTTPException(409,'Choose an actively scheduled service')
    if data.employee_id and not options['specialists']:raise HTTPException(422,'Choose a currently qualified employee')
    resources=options['resources']
    if not set(data.resource_ids)<={r['id'] for r in resources}:raise HTTPException(422,'Choose current resources in this branch')
    required=set(options['policy'].get('required_resource_types') or [])
    if not data.flexible_resources and required-{r['resource_type'] for r in resources if r['id'] in data.resource_ids}:raise HTTPException(422,'Choose required resources or allow alternatives')
    row=create(db,actor,branch,'prebooking_waitlist',data,record_data={'customer_name':buyer.name,'service_name':options['service']['name']},customer_id=data.customer_id)
    row.status='waiting'
    db.commit()
    return out(row,db,actor)

@router.post('/waitlist',status_code=201)
def waitlist(data:WaitlistInput,db=Depends(get_db),actor=Depends(get_current_user)):
    return save_waitlist(data,db,actor)

@router.get('/waitlist')
def waitlist_entries(db=Depends(get_db),actor=Depends(get_current_user)):
    branch=authority(db,actor)
    rows=query(db,actor,branch).filter_by(kind='prebooking_waitlist',created_by=actor.id,status='waiting').order_by(IndustryRecord.id.desc()).limit(20).all()
    return {'items':[out(row,db,actor) for row in rows],'limit':20}

@router.post('/waitlist/{ident}/cancel')
def cancel_waitlist(ident:int,data:ExpectedRevision,db=Depends(get_db),actor=Depends(get_current_user)):
    branch=authority(db,actor,True)
    row=own(db,actor,branch,ident,'prebooking_waitlist')
    revision(row,data.expected_revision)
    if row.status!='waiting':raise HTTPException(409,'Waitlist entry is no longer waiting')
    row.status='cancelled'
    return save(db,actor,row,'waitlist_cancelled')

@router.post('/series/preview')
def series_preview(data:SeriesInput,db=Depends(get_db),actor=Depends(get_current_user)):
    return preview_series(data,db,actor)

@router.post('/series',status_code=201)
def series_commit(data:SeriesInput,db=Depends(get_db),actor=Depends(get_current_user)):
    return commit_series(data,db,actor)

@router.get('/requests/{request_id}')
def workflow_request_status(request_id:UUID,db=Depends(get_db),actor=Depends(get_current_user)):
    branch=authority(db,actor)
    row=query(db,actor,branch).filter_by(request_id=str(request_id),created_by=actor.id).first()
    if not row or row.kind not in ('prebooking_waitlist','prebooking_series'):return {'state':'not_found'}
    return {'state':'confirmed','result':series_result(db,actor,branch,row) if row.kind=='prebooking_series' else out(row,db,actor)}

@router.get('/appointments/{ident}/summary')
def appointment_summary(ident:int,db=Depends(get_db),actor=Depends(get_current_user)):
    branch=authority(db,actor)
    row=get(db,actor,branch,ident,'appointment',lock=False)
    from app.apps.srm.industry_api import PROVIDER_TYPES
    resources=[get(db,actor,branch,i,'resource',lock=False) for i in row.data.get('resource_ids',[])]
    provider=next((r for r in resources if r.data.get('resource_type') in PROVIDER_TYPES),None)
    return {'row':out(row,db,actor),'employee_id':provider.data.get('employee_id') if provider else None,'provider_resource_id':provider.id if provider else None,'employee':provider.title if provider else 'Provider unavailable','timezone':provider.data.get('timezone','UTC') if provider else 'UTC','resources':[r.title for r in resources if r is not provider]}


@router.get('/eligibility/{service_id}/{employee_id}')
def eligibility_explanation(service_id:int,employee_id:int,db=Depends(get_db),actor=Depends(get_current_user)):
    branch=authority(db,actor)
    require_pack_operation(db,actor,'providers.manage','settings.manage')
    from app.apps.srm.industry_api import require, Record
    from app.apps.srm.service_checkout_models import ServiceSpecialistEligibility
    require(actor,'srm_manage','srm_admin')
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.apps.srm.services.commercial import tenant
    employee=db.query(Employee).join(Branch,Employee.branch_id==Branch.id).filter(Branch.company_id==tenant(actor),Branch.id==branch,Employee.id==employee_id,Employee.deleted_at.is_(None)).first()
    if not employee:raise HTTPException(404,'Permitted employee not found')
    options=service_options(db,actor,service_id,employee_id=employee_id)
    reasons=[]
    if employee.status not in ('Active','Probation','On Leave'):reasons.append('Employee status is not active for scheduling.')
    if employee.date_of_exit and employee.date_of_exit<=date.today():reasons.append('The employee exit date has been reached.')
    resources=query(db,actor,branch).filter(Record.kind=='resource',Record.data['employee_id'].as_integer()==employee_id).all()
    if not resources:reasons.append('No permitted provider resource is linked to this employee.')
    elif not any(r.status=='active' for r in resources):reasons.append('The linked provider resource is inactive.')
    policy=options['policy']
    if not policy or not policy['active']:reasons.append('The service scheduling policy is missing or inactive.')
    else:
        wanted={str(c).strip().casefold() for c in policy.get('employee_categories',[])}
        actual={str(c).strip().casefold() for c in employee.work_categories or []}
        if wanted and not wanted.intersection(actual):reasons.append('Employee categories do not match this service.')
        eligible=db.query(ServiceSpecialistEligibility).filter(ServiceSpecialistEligibility.booking_policy_id==policy['id'],ServiceSpecialistEligibility.provider_resource_id.in_([r.id for r in resources])).all() if resources else []
        if resources and not eligible:reasons.append('No service assignment exists for the linked provider.')
        elif eligible and not any(e.active for e in eligible):reasons.append('The service assignment is inactive.')
    if not options['specialists'] and not reasons:reasons.append('Eligibility effective dates or another service rule currently excludes this employee.')
    return {'employee_id':employee_id,'eligible':bool(options['specialists']),'reasons':reasons,'notice':'Only records permitted in the current branch and Business Pack were inspected.'}
