from app.apps.fam.models import FAMVoucher
from tests.test_fam_srm_invoice_posting import create_sent_srm_invoice


def test_fam_reverses_srm_invoice_posting_with_opposite_voucher(client, db, superuser_headers):
    invoice = create_sent_srm_invoice(client, superuser_headers, customer_id=901)
    posted = client.post(f"/api/v1/fam/integrations/srm/post-invoice/{invoice['id']}", headers=superuser_headers).json()

    response = client.post(f"/api/v1/fam/integrations/srm/reverse/invoice/{invoice['id']}", headers=superuser_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "reversed"
    assert body["reversalVoucher"]["status"] == "posted"

    original = db.query(FAMVoucher).filter(FAMVoucher.id == posted["voucher"]["id"]).first()
    assert original.reversed_voucher_id == body["reversalVoucher"]["id"]

    again = client.post(f"/api/v1/fam/integrations/srm/reverse/invoice/{invoice['id']}", headers=superuser_headers)
    assert again.json()["idempotent"] is True

