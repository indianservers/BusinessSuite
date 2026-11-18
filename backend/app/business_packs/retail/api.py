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

# Preserve every existing return URL while mounting Retail operations separately.
from datetime import date
from fastapi import Query
from .stock_receipts import ReceiptInput
operations = APIRouter(prefix='/srm/retail', tags=['Retail stock and reports'])


@operations.post('/stock-receipts', status_code=201)
def stock_receipt(data: ReceiptInput, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .stock_receipts import create
    return create(data, db, actor)


@operations.get('/stock-receipts')
def receipt_history(after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .stock_receipts import list_receipts
    return list_receipts(db, actor, after=after, limit=limit)


@operations.get('/stock')
def stock(after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), low_only: bool = False, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reports import stock
    return stock(db, actor, after=after, limit=limit, low_only=low_only)


@operations.get('/reports/daily')
def daily(day: date | None = None, db=Depends(get_db), actor=Depends(get_current_user), scope=Depends(pack_selection)):
    from .reports import daily
    return daily(db, actor, day)


_combined = APIRouter()
_combined.include_router(router)
_combined.include_router(operations)
router = _combined
