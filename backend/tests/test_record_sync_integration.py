"""Run with pytest to exercise the real authentication/tenant middleware stack."""
def test_authenticated_employee_pilot_preserves_route_authorization(client, superuser_headers, db):
    from app.models.company import Company
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Sync integration", is_active=True)); db.commit()
    headers = {**superuser_headers, "X-Suite-Sync": "1"}
    first = client.get("/api/v1/employees/", headers=headers, params={"page": 1, "per_page": 25})
    assert first.status_code == 200, first.text
    assert first.headers.get("x-suite-cache") == "persist"
    assert first.headers.get("x-suite-sync-scope")
    assert "no-store" not in first.headers["cache-control"]
    second = client.get("/api/v1/employees/", headers={**headers, "If-None-Match": first.headers["etag"], "X-Suite-Sync-Cursor": first.headers["x-suite-sync-cursor"]}, params={"page": 1, "per_page": 25})
    assert second.status_code == 304, second.text
    from app.models.user import User, Role
    actor = db.query(User).filter(User.email == "testadmin@test.com").one()
    replacement = Role(name="sync_replacement_role", description="Role change test")
    db.add(replacement); db.flush(); actor.role_id = replacement.id; db.commit()
    changed = client.get("/api/v1/employees/", headers={**headers, "If-None-Match": first.headers["etag"], "X-Suite-Sync-Cursor": first.headers["x-suite-sync-cursor"]}, params={"page": 1, "per_page": 25})
    assert changed.status_code == 200
    assert changed.headers["x-suite-sync-mode"] == "full"
    assert "items" in changed.json()
    assert changed.headers["x-suite-sync-scope"] != first.headers["x-suite-sync-scope"]
    denied = client.get("/api/v1/employees/", headers={"X-Suite-Sync": "1", "If-None-Match": first.headers["etag"], "X-Suite-Sync-Cursor": first.headers["x-suite-sync-cursor"]})
    assert denied.status_code in (401, 403)
    assert "no-store" in denied.headers["cache-control"]
    assert "x-suite-cache" not in denied.headers

def test_unknown_or_sensitive_endpoints_remain_no_store(client, superuser_headers):
    response = client.get("/api/v1/auth/me", headers={**superuser_headers, "X-Suite-Sync": "1"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert "x-suite-cache" not in response.headers

def test_signed_private_links_keep_no_store_policy():
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from app.core.middleware.record_sync import RecordSyncMiddleware
    from app.core.middleware.storage import PrivateUploadURLMiddleware
    from app.core.middleware.security_headers import SecurityHeadersMiddleware
    app = FastAPI()
    @app.get('/api/v1/crm/leads')
    def records(request: Request):
        request.state.record_sync_scope = 'authorized-test-scope'
        return {'items': [{'id': 1, 'image': 'https://private.example.test/photo?X-Amz-Signature=redacted'}]}
    app.add_middleware(PrivateUploadURLMiddleware)
    app.add_middleware(RecordSyncMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    with TestClient(app) as client:
        response = client.get('/api/v1/crm/leads', headers={'X-Suite-Sync': '1'})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'private, no-store'
        assert 'x-suite-cache' not in response.headers

def test_versioned_lead_contact_edit_rejects_a_stale_write(client, superuser_headers, db):
    from app.models.company import Company, Branch
    if not db.get(Company, 1):
        db.add(Company(id=1, name="Sync conflict integration", is_active=True)); db.flush()
    branch = Branch(company_id=1, name="Sync conflict branch", code="SYNC-CONFLICT", is_active=True)
    db.add(branch); db.commit()
    headers = {**superuser_headers, "X-Suite-Organization": "1", "X-Suite-Branch": str(branch.id)}
    root = "/api/v1/crm/lead-management/leads"
    created = client.post(root, headers=headers, json={"values": {"full_name": "Sync conflict pilot", "email": "sync-pilot@example.com"}})
    assert created.status_code == 201, created.text
    lead = created.json()
    changed = client.patch(f"{root}/{lead['id']}", headers=headers, json={"version": lead["version"], "values": {"email": "changed-sync@example.com"}})
    assert changed.status_code == 200, changed.text
    stale = client.patch(f"{root}/{lead['id']}", headers=headers, json={"version": lead["version"], "values": {"email": "stale-sync@example.com"}})
    assert stale.status_code == 409, stale.text
    current = client.get(f"{root}/{lead['id']}", headers=headers)
    assert current.json()["email"] == "changed-sync@example.com"
