from app.apps.fam.models import FAMVoucher
from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_cancel_and_reverse_voucher_lifecycle(client, db):
    headers = fam_admin_headers(client, db)
    draft = create_balanced_voucher(client, headers, amount=700)
    cancel = client.post(f"/api/v1/fam/vouchers/{draft['id']}/cancel", headers=headers, json={"reason": "Duplicate"})
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    posted = create_balanced_voucher(client, headers, amount=800)
    assert client.post(f"/api/v1/fam/vouchers/{posted['id']}/post", headers=headers).status_code == 200
    reverse = client.post(f"/api/v1/fam/vouchers/{posted['id']}/reverse", headers=headers)
    assert reverse.status_code == 201
    assert reverse.json()["reversed_voucher_id"] == posted["id"]
    assert db.query(FAMVoucher).filter_by(id=posted["id"], status="reversed").first()
