from app.models.user import User
from app.access.models import AccessAudit
from tests.test_suite_access import access_account, login, secure
ROOT = "/api/v1/access/control/super-admins"

def test_promotion_security_and_audit(client, db, access_account, superuser_headers):
    payload = {"email": access_account.email, "reason": "Authorize suite administrator"}
    assert client.post(ROOT, json=payload, headers=login(client)).status_code == 403
    assert client.post(ROOT, json=payload, headers=superuser_headers).status_code == 403
    db.refresh(access_account)
    assert not access_account.is_superuser
    result = client.post(ROOT, json=payload, headers=secure(client, superuser_headers))
    assert result.status_code == 200, result.text
    db.refresh(access_account)
    assert access_account.is_superuser
    assert db.query(AccessAudit).filter_by(operation="super_admin.granted", target_id=access_account.id).count() == 1
    for module in ("crm", "project_management", "hrms"):
        assert client.post("/api/v1/auth/login", json={"email":access_account.email,"password":"Sales@123456","module":module}).status_code == 200

def test_new_and_inactive_accounts(client, db, access_account, superuser_headers):
    headers = secure(client, superuser_headers)
    payload = {"email":"new.super@example.com", "reason":"New suite administrator"}
    assert client.post(ROOT, json=payload, headers=headers).status_code == 422
    result = client.post(ROOT, json={**payload,"password":"Secure@12345678"}, headers=headers)
    assert result.status_code == 200, result.text
    assert db.query(User).filter_by(email=payload["email"]).one().is_superuser
    assert client.post(ROOT, json=payload, headers=headers).status_code == 409
    access_account.is_active=False; db.commit()
    assert client.post(ROOT, json={**payload,"email":access_account.email}, headers=headers).status_code == 409

def test_logo_validation(client, db, access_account, superuser_headers, tmp_path, monkeypatch):
    import io
    from PIL import Image
    from app.core.config import settings
    monkeypatch.setattr(settings,"UPLOAD_DIR",str(tmp_path))
    monkeypatch.setattr("app.core.storage.persist_file",lambda path:None)
    url="/api/v1/access/enterprise/branding/logo?companyId=1"
    assert client.post(url,headers=login(client),files={"file":("x.png",b"invalid","image/png")}).status_code==403
    assert client.post(url,headers=superuser_headers,files={"file":("x.png",b"invalid","image/png")}).status_code==422
    content=io.BytesIO();Image.new("RGB",(10,10)).save(content,format="PNG")
    result=client.post(url,headers=superuser_headers,files={"file":("x.png",content.getvalue(),"image/png")})
    assert result.status_code==200,result.text
    from app.core.storage import normalize_upload_references
    assert normalize_upload_references(result.json())["url"].startswith("/uploads/branding/")

    saved=client.put("/api/v1/access/enterprise/policies",headers=secure(client,superuser_headers),json={"companyId":1,"kind":"branding","key":"theme","version":0,"reason":"Configure workspace identity","values":{"appName":"Indian Servers Pvt Limited","logoPath":result.json()["url"]}})
    assert saved.status_code==200,saved.text
    branding=client.get("/api/v1/access/enterprise/branding?companyId=1",headers=superuser_headers)
    assert branding.status_code==200
    assert branding.json()["values"]["appName"]=="Indian Servers Pvt Limited"
    assert normalize_upload_references(branding.json())["values"]["logoPath"].startswith("/uploads/branding/")


from tests.test_intern_signup_settings import firebase_identity
import pytest
import time


@pytest.mark.parametrize("provider", ["google.com", "microsoft.com"])
def test_social_step_up_can_promote(client, db, access_account, superuser_headers, firebase_identity, monkeypatch, provider):
    from app.core.config import settings
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "test-project")
    identity = firebase_identity(email="testadmin@test.com", firebase={"sign_in_provider": provider})
    result = client.post("/api/v1/access/step-up", json={"identity_token": identity}, headers=superuser_headers)
    assert result.status_code == 200, result.text
    headers = {**superuser_headers, "X-Access-Step-Up": result.json()["token"]}
    result = client.post(ROOT, json={"email": access_account.email, "reason": "Requested administrator access"}, headers=headers)
    assert result.status_code == 200, result.text
    db.refresh(access_account)
    assert access_account.is_superuser


@pytest.mark.parametrize("changes", [
    {"email": "someone-else@example.com"},
    {"auth_time": int(time.time()) - 600},
    {"email_verified": False},
    {"firebase": {"sign_in_provider": "password"}},
    {"aud": "another-project"},
])
def test_social_step_up_rejects_invalid_identity(client, superuser_headers, firebase_identity, monkeypatch, changes):
    from app.core.config import settings
    monkeypatch.setattr(settings, "FIREBASE_PROJECT_ID", "test-project")
    token = firebase_identity(email="testadmin@test.com", **changes) if "email" not in changes else firebase_identity(**changes)
    result = client.post("/api/v1/access/step-up", json={"identity_token": token}, headers=superuser_headers)
    assert result.status_code == 403, result.text
