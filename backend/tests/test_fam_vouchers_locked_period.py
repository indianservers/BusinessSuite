from app.apps.fam.models import FAMFinancialYear
from tests.fam_test_utils import balanced_voucher_payload, fam_admin_headers


def test_locked_financial_year_blocks_posting(client, db):
    headers = fam_admin_headers(client, db)
    client.get("/api/v1/fam/dashboard", headers=headers)
    fy = db.query(FAMFinancialYear).filter_by(is_current=True).first()
    fy.status = "locked"
    db.commit()
    response = client.post("/api/v1/fam/vouchers", headers=headers, json=balanced_voucher_payload(client, headers))
    assert response.status_code == 409
