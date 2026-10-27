from app.core.config import settings
from app.models.company import Company
from app.api.v1.auth import FirebaseLoginInput


def test_public_login_branding_only_exposes_configured_company(client, db, monkeypatch):
    row = Company(name="Master Company", legal_name="Private Legal Details", email="private@example.test", is_active=True)
    other = Company(name="Other tenant", is_active=True)
    db.add_all([row, other])
    db.commit()
    monkeypatch.setattr(settings, "LOGIN_COMPANY_ID", row.id)
    response = client.get("/api/v1/auth/branding", params={"companyId": other.id})
    assert response.status_code == 200, response.text
    assert response.json() == {"company_name": "Master Company"}
    row.name = "Renamed Company"
    db.commit()
    assert client.get("/api/v1/auth/branding").json() == {"company_name": "Renamed Company"}
    row.is_active = False
    db.commit()
    assert client.get("/api/v1/auth/branding").json() == {"company_name": None}


def test_firebase_suite_login_does_not_require_module():
    assert FirebaseLoginInput(token="x" * 30).module is None
