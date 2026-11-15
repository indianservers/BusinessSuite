"""Read-only employee booking projection; never creates actual time entries."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter()


@router.get('/planned-services')
def scheduled_services_list(
    request: Request,
    from_at: datetime,
    until_at: datetime,
    employee_id: int | None = Query(None, gt=0),
    service_id: int | None = Query(None, gt=0),
    pack_context_id: int | None = Query(None, gt=0),
    statuses: list[str] | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2000),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    from app.branches.service import context
    from app.business_packs.access import resolve_context
    from app.services.planned_services import scheduled_services

    header_context = request.headers.get('X-Suite-Pack-Context')
    if header_context is not None and pack_context_id is not None and header_context != str(pack_context_id):
        raise HTTPException(403, 'Business Pack selections must match')
    branch = context(db, actor, actor.organization_id, request.headers.get('X-Suite-Branch'))
    pack = resolve_context(db, actor, branch, requested_context_id=pack_context_id if pack_context_id is not None else header_context)
    return scheduled_services(db, actor, branch, from_at, until_at, pack_scope=pack,
        employee_id=employee_id, service_id=service_id, limit=limit, cursor=cursor, statuses=statuses)


@router.get('/{employee_id}/planned-services')
def employee_planned_services(
    employee_id: int,
    request: Request,
    from_at: datetime,
    until_at: datetime,
    pack_context_id: int | None = Query(None, gt=0),
    limit: int = Query(100, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2000),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    from app.branches.service import context
    from app.business_packs.access import resolve_context
    from app.services.planned_services import planned_services

    header_context = request.headers.get('X-Suite-Pack-Context')
    if header_context is not None and pack_context_id is not None and header_context != str(pack_context_id):
        raise HTTPException(403, 'Business Pack selections must match')
    branch = context(db, actor, actor.organization_id, request.headers.get('X-Suite-Branch'))
    pack = resolve_context(db, actor, branch, requested_context_id=pack_context_id if pack_context_id is not None else header_context)
    return planned_services(db, actor, branch, employee_id, from_at, until_at,
                            pack_scope=pack, limit=limit, cursor=cursor)
