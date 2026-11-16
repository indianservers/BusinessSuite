"""Mount this static options router before the checkout ID router."""
from fastapi import APIRouter, Depends, Header, Query
from app.core.deps import get_db, get_current_user
from app.apps.srm.service_checkout_options import provider_options, service_options, scheduling_availability
from datetime import date, datetime

router = APIRouter(prefix='/srm/service-checkout/options', tags=['Native service checkout'])


@router.get('/availability')
def availability(service_id: int = Query(..., gt=0), eligibility_id: int = Query(..., gt=0),
        day: date = Query(...), duration_minutes: int = Query(..., ge=5, le=720),
        resource_ids: list[int] = Query([]), starts_at: datetime | None = Query(None),
        selected: str | None = Header(None, alias='X-Suite-Pack-Context'),
        db=Depends(get_db), actor=Depends(get_current_user)):
    return scheduling_availability(db, actor, service_id, eligibility_id, day, duration_minutes,
        resource_ids=resource_ids, starts_at=starts_at, selected=selected)


@router.get('/providers')
def providers(search: str = Query('', max_length=100), selected: str | None = Header(None, alias='X-Suite-Pack-Context'),
        db=Depends(get_db), actor=Depends(get_current_user)):
    return provider_options(db, actor, selected=selected, search=search)


@router.get('')
def options(service_id: int = Query(..., gt=0), search: str = Query('', max_length=100), selected: str | None = Header(None, alias='X-Suite-Pack-Context'),
        db=Depends(get_db), actor=Depends(get_current_user)):
    return service_options(db, actor, service_id, selected=selected, search=search)
