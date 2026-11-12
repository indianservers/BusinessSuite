"""Actual shared customer React pages against the real disposable FastAPI DB."""
import json
from tests.test_contact_directory import directory_identity


def test_tc006_012_common_customer_ui_uses_real_canonical_api(client, db, superuser_headers, monkeypatch, request):
    from tests.test_control_browser import test_control_center_real_browser
    from app.models.user import User
    from app.models.company import Company
    db.get(Company,1).default_timezone='Asia/Kolkata'
    db.commit()
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'business-suite-live.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({'token':superuser_headers['Authorization'].split(' ',1)[1],
                        'user_id':actor.id, 'branch':superuser_headers['X-Suite-Branch']}))
    test_control_center_real_browser(client, db, None, superuser_headers)
    from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt
    # Record the existing financial integration gap explicitly. The browser
    # check verifies order arithmetic; it does not certify invoice/payment posting.
    assert db.query(SRMSalesOrder).count() == 1
    assert db.query(SRMInvoice).count() == 0
    assert db.query(SRMReceipt).count() == 0
    request.node.user_properties.append(('release_blocker', 'POS checkout creates an order, not an invoice or receipt'))
