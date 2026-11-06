"""Database selection is signed, scoped and established before any DB access."""
from dataclasses import replace
from cryptography.fernet import Fernet
from fastapi import FastAPI,HTTPException,Request
from fastapi.testclient import TestClient
import pytest
from app.core.config import settings
from app.core.security import create_access_token,create_refresh_token,verify_access_token
from app.core.middleware.tenant_database import TenantDatabaseMiddleware
from app.db import tenant
from app.platform_owner.models import PlatformTenantDatabase
from app.platform_owner.service import encode


@pytest.fixture
def routing(monkeypatch):
    monkeypatch.setattr(settings,"TENANT_DATABASES_ENABLED",True)
    route=tenant.TenantRoute("11111111-1111-4111-8111-111111111111","company-100",100,"127.0.0.1",5432,"test_company","test_runtime","not-a-secret",1)
    def lookup(value):
        if value in {route.workspace_code,route.tenant_uuid}:return route
        raise HTTPException(503,"Company database unavailable")
    monkeypatch.setattr("app.core.middleware.tenant_database.lookup_route",lookup)
    app=FastAPI()
    @app.get("/api/v1/probe")
    def probe():
        value=tenant.current_tenant.get()
        return {"tenant":value.tenant_uuid if value else None}
    @app.post("/api/v1/auth/refresh")
    def refresh():return probe()
    @app.get("/api/v1/platform/probe")
    def platform_probe():return probe()
    app.add_middleware(TenantDatabaseMiddleware)
    with TestClient(app) as client:yield client,route
    assert tenant.current_tenant.get() is None


def signed(route,refresh=False):
    marker=tenant.current_tenant.set(route)
    try:return (create_refresh_token if refresh else create_access_token)(1,session_id=1)
    finally:tenant.current_tenant.reset(marker)


def test_signed_tenant_selects_database_without_client_header(routing):
    client,route=routing
    response=client.get("/api/v1/probe",headers={"Authorization":"Bearer "+signed(route)})
    assert response.json()=={"tenant":route.tenant_uuid}
    assert client.get("/api/v1/probe").json()=={"tenant":None}


def test_header_cannot_change_signed_tenant_or_promote_legacy_session(routing):
    client,route=routing
    for raw in [signed(route),create_access_token(1,session_id=1),"invalid"]:
        assert client.get("/api/v1/probe",headers={"Authorization":"Bearer "+raw,"X-Suite-Tenant":"company-other"}).status_code==403


def test_unknown_workspace_fails_closed(routing):
    client,_=routing
    assert client.get("/api/v1/probe",headers={"X-Suite-Tenant":"missing"}).status_code==503


def test_refresh_capability_routes_without_access_token(routing):
    client,route=routing
    response=client.post("/api/v1/auth/refresh",json={"refresh_token":signed(route,True)})
    assert response.json()=={"tenant":route.tenant_uuid}
    assert client.post("/api/v1/auth/refresh",headers={"X-Suite-Tenant":"company-other"},json={"refresh_token":signed(route,True)}).status_code==403


def test_platform_routes_never_enter_a_client_database(routing):
    client,route=routing
    assert client.get("/api/v1/platform/probe",headers={"Authorization":"Bearer "+signed(route),"X-Suite-Tenant":route.workspace_code}).json()=={"tenant":None}


def test_workspace_claim_is_part_of_signed_token(routing):
    _,route=routing
    payload=verify_access_token(signed(route))
    assert payload["tenant"]==route.tenant_uuid and payload["workspace"]==route.workspace_code


def test_directory_serialization_never_returns_database_secret():
    row=PlatformTenantDatabase(signup_id=1,tenant_uuid="uuid",workspace_code="company-1",company_id=1,server_id=1,
        database_name="db",runtime_role="runtime",encrypted_password="never-expose-this")
    assert "encrypted_password" not in encode(row)
    assert "never-expose-this" not in str(encode(row))


def test_engine_cache_is_bounded_and_uses_no_idle_tenant_pools(monkeypatch):
    monkeypatch.setattr(settings,"TENANT_SECRET_KEY",Fernet.generate_key().decode())
    monkeypatch.setattr(settings,"TENANT_ENGINE_CACHE_SIZE",2)
    secret=tenant.cipher().encrypt(b"qa-runtime-password").decode()
    tenant._engines.clear()
    route=tenant.TenantRoute("uuid","company-1",1,"127.0.0.1",5432,"qa_db","qa_role",secret,1)
    for version in range(4):
        engine=tenant.tenant_engine(replace(route,version=version))
        assert engine.pool.__class__.__name__=="NullPool"
    assert len(tenant._engines)==2
    for engine in tenant._engines.values():engine.dispose()
    tenant._engines.clear()


def test_realtime_never_broadcasts_overlapping_local_ids_across_databases(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from app.apps.project_management.realtime import PMSRealtimeManager
    class Socket:
        def __init__(self):self.messages=[]
        async def accept(self):pass
        async def send_text(self,value):self.messages.append(value)
    manager=PMSRealtimeManager()
    monkeypatch.setattr(manager,"_authorized",lambda *args:True)
    async def scenario():
        a,b=Socket(),Socket()
        for socket,uuid in [(a,"tenant-a"),(b,"tenant-b")]:
            marker=tenant.current_tenant.set(SimpleNamespace(tenant_uuid=uuid))
            try:await manager.connect(socket,user_id=1,organization_id=1,accessible_project_ids={1})
            finally:tenant.current_tenant.reset(marker)
        marker=tenant.current_tenant.set(SimpleNamespace(tenant_uuid="tenant-a"))
        try:await manager.broadcast({"recipientIds":[1],"projectId":1})
        finally:tenant.current_tenant.reset(marker)
        assert len(a.messages)==1 and b.messages==[]
    asyncio.run(scenario())
