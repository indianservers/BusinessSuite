from fastapi import APIRouter, Depends, Query, Form, File, UploadFile, HTTPException
from uuid import UUID
from app.core.deps import get_db,get_current_user
from app.apps.srm.service_checkout_api import pack_selection
from .schemas import PeriodCreate,RevisionInput,WorkUpdate,ReviewInput,AssignmentInput,EngagementCreate,BillingInput,ActualTimeInput
from . import service
from .schemas import DocumentRequestInput,DocumentAttachInput
from .schemas import ProjectLinkInput
from .schemas import DocumentUploadInput
from app.apps.srm.payments import PaymentInput

router=APIRouter(prefix='/srm/accounts',tags=['Accounts service delivery'])


@router.get('/periods/{ident}/delivery')
def delivery(ident:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .selectors import delivery
    return delivery(ident,db,actor)


@router.get('/periods/{ident}/project-options')
def project_options(ident:int,after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),search:str=Query('',max_length=100),
        db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .selectors import projects
    return projects(ident,db,actor,after=after,limit=limit,search=search)


@router.get('/periods/{ident}/task-options')
def task_options(ident:int,after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),search:str=Query('',max_length=100),
        db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .selectors import tasks
    return tasks(ident,db,actor,after=after,limit=limit,search=search)


@router.post('/periods/{ident}/documents/{key}/upload',status_code=201)
def document_upload(ident:int,key:UUID,data:str=Form(...),file:UploadFile=File(...),
        db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from pydantic import ValidationError
    from .uploads import upload
    try:
        metadata = DocumentUploadInput.model_validate_json(data)
    except ValidationError:
        raise HTTPException(422,'Enter valid document upload metadata') from None
    return upload(ident,key,metadata,file,db,actor)


@router.post('/periods/{ident}/payments',status_code=201)
def collection(ident:int,data:PaymentInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .billing import collect
    return collect(ident,data,db,actor)


@router.post('/periods/{ident}/project')
def delivery_project(ident:int,data:ProjectLinkInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .project_links import link
    return link(ident,data,db,actor)


@router.get('/periods/{ident}/documents')
def document_list(ident:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .documents import listing
    return listing(ident,db,actor)


@router.post('/periods/{ident}/documents',status_code=201)
def document_request(ident:int,data:DocumentRequestInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .documents import request
    return request(ident,data,db,actor)


@router.put('/periods/{ident}/documents/{key}')
def document_attach(ident:int,key:UUID,data:DocumentAttachInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .documents import attach
    return attach(ident,key,data,db,actor)


@router.get('/periods/{ident}/documents/{key}/download')
def document_download(ident:int,key:UUID,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .documents import download
    return download(ident,key,db,actor)


@router.post('/periods/{ident}/time',status_code=201)
def actual_time(ident:int,data:ActualTimeInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .actual_time import record
    return record(ident,data,db,actor)


@router.post('/periods/{ident}/invoice',status_code=201)
def invoice(ident:int,data:BillingInput,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .billing import draft
    return draft(ident,data,db,actor)


@router.get('/periods/{ident}/billing')
def billing(ident:int,db=Depends(get_db),actor=Depends(get_current_user),scope=Depends(pack_selection)):
    from .billing import outstanding
    return outstanding(ident,db,actor)


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
