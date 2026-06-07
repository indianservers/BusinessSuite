from app.apps.fam.models import FAMAuditLog, FAMCompanyFinancialSettings
from tests.fam_test_utils import fam_admin_headers


def test_fam_settings_get_update_and_audit(client, db):
    headers = fam_admin_headers(client, db)

    response = client.get("/api/v1/fam/settings", headers=headers)
    assert response.status_code == 200
    assert response.json()["country_code"] == "IN"
    assert response.json()["base_currency"] == "INR"

    response = client.put("/api/v1/fam/settings", headers=headers, json={
        "legal_name": "Acme India Private Limited",
        "trade_name": "Acme India",
        "country_code": "IN",
        "base_currency": "INR",
        "financial_year_start_month": 4,
        "books_start_date": "2026-04-01",
        "gstin": "29ABCDE1234F1Z5",
        "pan": "ABCDE1234F",
        "tan": "BLRA12345B",
        "cin": "U72900KA2026PTC123456",
        "state_code": "29",
        "registered_address": "Bengaluru",
        "decimal_places": 2,
    })
    assert response.status_code == 200, response.text
    assert response.json()["legal_name"] == "Acme India Private Limited"
    assert db.query(FAMCompanyFinancialSettings).filter_by(legal_name="Acme India Private Limited").first()
    assert db.query(FAMAuditLog).filter_by(record_type="settings", action="UPDATE").first()


def test_fam_settings_reject_invalid_tax_placeholders(client, db):
    headers = fam_admin_headers(client, db)
    response = client.put("/api/v1/fam/settings", headers=headers, json={
        "legal_name": "Acme",
        "trade_name": "Acme",
        "country_code": "IN",
        "base_currency": "INR",
        "financial_year_start_month": 4,
        "books_start_date": "2026-04-01",
        "gstin": "X",
        "pan": "ABCDE1234F",
        "tan": "BLRA12345B",
        "cin": "",
        "state_code": "29",
        "registered_address": "",
        "decimal_places": 2,
    })
    assert response.status_code == 422
