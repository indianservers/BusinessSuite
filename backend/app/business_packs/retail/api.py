from fastapi import APIRouter,Depends,Request
from app.core.deps import get_db,get_current_user
from app.apps.srm.service_checkout_api import pack_selection
from .schemas import ReturnInput
from .returns import create,state
from uuid import UUID

router=APIRouter(prefix='/srm/retail/returns',tags=['Retail original-sale returns'])


@router.get('/sales/{checkout_id}')
def original_sale(checkout_id:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .returns import sale_options
    return sale_options(checkout_id,db,actor)


@router.get('/requests/{request_key}')
def recover_request(request_key:UUID,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .returns import recovery
    return recovery(request_key,db,actor)


@router.post('',status_code=201)
def return_sale(data:ReturnInput,request:Request,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return create(data,db,actor,request)


@router.get('/{return_id}')
def read_return(return_id:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return state(return_id,db,actor)
