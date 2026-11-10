"""Private platform routes must deny credentials before opening owner storage."""
import re
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from app.main import app
from app.core.route_policy import dependency_names,is_public


def private_platform_operations(router,prefix=''):
    for route in router.routes:
        if hasattr(route,'original_router'):
            yield from private_platform_operations(route.original_router,prefix+route.include_context.prefix)
        elif isinstance(route,APIRoute):
            path=prefix+route.path
            if 'current_platform_admin' in set(dependency_names(route.dependant)) and not is_public(path):
                for method in route.methods:
                    yield method,re.sub(r'\{[^}]+\}','1',path)


@pytest.mark.parametrize('authorization',[None,'Bearer invalid-audit-token','Bearer po_short','suite-user-token'])
def test_private_platform_routes_reject_before_database_availability(client,monkeypatch,authorization):
    from app.platform_owner import session
    def unavailable():raise HTTPException(503,'Storage must not be touched before credentials are checked')
    monkeypatch.setattr(session,'platform_factory',unavailable)
    if authorization=='suite-user-token':
        from app.core.security import create_access_token
        authorization='Bearer '+create_access_token('1')
    headers={'Authorization':authorization} if authorization else {}
    operations=list(private_platform_operations(app.router));assert len(operations)>=40
    failures=[]
    for method,path in operations:
        response=client.request(method,path,headers=headers,json={} if method in {'POST','PATCH','PUT'} else None)
        if response.status_code not in {401,403}:failures.append((method,path,response.status_code))
    assert not failures,failures
