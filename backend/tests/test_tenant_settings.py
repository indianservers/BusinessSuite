from phase10_test_utils import auth_headers


def test_tenant_company_settings_flags_subscription_and_usage(client, db):
    headers = auth_headers(client, db, permissions=["tenant_view", "tenant_admin"], superuser=True)
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


def test_default_plan_bootstrap_is_guarded_idempotent_and_preserves_customization(client, db):
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    ordinary = auth_headers(client, db, email="ordinary-plan-admin@example.com", permissions=["tenant_view", "tenant_admin"])
    denied = client.get("/api/v1/admin/subscription-plans", headers=ordinary)
    assert denied.status_code == 403
    assert db.query(TenantSubscriptionPlan).count() == 0
    assert db.query(TenantSubscription).count() == 0

    root = auth_headers(client, db, email="root-plan-admin@example.com", permissions=["tenant_view", "tenant_admin"], superuser=True)
    for _ in range(2):
        response = client.get("/api/v1/admin/subscription-plans", headers=root)
        assert response.status_code == 200, response.text
    assert db.query(TenantSubscriptionPlan).count() == 4
    assert db.query(TenantSubscription).filter(TenantSubscription.company_id.is_(None)).count() == 1
    assert db.query(TenantSubscription).filter(TenantSubscription.company_id.is_not(None)).count() == 0

    customized = db.query(TenantSubscriptionPlan).filter_by(code="ultimate").one()
    customized.name = "Installation custom edition"
    customized.features_json = ["custom-feature"]
    db.commit()
    response = client.get("/api/v1/admin/subscription-plans", headers=root)
    assert response.status_code == 200, response.text
    returned = next(row for row in response.json()["items"] if row["code"] == "ultimate")
    assert returned["name"] == "Installation custom edition"
    assert returned["features_json"] == ["custom-feature"]
    subscription = client.get("/api/v1/admin/subscription", headers=root)
    assert subscription.status_code == 200, subscription.text
    assert subscription.json()["company_id"] is None
