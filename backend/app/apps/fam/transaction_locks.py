"""Module/date locks complement existing financial-year and accounting-period locks."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, RequirePermission
from app.apps.fam.access import FAM_VIEW_PERMISSIONS, FAM_SETTINGS_PERMISSIONS
from app.shared.models import ServicePolicy

router=APIRouter(prefix='/transaction-locks',tags=['Accounting transaction locks'])
MODULES=('all','sales','purchases','banking','accountant')
Module=Literal['all','sales','purchases','banking','accountant']

def accounting_module(category):
    if category in {'sales','credit_note'}: return 'sales'
    if category in {'purchase','debit_note'}: return 'purchases'
    if category in {'receipt','payment','contra'}: return 'banking'
    return 'accountant'

def check_lock(db,company_id,category,transaction_date):
    module=accounting_module(category)
    keys=[f'fam-lock:{company_id}:{part}' for part in ('all',module)]
    policies=db.query(ServicePolicy).filter(ServicePolicy.organization_id==company_id,ServicePolicy.kind=='transaction_lock',ServicePolicy.scope_key.in_(keys)).all()
    for row in policies:
        through=(row.values_json or {}).get('locked_through')
        if through:
            try: locked=date.fromisoformat(through)
            except (ValueError,TypeError): raise HTTPException(409,'Accounting transaction lock configuration needs correction')
            if transaction_date <= locked:
                raise HTTPException(409,f'{module.title()} accounting transactions are locked through {locked.isoformat()}')

def check_existing(db,company_id,voucher):
    from app.apps.fam.models import FAMVoucherType
    from app.apps.fam.api.router import find_financial_year_for_date,find_period_for_date
    fy=find_financial_year_for_date(db,company_id,voucher.voucher_date)
    find_period_for_date(db,fy,voucher.voucher_date)
    kind=db.query(FAMVoucherType).filter_by(company_id=company_id,id=voucher.voucher_type_id).first()
    if not kind: raise HTTPException(409,'Voucher type is unavailable')
    check_lock(db,company_id,kind.category,voucher.voucher_date)

class LockInput(BaseModel):
    locked_through: date | None = None
    reason: str = Field(min_length=1,max_length=1000)
    expected_version: int = Field(ge=0)

@router.get('')
def list_locks(db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_VIEW_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap
    company_id=bootstrap(db,user)
    rows={r.scope_key.rsplit(':',1)[-1]:r for r in db.query(ServicePolicy).filter_by(organization_id=company_id,module_key='fam',kind='transaction_lock').all()}
    return [{'module':part,'locked_through':(rows[part].values_json or {}).get('locked_through') if part in rows else None,'reason':(rows[part].values_json or {}).get('reason','') if part in rows else '', 'version':rows[part].version if part in rows else 0} for part in MODULES]

@router.put('/{module}')
def save_lock(module:Module,data:LockInput,request:Request,db:Session=Depends(get_db),user=Depends(RequirePermission(*FAM_SETTINGS_PERMISSIONS))):
    from app.apps.fam.api.router import bootstrap,audit
    if not data.reason.strip(): raise HTTPException(422,'A reason is required when changing transaction locks')
    company_id=bootstrap(db,user)
    key=f'fam-lock:{company_id}:{module}'
    row=db.query(ServicePolicy).filter_by(scope_key=key,organization_id=company_id).with_for_update().first()
    if data.expected_version != (row.version if row else 0):
        raise HTTPException(409,'Transaction locks changed. Refresh and review the current lock before saving')
    before=row.values_json if row else None
    values=data.model_dump(mode='json',exclude={'expected_version'})
    values['reason']=data.reason.strip()
    if row: row.values_json=values;row.updated_by=user.id;row.version+=1
    else: row=ServicePolicy(scope_key=key,organization_id=company_id,module_key='fam',kind='transaction_lock',values_json=values,updated_by=user.id);db.add(row)
    db.flush();audit(db,request,user,company_id,'transaction_lock',row.id,'SET_LOCK' if data.locked_through else 'UNLOCK',before,values);db.commit()
    return {'module':module,**values,'version':row.version}
