from app.apps.fam.models import FAMLedgerEntry, FAMVoucher
from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_post_balanced_voucher_creates_immutable_ledger_entries(client, db):
    headers = fam_admin_headers(client, db)
    voucher = create_balanced_voucher(client, headers, amount=1500)
    response = client.post(f"/api/v1/fam/vouchers/{voucher['id']}/post", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "posted"
    assert db.query(FAMVoucher).filter_by(id=voucher["id"], status="posted").first()
    assert db.query(FAMLedgerEntry).filter_by(voucher_id=voucher["id"]).count() == 2
