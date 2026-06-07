from app.apps.fam.models import FAMBranch
from tests.fam_test_utils import fam_admin_headers


def test_fam_branch_create_and_list(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/branches", headers=headers, json={
        "branch_code": "BLR",
        "branch_name": "Bengaluru",
        "gstin": "29ABCDE1234F1Z5",
        "state_code": "29",
        "address": "Bengaluru",
        "active": True,
    })
    assert response.status_code == 201, response.text
    assert db.query(FAMBranch).filter_by(branch_code="BLR").first()
    response = client.get("/api/v1/fam/branches", headers=headers)
    assert response.status_code == 200
    assert any(item["branch_code"] == "BLR" for item in response.json()["items"])
