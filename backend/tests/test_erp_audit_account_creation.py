from tests.test_suite_access import ROOT, access_account, login, secure


def test_added_user_can_login_but_starts_without_modules_and_duplicate_is_rejected(client, db, access_account, superuser_headers):
    headers = secure(client, superuser_headers)
    payload = {"companyId": 1, "name": "Synthetic QA operator", "email": "audit.operator@example.com", "password": "Sales@123456", "invite": False, "reason": "Create isolated QA account"}
    response = client.post(ROOT + "/users", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["user"]["moduleCount"] == 0 and data["invitationToken"] is None and data["delivery"] is None
    own = login(client, payload["email"])
    access = client.get(ROOT + "/me", headers=own)
    assert access.status_code == 200
    assert not any(grant.get("enabled") for grant in access.json()["grants"].values())
    assert client.get("/api/v1/crm/lead-management/leads", headers=own).status_code == 403
    assert client.get(ROOT + "/users", headers=own).status_code == 403
    duplicate = client.post(ROOT + "/users", headers=headers, json=payload)
    assert duplicate.status_code == 409
    from app.models.user import User
    assert db.query(User).filter_by(email=payload["email"]).count() == 1
