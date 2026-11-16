"""Exact native branch destination for addressed company-admin pack configuration writes."""
from types import MappingProxyType
from fastapi import HTTPException
from sqlalchemy import select

TARGETS = MappingProxyType({
    ('PUT','/api/v1/access/settings/business-packs/contexts/{context_id}/masters'):'context_id',
    ('POST','/api/v1/access/settings/business-packs/contexts/{ident}/activate'):'ident',
})

def addressed_branch(db, actor, request):
    route=request.scope.get('route')
    template=getattr(route,'path',None)
    if not isinstance(template,str):return None
    if (request.method,template) not in TARGETS:
        template='/api/v1/access/settings'+template
    field=TARGETS.get((request.method,template))
    if field is None:return None
    try:canonical=template.format_map(request.path_params)
    except KeyError:raise HTTPException(403,'Pack configuration context is unavailable')
    if canonical!=request.url.path:return None
    raw=request.path_params.get(field)
    if not isinstance(raw,(str,int)) or isinstance(raw,bool) or len(str(raw))>10 or not str(raw).isascii() or not str(raw).isdecimal():
        raise HTTPException(403,'Pack configuration context is unavailable')
    ident=int(raw)
    if not 0<ident<=2147483647:raise HTTPException(403,'Pack configuration context is unavailable')
    from .service import company_control
    from .models import PackContext
    from app.branches.service import context
    company=company_control(db,actor)
    table=PackContext.__table__
    branch=db.connection().scalar(select(table.c.branch_id).where(table.c.id==ident,table.c.company_id==company))
    if branch is None:raise HTTPException(403,'Pack configuration context is unavailable')
    fresh=context(db,actor,company,str(branch))
    if fresh.company_id!=company or fresh.branch_id!=branch or branch not in fresh.writable:
        raise HTTPException(403,'Pack configuration branch is not writable')
    return branch
