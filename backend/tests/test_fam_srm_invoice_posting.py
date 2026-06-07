from app.apps.fam.models import FAMBillReference, FAMLedgerEntry, FAMPostingJob, FAMSRMMapping, FAMVoucher


def create_sent_srm_invoice(client, headers, customer_id=501, total=11800, tax=1800):
    response = client.post("/api/v1/srm/invoices/manual", headers=headers, json={
        "customer_id": customer_id,
        "currency": "INR",
        "issue_date": "2026-06-06",
        "due_date": "2026-07-06",
        "lines": [{
            "description": "Implementation services",
            "quantity": 1,
            "unit_price": total - tax,
            "tax_amount": tax,
            "line_total": total,
        }],
    })
    assert response.status_code == 201, response.text
    invoice = response.json()
    client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=headers)
    return client.post(f"/api/v1/srm/invoices/{invoice['id']}/send", headers=headers).json()


def test_fam_posts_srm_invoice_to_sales_voucher_bill_reference_and_ar(client, db, superuser_headers):
    invoice = create_sent_srm_invoice(client, superuser_headers)

    response = client.post(f"/api/v1/fam/integrations/srm/post-invoice/{invoice['id']}", headers=superuser_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "posted"
    assert body["voucher"]["status"] == "posted"
    assert body["billReference"]["bill_number"] == invoice["invoice_number"]
    assert body["billReference"]["outstanding_amount"] == invoice["balance_amount"]

    voucher = db.query(FAMVoucher).filter(FAMVoucher.id == body["voucher"]["id"]).first()
    assert voucher.source_module == "srm"
    assert voucher.source_record_type == "invoice"

    assert db.query(FAMLedgerEntry).filter(FAMLedgerEntry.voucher_id == voucher.id).count() >= 2
    assert db.query(FAMSRMMapping).filter(FAMSRMMapping.srm_record_type == "invoice", FAMSRMMapping.srm_record_id == invoice["id"]).count() >= 2
    assert db.query(FAMPostingJob).filter(FAMPostingJob.source_record_type == "invoice", FAMPostingJob.source_record_id == invoice["id"], FAMPostingJob.status == "posted").first()
    assert db.query(FAMBillReference).filter(FAMBillReference.bill_number == invoice["invoice_number"]).first()

    ar = client.get("/api/v1/fam/ar/aging", headers=superuser_headers)
    assert ar.status_code == 200
    assert ar.json()["totalOutstanding"] == invoice["balance_amount"]
