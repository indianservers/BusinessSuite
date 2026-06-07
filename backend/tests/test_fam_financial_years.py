from app.apps.fam.models import FAMAuditLog, FAMFinancialYear
from tests.fam_test_utils import fam_admin_headers


def test_fam_financial_years_seed_create_overlap_close_lock(client, db):
    headers = fam_admin_headers(client, db)
    response = client.get("/api/v1/fam/financial-years", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "FY 2026-27"

    response = client.post("/api/v1/fam/financial-years", headers=headers, json={
        "name": "FY 2027-28",
        "start_date": "2027-04-01",
        "end_date": "2028-03-31",
        "status": "open",
        "is_current": False,
    })
    assert response.status_code == 201, response.text
    year_id = response.json()["id"]
    assert db.query(FAMFinancialYear).filter_by(name="FY 2027-28").first()

    overlap = client.post("/api/v1/fam/financial-years", headers=headers, json={
        "name": "Overlap",
        "start_date": "2027-05-01",
        "end_date": "2028-02-28",
        "status": "open",
        "is_current": False,
    })
    assert overlap.status_code == 409

    assert client.post(f"/api/v1/fam/financial-years/{year_id}/close", headers=headers).json()["status"] == "closed"
    assert client.post(f"/api/v1/fam/financial-years/{year_id}/lock", headers=headers).json()["status"] == "locked"
    assert db.query(FAMAuditLog).filter_by(record_type="financial_year", action="LOCKED").first()
