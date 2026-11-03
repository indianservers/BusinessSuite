from app.apps.srm.models import SRMCollectionReminder
from tests.srm_test_utils import create_sales_order
from tests.rich_text_test_utils import organization_context


def test_srm_collection_reminder_escalation_and_writeoff_request(client, db, superuser_headers):
    from app.models.company import Branch
    if not db.query(Branch).filter_by(company_id=1).first():
        db.add(Branch(company_id=1, name='Synthetic collection branch', code='COLL', is_active=True))
        db.commit()
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()
    from app.models.company import Branch
    from app.apps.srm.models import SRMInvoice
    from app.apps.communication.customer_models import CustomerRecipient, CustomerBinding
    branch = db.query(Branch).filter_by(company_id=1).first()
    response = client.post('/api/v1/communication/customers/recipients', headers=superuser_headers, json={
        'name':'Synthetic billing contact', 'email':'billing@example.com', 'role':'billing',
        'preferences':{'email.transactional':True}, 'consent_source':'Synthetic fixture opt-in'})
    assert response.status_code == 201, response.text
    response = client.post(f"/api/v1/communication/customers/recipients/{response.json()['id']}/bindings", headers=superuser_headers, json={'source_type':'invoice','source_id':invoice['id']})
    assert response.status_code == 201, response.text
    obj = db.get(SRMInvoice, invoice['id'])
    obj.status = 'issued'
    db.commit()

    reminder = client.post("/api/v1/srm/collections/reminders/send", headers=superuser_headers, json={"customer_id": 101, "invoice_id": invoice["id"], "message": "Please pay"})
    assert reminder.status_code == 200, reminder.text
    assert reminder.json()["status"] == "queued"
    assert reminder.json()['sent_at'] is None

    escalation = client.post(f"/api/v1/srm/collections/{invoice['id']}/escalate", headers=superuser_headers, json={"message": "Escalate overdue payment"})
    assert escalation.status_code == 200, escalation.text
    assert escalation.json()["invoice"]["status"] == "overdue"

    writeoff = client.post(f"/api/v1/srm/collections/{invoice['id']}/write-off-request", headers=superuser_headers, json={"reason": "Customer insolvency"})
    assert writeoff.status_code == 200, writeoff.text
    assert writeoff.json()["write_off_request"]["reminder_type"] == "write_off_request"
    assert db.query(SRMCollectionReminder).filter(SRMCollectionReminder.invoice_id == invoice["id"]).count() >= 3
