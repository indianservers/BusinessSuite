"""Recurring purchase drafts reuse native FAM creation and the shared cadence helper."""
from datetime import date, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.shared.models import ServicePolicy
from app.apps.fam.access import FAM_PURCHASE_MANAGE_PERMISSIONS, FAM_EXPENSE_MANAGE_PERMISSIONS, FAM_PURCHASE_VIEW_PERMISSIONS, FAM_EXPENSE_VIEW_PERMISSIONS
from app.apps.srm.access import has_any_permission
from app.apps.srm.services.recurrence import occurrence_dates, business_date

router=APIRouter(prefix='/recurring-purchases',tags=['Recurring purchase drafts'])
MANAGE=FAM_PURCHASE_MANAGE_PERMISSIONS|FAM_EXPENSE_MANAGE_PERMISSIONS
VIEW=FAM_PURCHASE_VIEW_PERMISSIONS|FAM_EXPENSE_VIEW_PERMISSIONS


class Schedule(BaseModel):
    kind: Literal['bill','expense']
    source_id: int = Field(gt=0)
    name: str = Field(min_length=1,max_length=150)
    start_date: date
    rule: Literal['daily','weekly','monthly','quarterly','yearly'] = 'monthly'
    interval: int = Field(default=1,ge=1,le=120)
    occurrences: int = Field(default=12,ge=1,le=120)
    never_expires: bool = False
    end_date: date|None = None
    payment_terms_days: int = Field(default=30,ge=0,le=365)
    @model_validator(mode='after')
    def dates(self):
        if self.end_date and (self.end_date<self.start_date or self.never_expires):
            raise ValueError('Choose a valid end date or never expires')
        return self


class StateChange(BaseModel):
    status: Literal['active','paused','completed']
    expected_version: int = Field(ge=1)


def permissions(kind, write=False):
    return (FAM_PURCHASE_MANAGE_PERMISSIONS if write else FAM_PURCHASE_VIEW_PERMISSIONS) if kind=='bill' else (FAM_EXPENSE_MANAGE_PERMISSIONS if write else FAM_EXPENSE_VIEW_PERMISSIONS)


def branch_id(db):
    context=db.info.get('branch_context')
    return context.branch_id if context else None


def visible(db, user):
    from app.apps.fam.api.router import company_id_for
    company=company_id_for(user)
    rows=db.query(ServicePolicy).filter_by(organization_id=company,module_key='fam',kind='recurring_purchase').order_by(ServicePolicy.id).all()
    branch=branch_id(db)
    return [r for r in rows if (branch is None or r.values_json.get('branch_id')==branch) and has_any_permission(user,permissions(r.values_json['kind']))]


def payload(row):
    return {'id':row.id,'version':row.version,**{k:v for k,v in row.values_json.items() if k!='template'}}


def validate_accounts(db, company, template):
    from app.apps.fam.models import FAMLedger,FAMParty,FAMStockItem,FAMTDSSection
    if template.get('vendor_id') and not db.query(FAMParty).filter_by(company_id=company,id=template['vendor_id'],active=True).first():
        raise HTTPException(422,'The source vendor is unavailable')
    identifiers=[line['expense_ledger_id'] for line in template['lines']]
    if template.get('payable_ledger_id'): identifiers.append(template['payable_ledger_id'])
    for ident in set(identifiers):
        if not db.query(FAMLedger).filter_by(company_id=company,id=ident,active=True).first():
            raise HTTPException(422,'A recurring purchase account is unavailable in this company')
    for line in template['lines']:
        for key,model in [('item_id',FAMStockItem),('tds_section_id',FAMTDSSection)]:
            if line.get(key) and not db.query(model).filter_by(company_id=company,id=line[key],active=True).first():
                raise HTTPException(422,'A recurring purchase reference is unavailable in this company')


@router.get('')
def profiles(db:Session=Depends(get_db),user=Depends(RequirePermission(*VIEW))):
    return [payload(row) for row in visible(db,user)]


@router.post('',status_code=201)
def create_schedule(data:Schedule,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*MANAGE))):
    from app.apps.fam.api.router import bootstrap,audit
    from app.apps.fam.models import FAMPurchaseBill,FAMPurchaseBillLine,FAMExpenseClaim,FAMExpenseLine,FAMCompanyFinancialSettings
    from app.apps.fam.schemas import PurchaseBillPayload,PurchaseBillLinePayload,ExpenseClaimPayload,ExpenseLinePayload
    if not has_any_permission(user,permissions(data.kind,True)):
        raise HTTPException(403,'Manage permission is required for the selected purchase type')
    company=bootstrap(db,user)
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db,user)
    branch=branch_id(db)
    if branch is None:
        raise HTTPException(422,'Select a branch for the recurring schedule')
    model,line_model,foreign,schema,line_schema=(FAMPurchaseBill,FAMPurchaseBillLine,'purchase_bill_id',PurchaseBillPayload,PurchaseBillLinePayload) if data.kind=='bill' else (FAMExpenseClaim,FAMExpenseLine,'expense_claim_id',ExpenseClaimPayload,ExpenseLinePayload)
    source=db.query(model).filter_by(company_id=company,id=data.source_id).first()
    if not source or source.status=='cancelled':
        raise HTTPException(404,'An available source document is required')
    lines=db.query(line_model).filter(getattr(line_model,foreign)==source.id).all()
    if not lines:
        raise HTTPException(422,'Add source document lines before scheduling')
    body={key:getattr(source,key) for key in schema.model_fields if key!='lines' and hasattr(source,key)}
    body['lines']=[{key:getattr(line,key) for key in line_schema.model_fields if hasattr(line,key)} for line in lines]
    template=schema.model_validate(body).model_dump(mode='json')
    validate_accounts(db,company,template)
    key=f'fam-recurring:{company}:{branch}:{data.kind}:{source.id}'
    if db.query(ServicePolicy).filter_by(scope_key=key,organization_id=company).first():
        raise HTTPException(409,'This source document already has a recurring schedule; reuse its existing profile')
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=company).one()
    values={**data.model_dump(mode='json'),'branch_id':branch,'template':template,'status':'active','next_index':0,'history':[],
            'currency':settings.base_currency,'country':settings.country_code}
    row=ServicePolicy(scope_key=key,organization_id=company,module_key='fam',kind='recurring_purchase',values_json=values,updated_by=user.id)
    db.add(row);db.flush();audit(db,request,user,company,'recurring_purchase',row.id,'CREATE',None,payload(row));db.commit()
    return payload(row)


@router.put('/{ident}/status')
def change_status(ident:int,data:StateChange,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*MANAGE))):
    from app.apps.fam.api.router import audit
    row=next((r for r in visible(db,user) if r.id==ident),None)
    if not row: raise HTTPException(404,'Recurring purchase schedule not found')
    if not has_any_permission(user,permissions(row.values_json['kind'],True)): raise HTTPException(403,'Manage permission required')
    db.refresh(row,with_for_update=True)
    if row.version!=data.expected_version: raise HTTPException(409,'Schedule changed; refresh before updating')
    if row.values_json['status']=='completed': raise HTTPException(409,'Completed schedules cannot be restarted')
    before=row.values_json
    row.values_json={**before,'status':data.status};row.version+=1;row.updated_by=user.id
    audit(db,request,user,row.organization_id,'recurring_purchase',row.id,'STATUS',before,payload(row));db.commit()
    return payload(row)


def process_profile(db,ident,user):
    from app.apps.fam.api.router import create_purchase_bill,create_expense,company_id_for
    from app.apps.fam.models import FAMPurchaseBill,FAMExpenseClaim,FAMCompanyFinancialSettings
    from app.apps.fam.schemas import PurchaseBillPayload,ExpenseClaimPayload
    from app.apps.srm.services.commercial import lock_tenant
    from app.shared.form_defaults import effective
    lock_tenant(db,user)
    company=company_id_for(user)
    row=db.query(ServicePolicy).filter_by(id=ident,organization_id=company,kind='recurring_purchase').with_for_update().populate_existing().first()
    if not row or row.values_json['status']!='active': return 0
    values=dict(row.values_json)
    if branch_id(db)!=values['branch_id'] or not has_any_permission(user,permissions(values['kind'],True)):
        raise HTTPException(403,'The scheduling user no longer has access to this purchase workflow')
    settings=db.query(FAMCompanyFinancialSettings).filter_by(company_id=company).one()
    if settings.base_currency!=values['currency'] or settings.country_code!=values['country']:
        raise HTTPException(409,'Review recurring purchases after changing company currency or tax country')
    validate_accounts(db,company,values['template'])
    values.pop('last_error',None)
    today=business_date(effective(db,company,'fam',values['branch_id'])['values']['timezone'])
    created=0
    # Native creators flush into this transaction; the draft and cursor commit together.
    db.info['fam_recurring_transaction']=True
    try:
        for _ in range(100):
            index=values['next_index']
            due=occurrence_dates(date.fromisoformat(values['start_date']),1,values['rule'],offset=index,interval=values['interval'])[0]
            if (not values['never_expires'] and index>=values['occurrences']) or (values['end_date'] and due>date.fromisoformat(values['end_date'])):
                values['status']='completed';break
            if due>today: break
            number=f'REC-{row.id}-{index+1}'
            body=dict(values['template'])
            if values['kind']=='bill':
                existing=db.query(FAMPurchaseBill).filter_by(company_id=company,bill_number=number,vendor_id=body['vendor_id']).first()
                if existing: raise HTTPException(409,'Recurring bill reference already exists; review the conflicting document')
                body.update(bill_number=number,bill_date=due,due_date=due+timedelta(days=values['payment_terms_days']))
                result=create_purchase_bill(PurchaseBillPayload.model_validate(body),Request({'type':'http','headers':[]}),db,user)
            else:
                if db.query(FAMExpenseClaim).filter_by(company_id=company,claim_number=number).first():
                    raise HTTPException(409,'Recurring expense reference already exists; review the conflicting document')
                body.update(claim_number=number,claim_date=due)
                result=create_expense(ExpenseClaimPayload.model_validate(body),Request({'type':'http','headers':[]}),db,user)
            values['history']=[*values['history'],{'date':due.isoformat(),'record_id':result['id'],'number':number}][-100:]
            values['next_index']=index+1;created+=1
        if values != row.values_json:
            from app.apps.fam.api.router import audit
            audit(db,Request({'type':'http','headers':[]}),user,company,'recurring_purchase',row.id,'GENERATE_DRAFTS',
                  {'next_index':row.values_json['next_index']},{'next_index':values['next_index'],'created':created,'status':values['status']})
            row.values_json=values;row.version+=1
        db.commit()
        return created
    finally:
        db.info.pop('fam_recurring_transaction',None)


def dispatch_due(db):
    import logging
    from types import SimpleNamespace
    from app.models.user import User
    from app.access.service import activate_run_context,release_run_context,background_scope
    rows=db.query(ServicePolicy.id,ServicePolicy.updated_by,ServicePolicy.organization_id,ServicePolicy.values_json).filter_by(module_key='fam',kind='recurring_purchase').all()
    created=failed=0
    for ident,owner,company,values in rows:
        if values['status']!='active': continue
        user=db.get(User,owner)
        if not user or not user.is_active: continue
        try:
            activate_run_context(db,user,SimpleNamespace(scope_key=f'company:{company}'))
            with background_scope(db,user,'fam','create',branch_id=values['branch_id']):
                created+=process_profile(db,ident,user)
        except Exception as error:
            db.rollback();failed+=1;logging.getLogger(__name__).exception('Recurring purchase draft failed')
            current=db.query(ServicePolicy).filter_by(id=ident,organization_id=company,kind='recurring_purchase').with_for_update().first()
            if current:
                message=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,str) else 'Draft generation failed; review this schedule and retry.'
                if current.values_json.get('last_error')!=message:
                    current.values_json={**current.values_json,'last_error':message};current.version+=1
                db.commit()
        finally: release_run_context(db)
    return {'created':created,'failed_profiles':failed}
