from app.apps.srm.models import SRMCollectionReminder
from tests.srm_test_utils import create_sales_order


def test_srm_collection_reminder_escalation_and_writeoff_request(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()

    reminder = client.post("/api/v1/srm/collections/reminders/send", headers=superuser_headers, json={"customer_id": 101, "invoice_id": invoice["id"], "message": "Please pay"})
    assert reminder.status_code == 200, reminder.text
    assert reminder.json()["status"] == "sent"

    escalation = client.post(f"/api/v1/srm/collections/{invoice['id']}/escalate", headers=superuser_headers, json={"message": "Escalate overdue payment"})
    assert escalation.status_code == 200, escalation.text
    assert escalation.json()["invoice"]["status"] == "overdue"

    writeoff = client.post(f"/api/v1/srm/collections/{invoice['id']}/write-off-request", headers=superuser_headers, json={"reason": "Customer insolvency"})
    assert writeoff.status_code == 200, writeoff.text
    assert writeoff.json()["write_off_request"]["reminder_type"] == "write_off_request"
    assert db.query(SRMCollectionReminder).filter(SRMCollectionReminder.invoice_id == invoice["id"]).count() >= 3
