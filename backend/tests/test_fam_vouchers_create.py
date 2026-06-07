from app.apps.fam.models import FAMVoucher, FAMVoucherLine
from tests.fam_test_utils import balanced_voucher_payload, fam_admin_headers


def test_create_voucher_draft_with_lines_and_totals(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/vouchers", headers=headers, json=balanced_voucher_payload(client, headers))
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["status"] == "draft"
    assert data["total_debit"] == 1000
    assert data["total_credit"] == 1000
    assert db.query(FAMVoucher).filter_by(id=data["id"], status="draft").first()
    assert db.query(FAMVoucherLine).filter_by(voucher_id=data["id"]).count() == 2
