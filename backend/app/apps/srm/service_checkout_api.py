"""Unregistered atomic checkout routes; mounting is an integration decision."""
from fastapi import APIRouter,Depends,Header
from app.core.deps import get_db,get_current_user
from app.apps.srm.service_checkout_schemas import CheckoutInput,PolicyInput,EligibilityInput,AppendPaymentInput,GroupedRescheduleInput
from app.apps.srm.service_checkout import checkout,save_policy,save_eligibility,servicecheckout_state,installation_ready,append_payment,grouped_schedule,reschedule_grouped

router=APIRouter(prefix='/srm/service-checkout',tags=['Native service checkout'])


def pack_selection(selected:str|None=Header(default=None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user),expected_realm:str|None=Header(default=None,alias='X-Suite-Expected-Pack-Realm')):
    from app.business_packs.access import resolve_context
    from app.branches.service import context
    from app.apps.srm.services.commercial import tenant
    from fastapi import HTTPException
    branch=getattr(db.info.get('branch_context'),'branch_id',None)
    if not branch:raise HTTPException(409,'Select one branch')
    fresh=context(db,actor,tenant(actor),str(branch))
    resolved=resolve_context(db,actor,fresh,requested_context_id=selected)
    from app.business_packs.request_scope import assert_expected_realm
    assert_expected_realm(resolved,expected_realm if isinstance(expected_realm,str) else None)
    absent=object()
    previous=db.info.get('business_pack_scope',absent)
    if previous is not absent and previous!=resolved:raise HTTPException(403,'Business Pack selection cannot change inside a request')
    # Keep the exact object captured by the installed native record guard.
    # A fresh equal authorization proves it remains valid, not a new binding.
    bound=resolved if previous is absent else previous
    db.info['business_pack_scope']=bound
    try:yield bound
    finally:
        if previous is absent:db.info.pop('business_pack_scope',None)
        else:db.info['business_pack_scope']=previous

@router.post('',status_code=201)
def create(data:CheckoutInput,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return checkout(data,db,actor)

@router.put('/policies')
def policy(data:PolicyInput,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return save_policy(data,db,actor)

@router.put('/eligibility')
def eligibility(data:EligibilityInput,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return save_eligibility(data,db,actor)

@router.get('/{checkout_id}')
def state(checkout_id:int,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return servicecheckout_state(db,actor,db.info.get('branch_context'),checkout_id)


@router.post('/{checkout_id}/payments',status_code=201)
def payment(checkout_id:int,data:AppendPaymentInput,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return append_payment(checkout_id,data,db,actor)


@router.get('/appointments/{appointment_id}/schedule')
def schedule(appointment_id:int,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    return grouped_schedule(appointment_id,db,actor)

@router.post('/appointments/{appointment_id}/schedule')
def move_schedule(appointment_id:int,data:GroupedRescheduleInput,db=Depends(get_db),actor=Depends(get_current_user),_pack=Depends(pack_selection)):
    moved=reschedule_grouped(appointment_id,data,db,actor)
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.industry_api import out
    return {'appointment':out(db.get(IndustryRecord,moved['appointment_id']), db, actor),'schedule':moved}
