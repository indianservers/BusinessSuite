from app.apps.fam.models import FAMVoucherAuditLog
from tests.fam_test_utils import create_balanced_voucher, fam_admin_headers


def test_voucher_audit_records_create_and_post(client, db):
    headers = fam_admin_headers(client, db)
    voucher = create_balanced_voucher(client, headers)
    client.post(f"/api/v1/fam/vouchers/{voucher['id']}/post", headers=headers)
    response = client.get(f"/api/v1/fam/voucher-audit/{voucher['id']}", headers=headers)
    assert response.status_code == 200
    actions = {item["action"] for item in response.json()["items"]}
    assert {"CREATE", "POST"}.issubset(actions)
    assert db.query(FAMVoucherAuditLog).filter_by(voucher_id=voucher["id"]).count() >= 2
