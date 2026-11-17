"""Selected-POS routes; no generic master or CRM graph release."""
from fastapi import APIRouter,Depends,Header,Query
from app.core.deps import get_current_user,get_db
from . import pos_surface as service
router=APIRouter(prefix='/srm/pos',tags=['Selected POS'])
@router.get('/catalog')
def catalog(after:int=Query(0,ge=0),limit:int=Query(200,ge=1,le=200),search:str=Query('',max_length=100),selected:str|None=Header(None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user)):
    return service.catalog(db,actor,selected,after=after,limit=limit,search=search)
@router.get('/customers')
def customers(after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200),search:str=Query('',max_length=100),selected:str|None=Header(None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user)):
    return service.customers(db,actor,selected,after=after,limit=limit,search=search)
@router.get('/customers/{customer_id}')
def customer(customer_id:int,selected:str|None=Header(None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user)):
    return service.customer_detail(db,actor,customer_id,selected)
@router.post('/customers',status_code=201)
def create(data:service.CustomerInput,selected:str|None=Header(None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user)):
    return service.create_customer(data,db,actor,selected)

@router.get('/customer-schema')
def customer_schema(selected:str|None=Header(None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user)):
    return service.customer_schema(db,actor,selected)


@router.get('/customers/{customer_id}/identity')
def identity(customer_id:int,selected:str|None=Header(None,alias='X-Suite-Pack-Context'),db=Depends(get_db),actor=Depends(get_current_user)):
    return service.customer_identity(db,actor,customer_id,selected)
