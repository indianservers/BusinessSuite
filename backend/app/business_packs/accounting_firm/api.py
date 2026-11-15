from fastapi import APIRouter, Depends, Query
from app.core.deps import get_db,get_current_user
from app.apps.srm.service_checkout_api import pack_selection
from .schemas import PeriodCreate,RevisionInput,WorkUpdate,ReviewInput,AssignmentInput,EngagementCreate
from . import service

router=APIRouter(prefix='/srm/accounts',tags=['Accounts service delivery'])


@router.get('/capabilities')
def capabilities(db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.capabilities(db,actor)


@router.get('/options')
def options(engagement_after:int=Query(0,ge=0),preparer_after:int=Query(0,ge=0),
            reviewer_after:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=100),
            db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.options(db,actor,engagement_after=engagement_after,
                           preparer_after=preparer_after,reviewer_after=reviewer_after,limit=limit)


@router.get('/periods')
def periods(after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.listing(db,actor,after=after,limit=limit)


@router.post('/periods',status_code=201)
def create(data:PeriodCreate,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.create(data,db,actor)


@router.get('/periods/{ident}')
def period(ident:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.get(ident,db,actor)


@router.put('/periods/{ident}/assignment')
def assign(ident:int,data:AssignmentInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.change(ident,'assign',data,db,actor)


@router.put('/periods/{ident}/work')
def work(ident:int,data:WorkUpdate,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.change(ident,'work',data,db,actor)


@router.post('/periods/{ident}/submit')
def submit(ident:int,data:RevisionInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.change(ident,'submit',data,db,actor)


@router.post('/periods/{ident}/approve')
def approve(ident:int,data:ReviewInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.change(ident,'approve',data,db,actor)


@router.post('/periods/{ident}/return')
def return_work(ident:int,data:ReviewInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    return service.change(ident,'return',data,db,actor)


@router.get('/clients')
def engagement_clients(search:str=Query('',max_length=100),after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),
        db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .engagements import clients
    return clients(db,actor,search=search,after=after,limit=limit)


@router.post('/engagements',status_code=201)
def create_engagement(data:EngagementCreate,
        db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .engagements import create
    return create(data,db,actor)


@router.get('/engagements')
def engagements(after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),
        db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .engagements import listing
    return listing(db,actor,after=after,limit=limit)


@router.get('/engagements/{ident}')
def engagement(ident:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .engagements import get
    return get(ident,db,actor)
