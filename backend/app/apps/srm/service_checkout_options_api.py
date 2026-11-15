"""Mount this static options router before the checkout ID router."""
from fastapi import APIRouter, Depends, Header, Query
from app.core.deps import get_db, get_current_user
from app.apps.srm.service_checkout_options import provider_options, service_options

router = APIRouter(prefix='/srm/service-checkout/options', tags=['Native service checkout'])


@router.get('/providers')
def providers(search: str = Query('', max_length=100), selected: str | None = Header(None, alias='X-Suite-Pack-Context'),
        db=Depends(get_db), actor=Depends(get_current_user)):
    return provider_options(db, actor, selected=selected, search=search)


@router.get('')
def options(service_id: int = Query(..., gt=0), search: str = Query('', max_length=100), selected: str | None = Header(None, alias='X-Suite-Pack-Context'),
        db=Depends(get_db), actor=Depends(get_current_user)):
    return service_options(db, actor, service_id, selected=selected, search=search)
