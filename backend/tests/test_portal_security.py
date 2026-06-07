from phase10_test_utils import auth_headers, invite_portal


def test_portal_sessions_are_separate_from_employee_auth_and_customer_partner_are_isolated(client, db):
    headers = auth_headers(client, db)
    customer = invite_portal(client, headers, "customer", "cust-sec@example.com", customer_id=601)
    partner = invite_portal(client, headers, "partner", "partner-sec@example.com", partner_id=701)

    assert client.get("/api/v1/customer-portal/me").status_code == 403
    assert client.get("/api/v1/customer-portal/me", headers={"Authorization": headers["Authorization"]}).status_code == 403
    assert client.get("/api/v1/customer-portal/me", headers={"X-Portal-Session": partner["one_time_session_token"]}).status_code == 403
    assert client.get("/api/v1/partner-portal/dashboard", headers={"X-Portal-Session": customer["one_time_session_token"]}).status_code == 403
