"""Explicit company-admin counter account setup; no automatic activation."""
from fastapi import APIRouter,Depends
from app.core.deps import get_db,get_current_user
from .service_checkout_api import pack_selection
from .anonymous_cash_schemas import CashAccountSetup
from .anonymous_cash import configure,installed,_scope_query
from .service_checkout import _authority
router=APIRouter(prefix='/srm/anonymous-cash',tags=['Anonymous counter account setup'])
@router.put('/configuration')
def setup(data:CashAccountSetup,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return configure(data,db,actor)
@router.get('/configuration')
def configuration(db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    company,branch,scope=_authority(db,actor,write=False)
    if scope and not any(scope.pack_key+'.'+cap in scope.capabilities for cap in ('checkout.view','checkout.create','billing.view','billing.prepare','payments.record','settings.manage')):
        from fastapi import HTTPException
        raise HTTPException(403,'Assigned Business Pack role cannot inspect counter account settings')
    ready=installed(db.connection())
    row=_scope_query(db,company,branch,scope).first() if ready else None
    return {'schema_ready':ready,'configured':row is not None,'enabled':bool(row and row.active),
        'revision':row.revision if row else 0,'label':row.account_label if row else None}
