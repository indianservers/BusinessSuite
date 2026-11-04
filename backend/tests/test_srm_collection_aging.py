from tests.rich_text_test_utils import organization_context
from datetime import date, timedelta

from app.apps.srm.models import SRMCustomerAging, SRMInvoice
from tests.srm_test_utils import create_sales_order


def test_srm_collection_aging_buckets_overdue_invoice(client, db, superuser_headers):
    order = create_sales_order(client, superuser_headers)
    invoice = client.post(f"/api/v1/srm/invoices/draft-from-sales-order/{order['id']}", headers=superuser_headers).json()
    issued = client.post(f"/api/v1/srm/invoices/{invoice['id']}/approve", headers=superuser_headers)
    assert issued.status_code == 200, issued.text
    db.query(SRMInvoice).filter(SRMInvoice.id == invoice["id"]).update({"due_date": date.today() - timedelta(days=45)})
    db.commit()

    response = client.get("/api/v1/srm/collections/aging", headers=superuser_headers)
    assert response.status_code == 200
    bucket = response.json()[0]
    assert bucket["days_31_60"] > 0
    assert bucket["customer_id"] == 101
    assert bucket["total_outstanding"] == bucket["days_31_60"]
