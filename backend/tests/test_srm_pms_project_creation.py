from app.apps.project_management.models import PMSMilestone, PMSProject, PMSTask

from tests.srm_test_utils import create_engagement_via_confirm, create_sales_order


def test_sales_order_summary_preserves_header_and_skips_lines(client, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    path = "/api/v1/srm/sales-orders"
    full = client.get(path, headers=superuser_headers)
    summary = client.get(path, headers=superuser_headers, params={"summary_only": True})
    assert full.status_code == summary.status_code == 200
    assert [row["id"] for row in full.json()] == [row["id"] for row in summary.json()]
    header = next(row for row in summary.json() if row["id"] == order["id"])
    detailed = next(row for row in full.json() if row["id"] == order["id"])
    assert detailed["lines"]
    assert header == {key: detailed[key] for key in header}
    assert "lines" not in header


def test_srm_engagement_creates_pms_project(client, db, superuser_headers):
    engagement, _order = create_engagement_via_confirm(client, superuser_headers)
    response = client.post(f"/api/v1/srm/engagements/{engagement['id']}/create-pms-project", headers=superuser_headers)
    assert response.status_code == 200, response.text
    project = response.json()["project"]
    assert project["project_key"].startswith("SRM")
    assert db.query(PMSProject).filter(PMSProject.id == project["id"]).first() is not None
    assert db.query(PMSMilestone).filter(PMSMilestone.project_id == project["id"]).count() >= 2
    assert db.query(PMSTask).filter(PMSTask.project_id == project["id"]).count() >= 1


def test_srm_engagement_rejects_pms_project_before_sales_order_confirmed(client, db, superuser_headers):
    order = client.post("/api/v1/srm/sales-orders", headers=superuser_headers, json={"title": "Unconfirmed order"}).json()
    engagement = client.post("/api/v1/srm/engagements", headers=superuser_headers, json={
        "name": "Unconfirmed engagement",
        "sales_order_id": order["id"],
    }).json()
    response = client.post(f"/api/v1/srm/engagements/{engagement['id']}/create-pms-project", headers=superuser_headers)
    assert response.status_code == 400
