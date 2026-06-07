from phase10_test_utils import auth_headers


def test_tenant_company_settings_flags_subscription_and_usage(client, db):
    headers = auth_headers(client, db, permissions=["tenant_view", "tenant_admin"])
    settings = client.put("/api/v1/admin/company-settings", json={"company_name": "Vyapara Suite", "base_currency": "INR", "timezone": "Asia/Calcutta", "fiscal_year_start_month": 4, "tax_defaults": {"gst": "registered"}, "business_hours": {"weekday": "9-6"}, "numbering_settings": {"quote": "QT"}}, headers=headers)
    assert settings.status_code == 200, settings.text
    assert settings.json()["company_name"] == "Vyapara Suite"

    flag = client.put("/api/v1/admin/feature-flags", json={"feature_key": "portals", "enabled": True}, headers=headers)
    assert flag.status_code == 200
    plans = client.get("/api/v1/admin/subscription-plans", headers=headers)
    assert plans.status_code == 200
    assert {item["code"] for item in plans.json()["items"]} >= {"starter", "professional", "enterprise", "ultimate"}
    usage = client.get("/api/v1/admin/usage", headers=headers)
    assert usage.status_code == 200
