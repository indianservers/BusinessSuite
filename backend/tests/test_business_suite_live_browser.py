"""Actual shared customer React pages against the real disposable FastAPI DB."""
import json
from decimal import Decimal
from tests.test_contact_directory import directory_identity


def test_tc006_012_common_customer_ui_uses_real_canonical_api(client, db, superuser_headers, monkeypatch, request):
    from tests.test_control_browser import test_control_center_real_browser
    from app.models.user import User
    from app.models.company import Company
    seller = db.get(Company, 1)
    seller.default_timezone = 'Asia/Kolkata'
    seller.legal_name = 'Fictional Shared Customer Browser Seller Ltd'
    seller.address = '1 Fictional Test Road, Hyderabad, Telangana 500001'
    seller.city = 'Hyderabad'
    seller.state = 'Telangana'
    seller.country = 'India'
    seller.email = 'browser-seller@example.invalid'
    db.commit()
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'business-suite-live.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({'token':superuser_headers['Authorization'].split(' ',1)[1],
                        'user_id':actor.id, 'branch':superuser_headers['X-Suite-Branch']}))
    test_control_center_real_browser(client, db, None, superuser_headers)
    from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt, SRMReceiptAllocation, SRMPOSSession
    from app.apps.srm.commercial_models import InvoiceContext
    from app.apps.srm.service_checkout_models import POSServiceCheckout, POSCheckoutPayment
    from app.apps.crm.models import CRMCompany
    from app.apps.project_management.models import PMSTimesheet
    buyer = db.query(CRMCompany).filter_by(name='QA Sales edited المشتركة 客户').one()
    order = db.query(SRMSalesOrder).one()
    invoice = db.query(SRMInvoice).one()
    receipt = db.query(SRMReceipt).one()
    register = db.query(SRMPOSSession).one()
    checkout = db.query(POSServiceCheckout).one()
    allocation = db.query(SRMReceiptAllocation).one()
    mapped_payment = db.query(POSCheckoutPayment).one()
    issued = db.query(InvoiceContext).filter_by(invoice_id=invoice.id).one()
    assert order.customer_id == invoice.customer_id == receipt.customer_id == buyer.id
    assert checkout.customer_id == buyer.id and checkout.pos_session_id == register.id
    assert checkout.invoice_id == invoice.id and checkout.sales_order_id == order.id
    assert invoice.status == 'paid' and issued.issued_at is not None
    assert receipt.status == 'allocated' and receipt.payment_method.lower() == 'cash'
    assert invoice.total_amount == invoice.paid_amount == receipt.amount == Decimal('117.99')
    assert invoice.balance_amount == receipt.unallocated_amount == 0
    assert allocation.invoice_id == invoice.id and allocation.receipt_id == receipt.id
    assert allocation.amount == Decimal('117.99')
    assert mapped_payment.collection_session_id == register.id
    assert register.status == 'open' and register.opening_cash == 0
    # Native receipt-backed register summary, never order-total/payment-mode inference.
    summary = client.get('/api/v1/srm/pos/sessions/active', headers=superuser_headers)
    assert summary.status_code == 200, summary.text
    assert Decimal(str(summary.json()['cash_sales'])) == Decimal('117.99')
    assert Decimal(str(summary.json()['expected_cash'])) == Decimal('117.99')
    assert summary.json()['unattributed_cash_count'] == 0
    assert db.query(PMSTimesheet).count() == 0
