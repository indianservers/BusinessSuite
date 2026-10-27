from phase10_test_utils import auth_headers, invite_portal


def test_portal_sessions_are_separate_from_employee_auth_and_customer_partner_are_isolated(client, db):
    headers = auth_headers(client, db)
    customer = invite_portal(client, db, headers, "customer", "cust-sec@example.com", customer_id=601)
    partner = invite_portal(client, db, headers, "partner", "partner-sec@example.com", partner_id=701)

    assert client.get("/api/v1/customer-portal/me").status_code == 403
    assert client.get("/api/v1/customer-portal/me", headers={"Authorization": headers["Authorization"]}).status_code == 403
    assert client.get("/api/v1/customer-portal/me", headers={"X-Portal-Session": partner["one_time_session_token"]}).status_code == 403
    assert client.get("/api/v1/partner-portal/dashboard", headers={"X-Portal-Session": customer["one_time_session_token"]}).status_code == 403

def test_portal_file_capability_is_revoked_with_session(client, db, monkeypatch, tmp_path):
    import pytest
    from urllib.parse import urlsplit, parse_qs
    from fastapi import HTTPException
    from app.core.config import settings
    from app.core.audit_context import context
    from app.core.storage import signed_file_url, blob_token_path
    from app.apps.saas.api.router import _portal_session, portal_fingerprint
    from app.apps.saas.models import PortalSession

    headers = auth_headers(client, db)
    invited = invite_portal(client, db, headers, email="file-customer@example.com", customer_id=802)
    user = _portal_session(db, invited["one_time_session_token"], "customer")
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    state = context.set({"actor": {"portal_user_id": user.id, "access_company": 1,
        "access_portal_session": user._portal_session_id, "access_portal_grants": portal_fingerprint(db, user)}})
    try:
        url = signed_file_url(str(tmp_path / "invoice.pdf"))
    finally:
        context.reset(state)
    token = parse_qs(urlsplit(url).query)["token"][0]
    assert blob_token_path(token, db=db) == str(tmp_path / "invoice.pdf")
    db.get(PortalSession, user._portal_session_id).status = "revoked"
    db.flush()
    with pytest.raises(HTTPException):
        blob_token_path(token, db=db)
