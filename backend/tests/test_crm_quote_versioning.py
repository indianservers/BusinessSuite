from app.apps.crm.models import CRMQuoteVersion


def test_crm_quote_new_version_snapshots_existing_quote(client, db, superuser_headers):
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-VER-001",
        "issueDate": "2026-06-01",
        "expiryDate": "2026-06-30",
    })
    quote_id = quote.json()["id"]
    response = client.post(f"/api/v1/crm/quotes/{quote_id}/new-version", headers=superuser_headers)
    assert response.status_code == 201, response.text
    assert response.json()["quote"]["versionNumber"] == 2
    assert db.query(CRMQuoteVersion).filter(CRMQuoteVersion.quote_id == quote_id).count() == 1
