from app.apps.business_os.models import BOSEnabledModule


def _set_modules(client, headers, db, modules):
    db.query(BOSEnabledModule).delete()
    db.commit()
    response = client.put("/api/v1/business-os/modules", headers=headers, json={"enabled_modules": modules})
    assert response.status_code == 200


def test_dashboard_widgets_by_module_combination(client, db, superuser_headers):
    _set_modules(client, superuser_headers, db, ["fam"])
    response = client.get("/api/v1/business-os/dashboard", headers=superuser_headers)
    assert response.status_code == 200
    titles = {item["title"] for item in response.json()["widgets"]}
    assert {"Cash", "GST", "Trial Balance", "P&L", "Balance Sheet"}.issubset(titles)
    assert "Pipeline" not in titles

    _set_modules(client, superuser_headers, db, ["fam", "inventory"])
    response = client.get("/api/v1/business-os/dashboard", headers=superuser_headers)
    titles = {item["title"] for item in response.json()["widgets"]}
    assert {"Stock Value", "Low Stock", "COGS", "GRNI", "HSN Summary", "Gross Margin"}.issubset(titles)

    _set_modules(client, superuser_headers, db, ["crm", "srm"])
    response = client.get("/api/v1/business-os/dashboard", headers=superuser_headers)
    titles = {item["title"] for item in response.json()["widgets"]}
    assert {"Pipeline", "Won Deals", "Sales Orders", "Contracts", "Billing Plans", "Invoices", "Collections"}.issubset(titles)

    _set_modules(client, superuser_headers, db, ["fam", "inventory", "crm", "srm", "project_management", "hrms", "ai", "portals", "communication"])
    response = client.get("/api/v1/business-os/dashboard", headers=superuser_headers)
    titles = {item["title"] for item in response.json()["widgets"]}
    assert {"Lead-to-Cash", "Procure-to-Pay", "Project-to-Profit", "Inventory-to-Accounting", "Cash Flow", "Business Health Score"}.issubset(titles)


def test_reports_rbac_ai_and_customer_720_are_module_aware(client, db, superuser_headers):
    _set_modules(client, superuser_headers, db, ["fam"])
    reports = client.get("/api/v1/business-os/reports/catalog", headers=superuser_headers).json()["reports"]
    by_key = {item["key"]: item for item in reports}
    assert by_key["gst_summary"]["enabled"] is True
    assert by_key["inventory_valuation"]["enabled"] is False
    assert "Missing" in by_key["stock_cogs"]["reason"]

    rbac = client.get("/api/v1/business-os/rbac/catalog", headers=superuser_headers).json()["roles"]
    accounts = next(item for item in rbac if item["role"] == "Accounts Admin")
    inventory = next(item for item in rbac if item["role"] == "Inventory Manager")
    assert accounts["available"] is True
    assert inventory["available"] is False
    assert all(not permission.startswith("crm_") for item in rbac for permission in item["permissions"])

    ai = client.post("/api/v1/business-os/ai/ask", headers=superuser_headers, json={"question": "Show CRM pipeline"}).json()
    assert ai["allowed"] is False
    assert "CRM is not enabled" in ai["answer"]
    ai = client.post("/api/v1/business-os/ai/ask", headers=superuser_headers, json={"question": "Show GST and trial balance"}).json()
    assert ai["allowed"] is True

    customer = client.get("/api/v1/business-os/customer-720", headers=superuser_headers).json()
    assert [section["module"] for section in customer["sections"]] == ["fam"]

    _set_modules(client, superuser_headers, db, ["inventory", "fam"])
    reports = client.get("/api/v1/business-os/reports/catalog", headers=superuser_headers).json()["reports"]
    by_key = {item["key"]: item for item in reports}
    assert by_key["stock_cogs"]["enabled"] is True
    ai = client.post("/api/v1/business-os/ai/ask", headers=superuser_headers, json={"question": "Show stock value"}).json()
    assert ai["allowed"] is True
