from app.apps.fam.models import FAMVoucherType
from tests.fam_test_utils import fam_admin_headers


def test_fam_voucher_types_seeded_and_manageable(client, db):
    headers = fam_admin_headers(client, db)
    response = client.get("/api/v1/fam/voucher-types", headers=headers)
    assert response.status_code == 200
    assert {item["category"] for item in response.json()["items"]} >= {"journal", "receipt", "payment", "sales", "purchase"}

    response = client.post("/api/v1/fam/voucher-types", headers=headers, json={
        "voucher_type_code": "MEMO",
        "voucher_type_name": "Memo Voucher",
        "category": "journal",
        "numbering_prefix": "MEMO",
        "numbering_sequence": 1,
        "auto_numbering": True,
        "active": True,
        "system_type": False,
    })
    assert response.status_code == 201, response.text
    assert db.query(FAMVoucherType).filter_by(voucher_type_code="MEMO").first()
