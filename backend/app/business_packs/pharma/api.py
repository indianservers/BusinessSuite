from fastapi import APIRouter,Depends,Query
from app.core.deps import get_db,get_current_user
from app.apps.srm.service_checkout_api import pack_selection
from .schemas import ReceiptInput
from .receipts import create

router=APIRouter(prefix='/srm/pharma',tags=['Pharma batch stock'])


@router.get('/returns/sales/{checkout_id}/lots')
def return_sale_lots(checkout_id:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .return_sources import original_lots
    return {'checkout_id':checkout_id,'lots':[
        {'checkout_line_id':row.checkout_line_id,'allocation_id':row.allocation_id,
         'batch_id':row.batch_id,'product_id':row.product_id,'warehouse_id':row.warehouse_id,
         'batch_number':row.batch_number,'expiry_date':row.expiry_date.isoformat(),
         'sold_quantity':str(row.sold_quantity)} for row in original_lots(db,actor,checkout_id)]}


@router.post('/batch-receipts',status_code=201)
def receive(data:ReceiptInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return create(data,db,actor)


@router.get('/options')
def options(search:str=Query('',max_length=100),after:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .reads import options
    return options(db,actor,search=search,after=after,limit=limit)


@router.get('/batches')
def batches(search:str=Query('',max_length=100),after:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .reads import batches
    return batches(db,actor,search=search,after=after,limit=limit)


from .recall_schemas import RecallInput,RecallCommand


@router.post('/recalls',status_code=201)
def recall_create(data:RecallInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .recalls import create
    return create(data,db,actor)


@router.post('/recalls/{recall_id}/commands')
def recall_command(recall_id:int,data:RecallCommand,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .recalls import command
    return command(recall_id,data,db,actor)


@router.get('/recalls')
def recalls(after:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .recalls import list_cases
    return list_cases(db,actor,after=after,limit=limit)


@router.get('/recalls/{recall_id}')
def recall_detail(recall_id:int,include_affected_sales:bool=False,after:int=Query(0,ge=0),limit:int=Query(30,ge=1,le=100),db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .recalls import detail
    result=detail(recall_id,db,actor)
    if include_affected_sales:
        from .trace import affected_sales
        result['affected_sales']=affected_sales(recall_id,db,actor,after=after,limit=limit)
    return result
