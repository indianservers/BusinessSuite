"""Fail-closed company removal and unrelated-owner-record preservation."""
from datetime import timedelta
import uuid
import pytest
from tests.test_public_signup import platform_store, platform_headers, submit, approve
from app.platform_owner.models import PlatformTenant, PlatformTenantDatabase, PlatformDatabaseServer, PlatformRecord
from app.platform_owner import company_removal as removal
from app.platform_owner import service as s

ROOT = "/api/v1/platform/customers"
DROP_DATABASE = removal.drop_database
VERIFY_DATABASE = removal.verify_database


@pytest.fixture
def company(client, db, platform_headers, monkeypatch):
    signup = submit(client, db)
    approve(client, db, platform_headers, signup)
    store=db._platform_db
    tenant=store.query(PlatformTenant).filter_by(signup_id=signup.id).one()
    server=PlatformDatabaseServer(code="test",name="Local test",host="127.0.0.1",port=5432,provisioning_env="TENANT_PROVISIONING_URL",template_database="pristine_test")
    store.add(server);store.flush()
    ident=uuid.uuid4()
    database=PlatformTenantDatabase(signup_id=signup.id,tenant_uuid=str(ident),workspace_code=f"company-{signup.id}",
        company_id=tenant.company_id,server_id=server.id,database_name="suite_c_"+ident.hex,runtime_role="suite_r_"+ident.hex,
        encrypted_password="never-returned",status="ready")
    store.add(database);store.commit()
    calls=[]
    monkeypatch.setattr(removal,"verify_database",lambda d,server: 4321)
    monkeypatch.setattr(removal,"drop_database",lambda d,server,oid: calls.append((d.database_name,d.company_id,oid)))
    return signup,tenant,database,calls


def reviewed(client, headers, ident):
    result=client.post(f"{ROOT}/{ident}/removal/preview",headers=headers)
    assert result.status_code==200,result.text
    data=result.json()
    return {"preview_token":data["preview_token"],"confirmation":data["confirmation"],"reason":"Remove disposable test company"}


def test_removes_only_selected_company_and_redacts_its_owner_records(client,db,platform_headers,company):
    signup,tenant,database,calls=company
    second=submit(client,db,email="keep@example.com");approve(client,db,platform_headers,second)
    other=db._platform_db.query(PlatformTenant).filter_by(signup_id=second.id).one()
    note=PlatformRecord(kind="note",title="Keep company note",tenant_id=other.id,signup_id=second.id,data={"body":"Keep exactly"})
    own=PlatformRecord(kind="note",title="QA leftover",tenant_id=tenant.id,signup_id=signup.id,data={"body":"Delete only this"})
    db._platform_db.add_all([note,own]);db._platform_db.commit(); own_id=own.id;note_id=note.id
    payload=reviewed(client,platform_headers,tenant.id)
    assert not calls
    response=client.post(f"{ROOT}/{tenant.id}/removal",headers=platform_headers,json=payload)
    assert response.status_code==200,response.text
    assert calls==[(database.database_name,tenant.company_id,4321)]
    db._platform_db.expire_all()
    assert db._platform_db.get(PlatformRecord,own_id) is None
    assert db._platform_db.get(PlatformRecord,note_id).data=={"body":"Keep exactly"}
    assert other.status=="trial" and second.email=="keep@example.com"
    assert tenant.status==database.status=="removed" and database.encrypted_password==""
    assert signup.deleted_at and signup.notes is None and signup.email.startswith("removed-company-")
    assert not any(row["id"]==tenant.id for row in client.get("/api/v1/platform/client-directory",headers=platform_headers).json()["items"])
    retry=client.post(f"{ROOT}/{tenant.id}/removal",headers=platform_headers,json=payload)
    assert retry.status_code==200 and len(calls)==1
    assert client.post(f"{ROOT}/{tenant.id}/action",headers=platform_headers,json={"action":"resume","reason":"Try to reopen removed company"}).status_code==409


def test_confirmation_cross_company_and_stale_preview_block_ddl(client,db,platform_headers,company):
    signup,tenant,database,calls=company
    payload=reviewed(client,platform_headers,tenant.id)
    assert client.post(f"{ROOT}/{tenant.id}/removal",headers=platform_headers,json={**payload,"confirmation":"REMOVE company-999"}).status_code==422
    database.routing_version+=1;db._platform_db.commit()
    assert client.post(f"{ROOT}/{tenant.id}/removal",headers=platform_headers,json=payload).status_code==409
    assert not calls and database.status=="ready"


@pytest.mark.parametrize("change",["legal_hold","legacy_database","wrong_database","retention","cross_link"])
def test_unverified_or_protected_targets_never_reach_ddl(client,db,platform_headers,company,change):
    signup,tenant,database,calls=company
    if change=="legal_hold":signup.legal_hold=True
    if change=="legacy_database":db._platform_db.delete(database)
    if change=="wrong_database":database.database_name="business_suite"
    if change=="retention":tenant.config={**tenant.config,"retention_until":(s.now()+timedelta(days=30)).isoformat()}
    if change=="cross_link":
        other=submit(client,db,email="other-link@example.com");approve(client,db,platform_headers,other)
        other_tenant=db._platform_db.query(PlatformTenant).filter_by(signup_id=other.id).one()
        db._platform_db.add(PlatformRecord(kind="note",title="Inconsistent",signup_id=signup.id,tenant_id=other_tenant.id,data={}))
    db._platform_db.commit()
    assert client.post(f"{ROOT}/{tenant.id}/removal/preview",headers=platform_headers).status_code==409
    assert not calls


def test_failed_ddl_fences_routing_and_can_retry_exact_request(client,db,platform_headers,company,monkeypatch):
    signup,tenant,database,calls=company
    payload=reviewed(client,platform_headers,tenant.id)
    def fail(*args):raise RuntimeError("simulated failure after DDL")
    monkeypatch.setattr(removal,"drop_database",fail)
    assert client.post(f"{ROOT}/{tenant.id}/removal",headers=platform_headers,json=payload).status_code==503
    assert database.status==tenant.status=="deleting"
    # Reloading the UI can review the durable destination again, even after the
    # original token has been lost. No connection to a replacement DB is used.
    payload=reviewed(client,platform_headers,tenant.id)
    monkeypatch.setattr(removal,"drop_database",lambda d,server,oid:calls.append(d.company_id))
    assert client.post(f"{ROOT}/{tenant.id}/removal",headers=platform_headers,json=payload).status_code==200
    assert database.status=="removed" and calls==[tenant.company_id]


def test_business_admin_and_support_cannot_remove_companies(client,db,platform_headers,company,superuser_headers):
    from tests.test_platform_portal import staff_login
    _,tenant,_,calls=company
    assert client.post(f"{ROOT}/{tenant.id}/removal/preview",headers=superuser_headers).status_code==401
    _,support=staff_login(client,db._platform_db,"support")
    assert client.post(f"{ROOT}/{tenant.id}/removal/preview",headers=support).status_code==403
    assert not calls


@pytest.mark.parametrize("physical_oid",[4321,9999])
def test_physical_drop_uses_only_verified_identifiers(db,company,monkeypatch,physical_oid):
    from contextlib import contextmanager
    from sqlalchemy.engine import make_url
    from fastapi import HTTPException
    _,_,database,_=company
    server=db._platform_db.get(PlatformDatabaseServer,database.server_id)
    statements=[]
    class Control:
        def execute(self,query,parameters=None):
            statement=query if isinstance(query,str) else query.as_string()
            statements.append((statement,parameters))
            value=(physical_oid,) if statement.startswith("SELECT oid") else (1,) if statement.startswith("SELECT 1 FROM pg_roles") else None
            return type("Cursor",(),{"fetchone":lambda self:value})()
    @contextmanager
    def connection(url):yield Control()
    monkeypatch.setattr(removal,"admin_url",lambda _:make_url("postgresql://localhost/postgres"))
    monkeypatch.setattr(removal,"pg_connection",connection)
    if physical_oid!=4321:
        with pytest.raises(HTTPException):DROP_DATABASE(database,server,4321)
        assert not any(q.startswith(("DROP","ALTER")) for q,_ in statements)
    else:
        DROP_DATABASE(database,server,4321)
        assert [q for q,_ in statements if q.startswith("DROP DATABASE")]==[f'DROP DATABASE "{database.database_name}" WITH (FORCE)']
        assert [q for q,_ in statements if q.startswith("DROP ROLE")]==[f'DROP ROLE "{database.runtime_role}"']
        assert not any("DROP OWNED" in q for q,_ in statements)


def test_removed_workspace_never_falls_back_to_shared_database(db,company,monkeypatch):
    from contextlib import contextmanager
    from fastapi import HTTPException
    from app.db import tenant as routing
    _,_,database,_=company
    database.status="removed";db._platform_db.commit()
    @contextmanager
    def registry():yield db._platform_db
    monkeypatch.setattr(routing,"registry_factory",lambda:registry)
    with pytest.raises(HTTPException) as blocked:routing.lookup_route(database.workspace_code)
    assert blocked.value.status_code==410
    from app.platform_owner import tenant_provisioning as provisioning
    monkeypatch.setattr(provisioning,"platform_factory",lambda:registry)
    with pytest.raises(HTTPException) as recreate:provisioning.ensure_database(database.signup_id)
    assert recreate.value.status_code==409
