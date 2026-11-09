from datetime import timedelta
from urllib.parse import urlsplit, parse_qs
import pytest
from app.models.file_storage import StorageConnection, StorageOAuthState
from app.services import file_storage_providers as providers
from app.core.config import settings
from app.apps.power_apps.integrations.vault import CredentialVault

ROOT = "/api/v1/files-storage"


@pytest.fixture
def oauth(monkeypatch):
    monkeypatch.setattr(settings,"FRONTEND_PUBLIC_URL","https://suite.example.test")
    monkeypatch.setattr(settings,"BACKEND_CORS_ORIGINS",["https://suite.example.test","https://legacy.example.test"])
    monkeypatch.setattr(providers,"app_config",lambda kind:{"ready":True,"label":kind,"client_id":"fixture-client",
        "redirect_uri":"https://api.example.test/api/v1/files-storage/oauth/callback",
        "authorize":"https://provider.example.test/authorize","scopes":["files","offline_access"]})
    monkeypatch.setattr(providers,"tokens",lambda *a:{"access_token":"private-test-access","refresh_token":"private-test-refresh","expires_in":3600})
    monkeypatch.setattr(providers,"account_info",lambda *a:"personal@example.test")


def start(client, headers, provider="google_drive", origin="https://suite.example.test"):
    return client.post(ROOT+"/notes/connect",headers={**headers,"Origin":origin},json={"source":"crm","provider":provider})


@pytest.mark.parametrize("provider",["google_drive","onedrive"])
def test_notes_authorization_uses_pkce_and_returns_only_to_initiating_window(client,db,superuser_headers,oauth,provider):
    response=start(client,superuser_headers,provider,"https://legacy.example.test")
    assert response.status_code==200,response.text
    data=response.json();fields=parse_qs(urlsplit(data["authorize_url"]).query)
    assert fields["code_challenge_method"]==["S256"] and fields["prompt"]==["consent select_account" if provider=="google_drive" else "select_account"]
    assert data["callback_origin"]=="https://api.example.test"
    row=db.query(StorageOAuthState).one();value=CredentialVault.decrypt(row)
    assert value["purpose"]=="notes" and value["module"]=="crm" and value["request_id"]==data["request_id"]
    assert "verifier" not in row.encrypted_value
    state=fields["state"][0]
    callback=client.get(ROOT+"/oauth/callback",params={"state":state,"code":"fixture-code"},follow_redirects=False)
    assert callback.status_code==200,callback.text
    assert '"status": "connected"' in callback.text and "https://legacy.example.test" in callback.text
    assert data["request_id"] in callback.text and "window.opener.postMessage" in callback.text
    assert "private-test-access" not in callback.text and "private-test-refresh" not in callback.text
    assert "frame-ancestors 'none'" in callback.headers["content-security-policy"]
    account=db.query(StorageConnection).one();assert account.connected and account.account=="personal@example.test"
    assert account.created_by==row.user_id and account.organization_id==row.organization_id
    assert client.get(ROOT+"/oauth/callback",params={"state":state,"code":"fixture-code"}).status_code==400


def test_notes_denial_and_expiration_do_not_connect_accounts(client,db,superuser_headers,oauth):
    data=start(client,superuser_headers).json();state=parse_qs(urlsplit(data["authorize_url"]).query)["state"][0]
    response=client.get(ROOT+"/oauth/callback",params={"state":state,"error":"access_denied"})
    assert response.status_code==200 and '"status": "denied"' in response.text
    assert not db.query(StorageConnection).one().connected
    data=start(client,superuser_headers).json();state=parse_qs(urlsplit(data["authorize_url"]).query)["state"][0]
    row=db.query(StorageOAuthState).filter_by(consumed_at=None).one();row.expires_at=providers.now()-timedelta(seconds=1);db.commit()
    assert client.get(ROOT+"/oauth/callback",params={"state":state,"code":"code"}).status_code==400
    assert not any(a.connected for a in db.query(StorageConnection).all())


def test_notes_connect_rejects_unconfigured_provider_and_foreign_origin(client,db,superuser_headers,oauth,monkeypatch):
    assert start(client,superuser_headers,origin="https://attacker.example").status_code==403
    assert start(client,superuser_headers,provider="dropbox").status_code==422
    monkeypatch.setattr(providers,"app_config",lambda kind:{"ready":False})
    assert start(client,superuser_headers).status_code==503
    assert db.query(StorageOAuthState).count()==0 and db.query(StorageConnection).count()==0


def test_notes_user_can_connect_without_settings_access_and_is_rechecked_on_callback(client,db,superuser_headers,oauth):
    from tests.test_crm_lead_assignment import employee_account
    from app.access.models import AccessPolicy, AccessMembership
    user,_=employee_account(db,"notes-personal-storage")
    policy=AccessPolicy(user_id=user.id,company_id=1,status="active",grants={"crm":{"enabled":True,"actions":["view","export"],"permissions":["crm_view"],"scope":"own"}})
    db.add(policy);db.commit()
    auth=client.post("/api/v1/auth/login",json={"email":user.email,"password":"Sales@123456"})
    headers={"Authorization":"Bearer "+auth.json()["access_token"]}
    assert client.get(ROOT,headers=headers).status_code==403
    response=start(client,headers);assert response.status_code==200,response.text
    state=parse_qs(urlsplit(response.json()["authorize_url"]).query)["state"][0]
    result=client.get(ROOT+"/oauth/callback",params={"state":state,"code":"fixture-code"})
    assert result.status_code==200,result.text
    account=db.query(StorageConnection).one()
    assert account.created_by==user.id
    assert CredentialVault.decrypt(account)["notes_owner_id"]==user.id
    assert client.get(ROOT,headers=superuser_headers).json()["connections"]==[]
    assert client.get(ROOT+f"/connections/{account.id}/folders",headers=superuser_headers).status_code==404
    # A grant revoked after initiating consent cannot issue a connected account.
    response=start(client,headers);assert response.status_code==200,response.text
    state=parse_qs(urlsplit(response.json()["authorize_url"]).query)["state"][0]
    policy.grants={"crm":{"enabled":True,"actions":["view"],"permissions":["crm_view"],"scope":"own"}};db.commit()
    assert client.get(ROOT+"/oauth/callback",params={"state":state,"code":"fixture-code"}).status_code==403
    assert sum(bool(a.connected) for a in db.query(StorageConnection).all())==1
