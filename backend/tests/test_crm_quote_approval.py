from app.apps.crm.models import CRMQuoteApproval


def test_crm_quote_submit_approve_and_reject_paths(client, db, superuser_headers):
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-APP-001",
        "issueDate": "2026-06-01",
        "expiryDate": "2026-06-30",
    })
    quote_id = quote.json()["id"]

    submit = client.post(f"/api/v1/crm/quotes/{quote_id}/submit", headers=superuser_headers, json={"comments": "Discount review"})
    assert submit.status_code == 200, submit.text
    assert submit.json()["approvalStatus"] == "pending"
    assert db.query(CRMQuoteApproval).filter(CRMQuoteApproval.quote_id == quote_id, CRMQuoteApproval.status == "pending").count() == 1

    approve = client.post(f"/api/v1/crm/quotes/{quote_id}/approve", headers=superuser_headers, json={"comments": "Approved"})
    assert approve.status_code == 200, approve.text
    assert approve.json()["approvalStatus"] == "approved"
    assert db.query(CRMQuoteApproval).filter(CRMQuoteApproval.quote_id == quote_id, CRMQuoteApproval.status == "approved").count() == 1
