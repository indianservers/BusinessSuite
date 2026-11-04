from app.apps.fam.models import FAMBranch
from tests.fam_test_utils import fam_admin_headers


def test_fam_branch_create_and_list(client, db):
    headers = fam_admin_headers(client, db)
    from app.branches.models import BranchPolicy
    from app.models.user import User
    admin = db.query(User).filter_by(email="fam-admin@example.com").one()
    db.add(BranchPolicy(user_id=admin.id,company_id=1,manage_access=True,use_home_branch=False))
    db.commit()
    response = client.post("/api/v1/fam/branches", headers=headers, json={
        "branch_code": "BLR",
        "branch_name": "Bengaluru",
        "gstin": "29AAPFU0939F1ZR",
        "state_code": "29",
        "address": "Bengaluru",
        "active": True,
    })
    assert response.status_code == 201, response.text
    assert db.query(FAMBranch).filter_by(branch_code="BLR").first()
    response = client.get("/api/v1/fam/branches", headers=headers)
    assert response.status_code == 200
    assert any(item["branch_code"] == "BLR" for item in response.json()["items"])
