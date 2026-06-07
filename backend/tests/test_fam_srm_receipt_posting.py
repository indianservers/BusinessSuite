from app.apps.fam.models import FAMBillReference, FAMLedgerEntry, FAMPostingJob


def test_fam_posts_confirmed_srm_receipt_to_receipt_voucher_and_advance_reference(client, db, superuser_headers):
    receipt = client.post("/api/v1/srm/receipts", headers=superuser_headers, json={"customer_id": 601, "amount": 25000, "reference_number": "BANK-601"}).json()
    receipt = client.post(f"/api/v1/srm/receipts/{receipt['id']}/confirm", headers=superuser_headers).json()

    response = client.post(f"/api/v1/fam/integrations/srm/post-receipt/{receipt['id']}", headers=superuser_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "posted"
    assert body["voucher"]["status"] == "posted"
    assert body["billReference"]["bill_type"] == "advance"

    assert db.query(FAMLedgerEntry).filter(FAMLedgerEntry.voucher_id == body["voucher"]["id"]).count() == 2
    assert db.query(FAMBillReference).filter(FAMBillReference.bill_number == receipt["receipt_number"], FAMBillReference.bill_type == "advance").first()
    assert db.query(FAMPostingJob).filter(FAMPostingJob.source_record_type == "receipt", FAMPostingJob.source_record_id == receipt["id"], FAMPostingJob.status == "posted").first()

