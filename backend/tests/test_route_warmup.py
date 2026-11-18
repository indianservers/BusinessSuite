from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from app.core.route_warmup import prime_routes


def test_route_preparation_never_executes_handlers_or_authorization():
    calls = {'guard': 0, 'handler': 0}
    def guard(authorization: str | None = Header(default=None)):
        calls['guard'] += 1
        if authorization != 'Bearer fixture':
            raise HTTPException(401, 'Login required')
    child = APIRouter()
    @child.get('/items/{ident}', dependencies=[Depends(guard)])
    def item(ident: int):
        calls['handler'] += 1
        return {'id': ident}
    nested = APIRouter()
    nested.include_router(child, prefix='/records')
    app = FastAPI()
    app.include_router(nested, prefix='/api/v1')
    prime_routes(app)
    assert calls == {'guard': 0, 'handler': 0}
    client = TestClient(app)
    assert client.get('/api/v1/records/items/7').status_code == 401
    assert calls == {'guard': 1, 'handler': 0}
    response = client.get('/api/v1/records/items/7', headers={'Authorization': 'Bearer fixture'})
    assert response.json() == {'id': 7}
    assert calls == {'guard': 2, 'handler': 1}
    # Later registrations retain the router's native invalidation and method checks.
    later = APIRouter()
    @later.post('/later')
    def create():
        calls['handler'] += 1
        return {'created': True}
    app.include_router(later, prefix='/api/v1')
    prime_routes(app)
    assert calls == {'guard': 2, 'handler': 1}
    assert client.get('/api/v1/later').status_code == 405
    assert client.post('/api/v1/later').json() == {'created': True}
