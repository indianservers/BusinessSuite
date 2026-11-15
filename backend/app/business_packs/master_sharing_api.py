from fastapi import APIRouter, Depends, Query, Request
from app.core.deps import get_db, get_current_user
from . import master_sharing as service
from .master_sharing_schemas import MasterKind, ShareMaster, GrantPreview

router = APIRouter(prefix='/business-packs', tags=['Business Packs settings'])


@router.get('/contexts/{context_id}/master-options')
def masters(context_id: int, kind: MasterKind, search: str = Query('', max_length=100), db=Depends(get_db), actor=Depends(get_current_user)):
    return service.master_options(db, actor, context_id, kind, search)


@router.put('/contexts/{context_id}/masters')
def share(context_id: int, data: ShareMaster, request: Request, db=Depends(get_db), actor=Depends(get_current_user)):
    return service.share_master(db, actor, context_id, data, request)


@router.get('/contexts/{context_id}/user-options')
def users(context_id: int, search: str = Query('', max_length=100), db=Depends(get_db), actor=Depends(get_current_user)):
    return service.user_options(db, actor, context_id, search)


@router.post('/contexts/{context_id}/grant-preview')
def preview(context_id: int, data: GrantPreview, db=Depends(get_db), actor=Depends(get_current_user)):
    return service.grant_preview(db, actor, context_id, data)
