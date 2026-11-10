"""Private platform routes must deny credentials before opening owner storage."""
import re
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from app.main import app
from app.core.route_policy import dependency_names,is_public


def private_platform_gets(router,prefix=''):
    for route in router.routes:
        if hasattr(route,'original_router'):
            yield from private_platform_gets(route.original_router,prefix+route.include_context.prefix)
        elif isinstance(route,APIRoute):
            path=prefix+route.path
            if 'GET' in route.methods and 'current_platform_admin' in set(dependency_names(route.dependant)) and not is_public(path):
                yield re.sub(r'\{[^}]+\}','1',path)


@pytest.mark.parametrize('authorization',[None,'Bearer invalid-audit-token','Bearer po_short'])
def test_private_platform_routes_reject_before_database_availability(client,monkeypatch,authorization):
    from app.platform_owner import session
    def unavailable():raise HTTPException(503,'Storage must not be touched before credentials are checked')
    monkeypatch.setattr(session,'platform_factory',unavailable)
    headers={'Authorization':authorization} if authorization else {}
    paths=list(private_platform_gets(app.router));assert len(paths)>=20
    failures=[]
    for path in paths:
        response=client.get(path,headers=headers)
        if response.status_code not in {401,403}:failures.append((path,response.status_code))
    assert not failures,failures
