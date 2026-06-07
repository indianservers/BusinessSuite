from tests.test_fam_srm_invoice_posting import create_sent_srm_invoice


def test_fam_posts_srm_receipt_allocation_to_bill_allocation(client, db, superuser_headers):
    invoice = create_sent_srm_invoice(client, superuser_headers, customer_id=701, total=20000, tax=0)
    client.post(f"/api/v1/fam/integrations/srm/post-invoice/{invoice['id']}", headers=superuser_headers)
    receipt = client.post("/api/v1/srm/receipts", headers=superuser_headers, json={"customer_id": 701, "amount": 12000}).json()
    allocation_payload = client.post(f"/api/v1/srm/receipts/{receipt['id']}/allocate", headers=superuser_headers, json={"invoice_id": invoice["id"], "amount": 12000}).json()
    allocation = allocation_payload["allocation"]

    response = client.post(f"/api/v1/fam/integrations/srm/post-allocation/{allocation['id']}", headers=superuser_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "posted"
    assert body["allocation"]["allocated_amount"] == 12000.0

    ar = client.get("/api/v1/fam/ar/outstanding", headers=superuser_headers)
    assert ar.json()["totalOutstanding"] == 8000.0

