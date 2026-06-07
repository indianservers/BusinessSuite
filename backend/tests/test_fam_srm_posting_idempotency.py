from tests.test_fam_srm_invoice_posting import create_sent_srm_invoice


def test_fam_srm_invoice_and_receipt_posting_are_idempotent(client, db, superuser_headers):
    invoice = create_sent_srm_invoice(client, superuser_headers, customer_id=801)
    first = client.post(f"/api/v1/fam/integrations/srm/post-invoice/{invoice['id']}", headers=superuser_headers).json()
    second = client.post(f"/api/v1/fam/integrations/srm/post-invoice/{invoice['id']}", headers=superuser_headers).json()
    assert second["idempotent"] is True
    assert first["voucher"]["id"] == second["voucher"]["id"]

    receipt = client.post("/api/v1/srm/receipts", headers=superuser_headers, json={"customer_id": 801, "amount": 1000}).json()
    client.post(f"/api/v1/srm/receipts/{receipt['id']}/confirm", headers=superuser_headers)
    receipt_first = client.post(f"/api/v1/fam/integrations/srm/post-receipt/{receipt['id']}", headers=superuser_headers).json()
    receipt_second = client.post(f"/api/v1/fam/integrations/srm/post-receipt/{receipt['id']}", headers=superuser_headers).json()
    assert receipt_second["idempotent"] is True
    assert receipt_first["voucher"]["id"] == receipt_second["voucher"]["id"]

