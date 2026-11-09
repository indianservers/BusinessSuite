from pathlib import Path
from datetime import timedelta
import hashlib
import pytest
from fastapi import HTTPException
from tests.rich_text_test_utils import organization_context
from app.core.config import settings
from app.core.audit_context import context
from app.core.storage import persist_file, materialize_file
from app.models.file_storage import StoragePolicy, StorageConnection, StorageObject, StorageOAuthState
from app.services import file_storage_providers as providers
from app.services.file_storage import locator
from app.apps.power_apps.integrations.vault import CredentialVault

ROOT = "/api/v1/files-storage"


def test_google_root_uses_scope_permitted_listing(monkeypatch):
    from types import SimpleNamespace
    calls = []
    monkeypatch.setattr(providers, "json_request", lambda *args: calls.append(args[3]) or {"files": []})
    assert providers.folder_info(None, SimpleNamespace(provider="google_drive"), "root")["id"] == "root"
    assert len(calls) == 1 and "/files?" in calls[0]


def test_note_route_uses_only_current_users_drive(db):
    from app.services.file_storage import upload_route
    own = StorageConnection(organization_id=1, provider="google_drive", label="Personal", created_by=1, connected=True)
    other = StorageConnection(organization_id=1, provider="google_drive", label="Other", created_by=2, connected=True)
    db.add_all([own, other]); db.flush()
    token = context.set({"actor": {"user_id": 1, "access_company": 1}})
    try:
        assert upload_route(db, 1, "pms", 1) == {"connection_id": own.id, "folder_id": "root"}
        assert upload_route(db, 2, "pms", 1) is None
        with pytest.raises(HTTPException) as error:
            upload_route(db, 1, "pms", 2)
        assert error.value.status_code == 403
        assert upload_route(db, 1, "pms") is None
    finally:
        context.reset(token)


def test_cloud_quota_failure_explains_recovery(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(providers.HttpTransport, "request", lambda *args, **kwargs: SimpleNamespace(status=507))
    with pytest.raises(HTTPException) as error:
        providers.request("POST", "https://graph.microsoft.com/v1.0/me/drive/root/children")
    assert error.value.status_code == 409
    assert "quota is full" in error.value.detail
    assert "original file is retained" in error.value.detail


@pytest.fixture
def storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "local")
    return tmp_path


def cloud(db, provider="google_drive", company=1):
    conn = StorageConnection(organization_id=company, provider=provider, label=provider, created_by=1, connected=True,
        encrypted_value=CredentialVault.encrypt({"access_token": "unit-test-only", "refresh_token": "unit-test-only", "account":"qa@example.test"}), expires_at=providers.now()+timedelta(hours=1))
    db.add(conn); db.flush()
    policy = db.get(StoragePolicy, company)
    if not policy:
        policy = StoragePolicy(organization_id=company, revision=1, enabled=True, default_provider=provider)
        db.add(policy)
    policy.enabled=True
    policy.routes={"default":{"connection_id":conn.id,"folder_id":"qa-folder","folder_name":"QA"}}
    db.commit()
    return conn, policy


def test_settings_default_and_credentials_are_private(client, superuser_headers):
    response=client.get(ROOT,headers=superuser_headers)
    assert response.status_code==200,response.text
    data=response.json()
    assert data["default_provider"]=="google_drive" and data["enabled"] is False
    assert {p["id"] for p in data["providers"]}=={"google_drive","box","onedrive","dropbox"}
    assert data["server_photos"] is True
    assert not any(key in data for key in ("access_token","refresh_token","client_secret"))
    assert client.get(ROOT).status_code in {401,403}


def test_missing_oauth_setup_does_not_create_account(client,db,superuser_headers,monkeypatch):
    monkeypatch.setattr(settings,"FILES_GOOGLE_CLIENT_JSON","")
    monkeypatch.setattr(settings,"FILES_GOOGLE_CLIENT_ID","")
    monkeypatch.setattr(settings,"POWER_GOOGLE_CLIENT_ID","")
    response=client.post(ROOT+"/connect",headers=superuser_headers,json={"provider":"google_drive"})
    assert response.status_code==503,response.text
    assert db.query(StorageConnection).count()==0
    assert client.get(ROOT+"/oauth/callback?state=unknown&code=unknown").status_code==400


def test_module_folders_validate_company_and_revision(client,db,superuser_headers,monkeypatch):
    conn,policy=cloud(db)
    other,_=cloud(db,company=2)
    monkeypatch.setattr(providers,"folder_info",lambda db,c,folder:{"id":folder,"name":"Verified folder"})
    payload={"revision":policy.revision,"enabled":True,"default_provider":"google_drive","routes":{"default":{"connection_id":conn.id,"folder_id":"root"},"pms":{"connection_id":conn.id,"folder_id":"project-folder"}}}
    response=client.put(ROOT,headers=superuser_headers,json=payload)
    assert response.status_code==200,response.text
    assert response.json()["routes"]["pms"]["folder_name"]=="Verified folder"
    assert client.put(ROOT,headers=superuser_headers,json=payload).status_code==409
    payload["revision"]=response.json()["revision"]
    payload["routes"]["pms"]["connection_id"]=other.id
    assert client.put(ROOT,headers=superuser_headers,json=payload).status_code==404
    db.expire_all()
    assert db.get(StoragePolicy,1).routes["pms"]["connection_id"]==conn.id


@pytest.mark.parametrize("module",["hrms","crm","pms","sales","finance","interns","shared"])
def test_verified_upload_retains_original_locator_after_folder_change(db,storage_root,monkeypatch,module):
    conn,policy=cloud(db)
    uploaded={}
    def upload(db,c,folder,name,content,mime):
        uploaded.update(connection=c.id,folder=folder,content=content)
        return "remote-qa-id"
    monkeypatch.setattr(providers,"upload",upload)
    monkeypatch.setattr(providers,"download",lambda db,c,remote:uploaded["content"])
    path=storage_root/module/"attachment.pdf";path.parent.mkdir();path.write_bytes(b"%PDF-1.4 retained bytes")
    persist_file(str(path),db=db,company=1,module=module)
    assert path.is_file()  # Never remove staging before the business transaction commits.
    row=locator(path,db,1)
    assert row.status=="cloud" and row.remote_id=="remote-qa-id"
    db.commit()
    assert not path.exists()
    policy.routes={"default":{"connection_id":conn.id,"folder_id":"different-folder"}}
    db.commit()
    db.info["file_download_company"]=1
    assert Path(materialize_file(str(path),db=db)).read_bytes()==uploaded["content"]
    assert row.folder_id=="qa-folder"
    assert row.sha256==hashlib.sha256(uploaded["content"]).hexdigest()


def test_failed_cloud_upload_retains_bytes_and_retry_succeeds(client,db,storage_root,superuser_headers,monkeypatch):
    cloud(db)
    path=storage_root/"crm"/"proof.pdf";path.parent.mkdir();path.write_bytes(b"%PDF-1.4 proof")
    monkeypatch.setattr(providers,"upload",lambda *args: (_ for _ in ()).throw(HTTPException(502,"provider unavailable")))
    persist_file(str(path),db=db,company=1,module="crm")
    db.commit()
    row=locator(path,db,1)
    assert row.status=="pending" and path.read_bytes()==b"%PDF-1.4 proof"
    monkeypatch.setattr(providers,"upload",lambda *args:"retried-file")
    monkeypatch.setattr(providers,"download",lambda *args:b"%PDF-1.4 proof")
    response=client.post(ROOT+f"/files/{row.id}/retry",headers=superuser_headers)
    assert response.status_code==200,response.text
    assert response.json()["status"]=="cloud"
    db.expire_all()
    assert db.get(StorageObject,row.id).remote_id=="retried-file"


def test_employee_photos_stay_local_and_legacy_files_stay_unchanged(db,storage_root,monkeypatch):
    cloud(db)
    monkeypatch.setattr(providers,"upload",lambda *args:pytest.fail("Employee photo must never leave the server"))
    for relative in ("photos/employee.png","_private/profiles/1/1/profile.png"):
        path=storage_root/relative;path.parent.mkdir(parents=True);path.write_bytes(b"photo")
        persist_file(str(path),db=db,company=1,module="hrms")
        db.commit()
        assert path.read_bytes()==b"photo" and locator(path,db,1) is None
    legacy=storage_root/"old.pdf";legacy.write_bytes(b"legacy")
    db.info["file_download_company"]=1
    assert Path(materialize_file(str(legacy),db=db)).read_bytes()==b"legacy"


def test_rollback_and_checksum_failure_do_not_delete_server_file(db,storage_root,monkeypatch):
    cloud(db)
    path=storage_root/"rollback.pdf";path.write_bytes(b"original")
    monkeypatch.setattr(providers,"upload",lambda *args:"uploaded")
    monkeypatch.setattr(providers,"download",lambda *args:b"original")
    persist_file(str(path),db=db,company=1,module="crm")
    db.rollback()
    assert path.read_bytes()==b"original" and locator(path,db,1) is None
    monkeypatch.setattr(providers,"download",lambda *args:b"different")
    persist_file(str(path),db=db,company=1,module="crm");db.commit()
    assert path.read_bytes()==b"original" and locator(path,db,1).status=="pending"


def test_native_crm_upload_is_registered(client,db,storage_root,superuser_headers):
    response=client.post("/api/v1/crm/file-workspace/upload",headers=superuser_headers,files={"file":("storage-native.pdf",b"%PDF-1.4 native upload","application/pdf")})
    assert response.status_code==201,response.text
    rows=client.get(ROOT+"/files",headers=superuser_headers)
    assert rows.status_code==200,rows.text
    assert any(r["module"]=="crm" and r["status"]=="local" for r in rows.json()["items"])


def test_generated_pdf_and_spreadsheet_are_archived(db,storage_root):
    from app.services.file_storage_exports import archive
    token=context.set({"storage_session":db,"actor":{"access_company":1,"user_id":1,"access_module":"hrms"}})
    try:
        archive(b"%PDF-1.4 report",'attachment; filename="report.pdf"')
        archive(b"a,b\n1,2",'attachment; filename="report.csv"')
    finally: context.reset(token)
    rows=db.query(StorageObject).filter_by(organization_id=1).all()
    assert {r.filename for r in rows}=={"report.pdf","report.csv"}
    assert {r.module for r in rows}=={"hrms"}


def test_oauth_callback_is_one_time_and_credentials_stay_encrypted(client,db,superuser_headers,monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    monkeypatch.setattr(settings,"FILES_GOOGLE_CLIENT_ID","test-client-id")
    monkeypatch.setattr(settings,"FILES_GOOGLE_CLIENT_SECRET","test-secret")
    monkeypatch.setattr(settings,"BACKEND_PUBLIC_URL","http://127.0.0.1:1534")
    monkeypatch.setattr(settings,"ENVIRONMENT","test")
    response=client.post(ROOT+"/connect",headers=superuser_headers,json={"provider":"google_drive"})
    assert response.status_code==200,response.text
    fields=parse_qs(urlsplit(response.json()["authorize_url"]).query)
    assert fields["code_challenge_method"]==["S256"]
    assert fields["scope"]==["https://www.googleapis.com/auth/drive.file"]
    state=fields["state"][0]
    row=db.query(StorageOAuthState).one()
    assert row.id!=state and "verifier" not in row.encrypted_value
    monkeypatch.setattr(providers,"tokens",lambda *args:{"access_token":"private-test-token","refresh_token":"private-refresh-token","expires_in":3600})
    monkeypatch.setattr(providers,"account_info",lambda *args:"owner@example.test")
    response=client.get(ROOT+"/oauth/callback",params={"state":state,"code":"provider-code"},follow_redirects=False)
    assert response.status_code==303,response.text
    conn=db.query(StorageConnection).one()
    assert conn.connected and "private-test-token" not in conn.encrypted_value
    public=client.get(ROOT,headers=superuser_headers).text
    assert "private-test-token" not in public and "private-refresh-token" not in public
    assert client.get(ROOT+"/oauth/callback",params={"state":state,"code":"provider-code"}).status_code==400


def test_non_admin_cannot_configure_storage(client,db,superuser_headers):
    from tests.test_crm_lead_assignment import employee_account
    user,_=employee_account(db,"storage-non-admin")
    response=client.post("/api/v1/auth/login",json={"email":user.email,"password":"Sales@123456"})
    headers={"Authorization":"Bearer "+response.json()["access_token"]}
    assert client.get(ROOT,headers=headers).status_code==403
    assert client.put(ROOT,headers=headers,json={"revision":0,"enabled":False}).status_code==403


@pytest.mark.parametrize("kind",["google_drive","box","onedrive"])
def test_provider_upload_uses_native_binary_protocol(db,monkeypatch,kind):
    from types import SimpleNamespace
    conn,_=cloud(db,kind)
    calls=[]
    def send(method,url,headers=None,body=None,**kwargs):
        calls.append((method,url,headers,body))
        result={"entries":[{"id":"file-123"}]} if kind=="box" else {"id":"file-123"}
        import json
        return SimpleNamespace(body=json.dumps(result).encode(),status=201)
    monkeypatch.setattr(providers,"request",send)
    assert providers.upload(db,conn,"chosen-folder","report.pdf",b"%PDF-raw-bytes","application/pdf")=="file-123"
    method,url,headers,body=calls[0]
    assert b"%PDF-raw-bytes" in body and "Bearer " in headers["Authorization"]
    if kind=="google_drive": assert '"parents": ["chosen-folder"]' in body.decode() and "uploadType=multipart" in url
    elif kind=="box": assert body.index(b'name="attributes"')<body.index(b'name="file"') and "upload.box.com" in url
    else: assert method=="PUT" and "items/chosen-folder:/" in url and body==b"%PDF-raw-bytes"


def test_provider_redirect_never_forwards_credentials_to_untrusted_host(db,monkeypatch):
    from types import SimpleNamespace
    conn,_=cloud(db,"box")
    monkeypatch.setattr(providers,"request",lambda *args,**kwargs:SimpleNamespace(status=302,headers={"location":"https://attacker.example/file"}))
    with pytest.raises(HTTPException,match="unsupported host"):
        providers.download(db,conn,"file-123")


def test_quote_pdf_is_registered_without_changing_business_reference(client,db,storage_root,superuser_headers):
    quote=client.post("/api/v1/crm/quotes",headers=superuser_headers,json={"quoteNumber":"STORAGE-QA-PDF","issueDate":"2026-11-04","expiryDate":"2026-12-04"})
    assert quote.status_code==201,quote.text
    response=client.get(f"/api/v1/crm/quotes/{quote.json()['id']}/pdf",headers=superuser_headers)
    assert response.status_code==200,response.text
    rows=db.query(StorageObject).filter_by(module="crm").all()
    assert len(rows)==1 and rows[0].sha256==hashlib.sha256(response.content).hexdigest()
    assert rows[0].relative_path.startswith("crm/quotations/")


def test_invoice_pdf_is_registered_and_invoice_values_are_preserved(client,db,storage_root,superuser_headers):
    from tests.srm_test_utils import create_sales_order
    order=create_sales_order(client,superuser_headers)
    response=client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}",headers=superuser_headers)
    assert response.status_code==201,response.text
    before=response.json()
    response=client.get(f"/api/v1/srm/invoices/{before['id']}/pdf",headers=superuser_headers)
    assert response.status_code==200,response.text
    row=db.query(StorageObject).filter_by(module="sales").one()
    assert row.sha256==hashlib.sha256(response.content).hexdigest()
    after=client.get(f"/api/v1/srm/invoices/{before['id']}",headers=superuser_headers).json()
    for key in ("invoice_number","total_amount","paid_amount","balance_amount","status"):
        assert after[key]==before[key]


def test_google_client_json_loads_only_server_side(tmp_path,monkeypatch):
    import json
    path=tmp_path/"client.json"
    path.write_text(json.dumps({"web":{"client_id":"file-client-id","client_secret":"private-file-secret"}}))
    monkeypatch.setattr(settings,"FILES_GOOGLE_CLIENT_JSON",str(path))
    monkeypatch.setattr(settings,"BACKEND_PUBLIC_URL","http://localhost:1534")
    monkeypatch.setattr(settings,"ENVIRONMENT","test")
    assert providers.app_config("google_drive")["ready"]
    path.write_text("invalid-json")
    assert not providers.app_config("google_drive")["ready"]


def test_dropbox_binary_folder_pagination_and_stable_ids(db,monkeypatch):
    import json
    from types import SimpleNamespace
    conn,_=cloud(db,"dropbox")
    calls=[]
    def send(method,url,headers=None,body=None,**kwargs):
        calls.append((method,url,headers,body))
        if url.endswith("files/download"): return SimpleNamespace(body=b"binary-qa")
        if url.endswith("files/get_metadata"): data={".tag":"folder","id":"id:folder_123","path_lower":"/renamed-folder","name":"Renamed"}
        elif url.endswith("files/upload"):
            assert json.loads(headers["Dropbox-API-Arg"])["path"].startswith("/renamed-folder/")
            assert body==b"binary-qa" and headers["Content-Type"]=="application/octet-stream"
            data={"id":"id:file_123"}
        elif url.endswith("files/create_folder_v2"):
            assert json.loads(body)["path"]=="/renamed-folder/Child"
            data={"metadata":{"id":"id:child_123","name":"Child"}}
        elif url.endswith("users/get_current_account"): data={"email":"qa@example.test"}
        elif url.endswith("list_folder/continue"):
            assert json.loads(body)=={"cursor":"opaque-page"}
            data={"entries":[],"has_more":False}
        else:
            assert json.loads(body)["path"]==""
            data={"entries":[{".tag":"folder","id":"id:folder_123","name":"Folder"},{".tag":"file","id":"id:file_123","name":"file"}],"has_more":True,"cursor":"opaque-page"}
        return SimpleNamespace(body=json.dumps(data).encode())
    monkeypatch.setattr(providers,"request",send)
    assert providers.account_info(db,conn)=="qa@example.test"
    page=providers.folders(db,conn,"root")
    assert page["items"]==[{"id":"id:folder_123","name":"Folder"}]
    assert providers.folders(db,conn,"root",page["cursor"])["cursor"] is None
    assert providers.folder_info(db,conn,"id:folder_123")["name"]=="Renamed"
    assert providers.create_folder(db,conn,"id:folder_123","Child")["id"]=="id:child_123"
    assert providers.upload(db,conn,"id:folder_123","report.pdf",b"binary-qa","application/pdf")=="id:file_123"
    assert providers.download(db,conn,"id:file_123")==b"binary-qa"
    assert json.loads(calls[-1][2]["Dropbox-API-Arg"])["path"]=="id:file_123"
    with pytest.raises(HTTPException): providers.download(db,conn,"https://attacker.test/file")


def test_dropbox_oauth_requests_offline_access_and_pkce(client,superuser_headers,monkeypatch):
    from urllib.parse import urlsplit,parse_qs
    monkeypatch.setattr(settings,"FILES_DROPBOX_CLIENT_ID","qa-client")
    monkeypatch.setattr(settings,"FILES_DROPBOX_CLIENT_SECRET","qa-private")
    response=client.post(ROOT+"/connect",headers=superuser_headers,json={"provider":"dropbox"})
    assert response.status_code==200,response.text
    query=parse_qs(urlsplit(response.json()["authorize_url"]).query)
    assert query["token_access_type"]==["offline"]
    assert query["code_challenge_method"]==["S256"]
    assert "files.content.write" in query["scope"][0]


def test_primary_project_storage_rejects_other_tenant_and_disconnected_drive(db, storage_root, monkeypatch):
    from app.services.file_storage import require_project_drive
    monkeypatch.setattr(settings, "PMS_GOOGLE_DRIVE_REQUIRED", True)
    other, _ = cloud(db, company=2)
    policy = StoragePolicy(organization_id=1, enabled=True, routes={"default": {"connection_id": other.id, "folder_id": "other-tenant"}})
    db.add(policy); db.commit()
    with pytest.raises(HTTPException) as exc:
        require_project_drive(db, 1)
    assert exc.value.status_code == 409
    own, _ = cloud(db)
    require_project_drive(db, 1)
    own.connected = False
    with pytest.raises(HTTPException):
        require_project_drive(db, 1)


def test_primary_project_failure_preserves_original_without_local_fallback(db, storage_root, monkeypatch):
    monkeypatch.setattr(settings, "PMS_GOOGLE_DRIVE_REQUIRED", True)
    cloud(db)
    path = storage_root / "pms" / "failed.pdf"
    path.parent.mkdir(); path.write_bytes(b"%PDF-original")
    monkeypatch.setattr(providers, "upload", lambda *args: "unverified-id")
    monkeypatch.setattr(providers, "download", lambda *args: b"wrong bytes")
    with pytest.raises(HTTPException) as exc:
        persist_file(str(path), db=db, company=1, module="pms")
    assert exc.value.status_code == 503
    db.rollback()
    assert path.read_bytes() == b"%PDF-original"


def test_cloud_read_does_not_recreate_server_copy(db, storage_root, monkeypatch):
    from app.services.file_storage import cloud_content
    monkeypatch.setattr(settings, "PMS_GOOGLE_DRIVE_REQUIRED", True)
    cloud(db)
    content = b"%PDF-private-project"
    monkeypatch.setattr(providers, "upload", lambda *args: "verified-id")
    monkeypatch.setattr(providers, "download", lambda *args: content)
    path = storage_root / "pms" / "verified.pdf"
    path.parent.mkdir(); path.write_bytes(content)
    persist_file(str(path), db=db, company=1, module="pms")
    assert path.exists()
    db.commit()
    assert not path.exists()
    assert cloud_content(str(path), db, 1)[0] == content
    assert not path.exists()
    assert cloud_content(str(path), db, 2) is None


def test_primary_project_upload_never_falls_back_without_business_context(storage_root, monkeypatch):
    monkeypatch.setattr(settings, "PMS_GOOGLE_DRIVE_REQUIRED", True)
    path = storage_root / "pms" / "unowned.pdf"
    path.parent.mkdir(); path.write_bytes(b"%PDF-unowned")
    from app.core.audit_context import context
    token = context.set(None)
    try:
        with pytest.raises(HTTPException) as exc:
            persist_file(str(path), module="pms")
        assert exc.value.status_code == 409
        assert path.exists()
    finally:
        context.reset(token)


def test_private_note_chat_response_does_not_mint_links_or_cache_bytes(db, storage_root, monkeypatch):
    from app.core.storage import private_attachment_response
    conn, _ = cloud(db)
    content = b"private chat bytes"
    path = storage_root / "pms" / "chat" / "private.txt"
    path.parent.mkdir(parents=True)
    row = StorageObject(organization_id=1, module="pms", relative_path="pms/chat/private.txt", filename="private.txt", content_type="text/plain", size=len(content), sha256=hashlib.sha256(content).hexdigest(), connection_id=conn.id, provider="google_drive", folder_id="qa-folder", remote_id="private-id", status="cloud", versions=[])
    db.add(row); db.commit()
    monkeypatch.setattr(providers, "download", lambda *args: content)
    token = context.set({"actor": {"access_company": 1}, "storage_session": db})
    try:
        response = private_attachment_response(str(path), db=db, filename="private.txt", media_type="text/plain")
        assert response.body == content
        assert context.get()["file_response_path"] == str(path)
        assert "location" not in response.headers
        assert response.headers["cache-control"] == "private, no-store"
        assert not path.exists()
    finally:
        context.reset(token)
