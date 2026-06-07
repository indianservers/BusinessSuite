from app.apps.saas.models import DeveloperAPIKey
from phase10_test_utils import auth_headers


def test_developer_api_key_is_shown_once_and_hash_only_is_stored(client, db):
    headers = auth_headers(client, db, permissions=["developer_manage"])
    create = client.post("/api/v1/developer/api-keys", json={"name": "ERP Sync", "scopes": ["crm.read"]}, headers=headers)
    assert create.status_code == 201, create.text
    assert create.json()["api_key"].startswith("bs_")
    item = db.query(DeveloperAPIKey).first()
    assert item.key_hash
    assert create.json()["api_key"] not in item.key_hash

    listing = client.get("/api/v1/developer/api-keys", headers=headers)
    assert "api_key" not in listing.text
    revoke = client.delete(f"/api/v1/developer/api-keys/{item.id}", headers=headers)
    assert revoke.status_code == 204
    assert item.status == "revoked"
