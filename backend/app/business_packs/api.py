"""Settings control plane. Native operational pack routes remain separate."""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from . import schemas, service

router = APIRouter(prefix='/business-packs', tags=['Business Packs settings'])


@router.get('/theme')
def theme(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .theme_selection import configuration
    return configuration(db, actor)


@router.post('/theme')
def activate_theme(data: schemas.ActivateTheme, request: Request,
                   db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    from .theme_selection import activate
    return activate(db, actor, data, request)


@router.get('/catalog')
def catalog(db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.catalog(db, actor)


@router.get('/configuration')
def configuration(limit: int = Query(200, ge=1, le=200), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.configuration(db, actor, limit)


@router.get('/readiness')
def readiness(pack_key: str = Query(min_length=1, max_length=64), branch_id: int | None = Query(None, gt=0),
              db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.readiness(db, actor, pack_key, branch_id)


@router.post('/preview')
def preview(data: schemas.PreviewInput, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.preview(db, actor, data)


@router.post('/activations', status_code=201)
def draft_activation(data: schemas.DraftActivation, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.draft_activation(db, actor, data, request)


@router.post('/contexts', status_code=201)
def draft_context(data: schemas.DraftContext, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.draft_context(db, actor, data, request)


@router.put('/contexts/{context_id}/grants/{user_id}')
def grant_role(context_id: int, user_id: int, data: schemas.GrantRole, request: Request,
               db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.grant_role(db, actor, context_id, user_id, data, request)


@router.post('/activations/{ident}/activate')
def activate(ident: int, data: schemas.Activate, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.activate(db, actor, ident, data, request)


@router.post('/contexts/{ident}/activate')
def activate_context(ident: int, data: schemas.ActivateContext, request: Request, db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.activate_context(db, actor, ident, data, request)


@router.get('/history')
def history(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), actor: User = Depends(get_current_user)):
    return service.history(db, actor, limit)
