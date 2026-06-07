from app.apps.fam.models import FAMCostCenter
from tests.fam_test_utils import fam_admin_headers


def test_fam_cost_center_create_and_list(client, db):
    headers = fam_admin_headers(client, db)
    response = client.post("/api/v1/fam/cost-centers", headers=headers, json={
        "code": "SALES",
        "name": "Sales Department",
        "parent_id": None,
        "active": True,
    })
    assert response.status_code == 201, response.text
    assert db.query(FAMCostCenter).filter_by(code="SALES").first()
    response = client.get("/api/v1/fam/cost-centers", headers=headers)
    assert response.status_code == 200
    assert any(item["code"] == "SALES" for item in response.json()["items"])
