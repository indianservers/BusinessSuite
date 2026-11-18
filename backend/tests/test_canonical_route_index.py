from fastapi import FastAPI, APIRouter, Request
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest
from app.business_packs.common_binding import canonical_route


def test_nested_aliases_and_late_registration_remain_canonical():
    app=FastAPI()
    child=APIRouter()
    @child.get('/items/{item_id}')
    def item(item_id: int, request: Request):
        return {'route':canonical_route(request)}
    app.include_router(child,prefix='/first')
    app.include_router(child,prefix='/second')
    with TestClient(app) as client:
        for _ in range(2):
            for prefix in ('first','second'):
                assert client.get(f'/{prefix}/items/1').json()=={'route':f'/{prefix}/items/{{item_id}}'}
        @child.get('/later')
        def later(request: Request):
            return {'route':canonical_route(request)}
        assert client.get('/first/later').json()=={'route':'/first/later'}
        app.include_router(child,prefix='/third')
        assert client.get('/third/items/2').json()=={'route':'/third/items/{item_id}'}


def test_index_never_trusts_unmatched_route_or_method():
    app=FastAPI()
    @app.get('/native/{ident}')
    def native(ident: int):return {}
    route=app.routes[-1]
    base={'type':'http','app':app,'route':route,'path':'/native/1','root_path':'','method':'GET','headers':[],'query_string':b''}
    assert canonical_route(StarletteRequest(base))=='/native/{ident}'
    assert canonical_route(StarletteRequest({**base,'path':'/unregistered'})) is None
    assert canonical_route(StarletteRequest({**base,'method':'DELETE'})) is None
    other=FastAPI()
    assert canonical_route(StarletteRequest({**base,'app':other})) is None
