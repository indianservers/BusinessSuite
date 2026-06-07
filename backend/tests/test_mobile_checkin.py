from app.apps.saas.models import MobileSalesVisitCheckIn
from phase10_test_utils import auth_headers


def test_mobile_sales_visit_checkin_creates_auditable_record(client, db):
    headers = auth_headers(client, db, permissions=["crm_view"])
    response = client.post("/api/v1/mobile/check-in", json={"customer_name": "Acme", "latitude": "12.97", "longitude": "77.59", "notes": "Discovery visit"}, headers=headers)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "checked_in"
    assert db.query(MobileSalesVisitCheckIn).filter(MobileSalesVisitCheckIn.customer_name == "Acme").count() == 1
