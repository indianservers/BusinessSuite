from uuid import UUID
from fastapi import APIRouter,Depends,Request
from app.core.deps import get_db,get_current_user
from app.apps.srm.service_checkout_api import pack_selection
from .return_schemas import PharmaReturnInput
from . import returns

router=APIRouter(prefix='/srm/pharma/returns',tags=['Original medicine returns'])

@router.get('/requests/{request_key}')
def recovery(request_key:UUID,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return returns.recovery(request_key,db,actor)

@router.post('',status_code=201)
def create(data:PharmaReturnInput,request:Request,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return returns.create(data,db,actor,request)

@router.get('/{return_id}')
def read(return_id:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return returns.state(return_id,db,actor)
