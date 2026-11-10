"""Resolve only approved placements for an already verified social identity."""
from app.platform_owner.models import PlatformSignupRequest, PlatformTenantDatabase
from app.platform_owner.session import platform_factory
from app.db.tenant import current_tenant, lookup_route, tenant_session
from sqlalchemy import func
from fastapi import HTTPException


def discover(identity, data, request, legacy_user=None):
    from app.api.v1.auth import firebase_login
    with platform_factory()() as owner:
        rows=owner.query(PlatformTenantDatabase,PlatformSignupRequest).join(PlatformSignupRequest,
            PlatformSignupRequest.id==PlatformTenantDatabase.signup_id).filter(
            func.lower(PlatformSignupRequest.email)==identity["email"].lower(),PlatformSignupRequest.status=="approved",
            PlatformSignupRequest.deleted_at.is_(None),PlatformTenantDatabase.status=="ready").all()
        choices=[{"workspace":p.workspace_code,"name":r.company_name or r.name} for p,r in rows]
    if legacy_user and legacy_user.is_active:
        choices.append({"workspace":"legacy","name":"Existing company workspace"})
    if not choices:
        if data.workspace:raise HTTPException(403,"This identity does not have access to that workspace")
        return None
    if len(choices)>1 and not data.workspace:
        return {"workspace_required":True,"workspaces":choices}
    workspace=data.workspace or choices[0]["workspace"]
    if workspace not in {c["workspace"] for c in choices}:
        raise HTTPException(403,"This identity does not have access to that workspace")
    if workspace=="legacy":return None
    route=lookup_route(workspace)
    marker=current_tenant.set(route)
    try:
        with tenant_session(route) as db:
            result=firebase_login(data.model_copy(update={"workspace":None}),request,db)
            if isinstance(result,dict):return {**result,"workspace":route.workspace_code}
            return {**result.model_dump(),"workspace":route.workspace_code}
    finally:current_tenant.reset(marker)
