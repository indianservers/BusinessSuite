from datetime import date
from sqlalchemy import update
from app.apps.srm.models import SRMInvoiceLine
from tests.test_retail_return_http import retail_setup, scenario, catalog, directory_identity
from tests.test_retail_workflows import cart


def test_batched_daily_report_still_rejects_changed_native_charge(client, db, retail_setup):
    response = client.post('/api/v1/srm/service-checkout', headers=retail_setup[0], json=cart(retail_setup))
    assert response.status_code == 201, response.text
    invoice = response.json()['invoice']['id']
    db.connection().execute(update(SRMInvoiceLine.__table__).where(SRMInvoiceLine.invoice_id == invoice).values(line_total=999))
    db.commit()
    result = client.get('/api/v1/srm/retail/reports/daily', headers=retail_setup[0], params={'day': date.today().isoformat()})
    assert result.status_code == 409, result.text
    assert 'charge identity differs' in result.json()['detail']
    assert 'checkout_report_read_batch' not in db.info
