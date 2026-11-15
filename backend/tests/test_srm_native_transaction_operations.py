"""Native order/issue operations compose without committing an outer checkout."""
from contextlib import contextmanager
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException

from app.apps.srm.api.router import (
    create_sales_order_operation, approve_invoice_operation, _create_invoice_from_lines,
)
from app.apps.srm.schemas import SRMSalesOrderCreate
from app.apps.srm.models import (
    SRMSalesOrder, SRMSalesOrderLine, SRMProduct, SRMInventoryMovement, SRMInvoice,
    SRMInvoiceDraft, SRMInvoiceLine, SRMInvoiceHistory, SRMAuditLog, SRMEngagement,
)
from app.apps.srm.commercial_models import InvoiceContext
from app.apps.fam.models import FAMVoucher, FAMLedgerEntry
from app.models.notification import Notification
from app.models.user import User
from app.shared.models import ServicePolicy
from app.shared.follow_ups import FollowUp, FollowUpActivity
from app.branches.boundary import install
from app.branches.service import context
from tests.test_business_suite_pos_integrity import catalog
from tests.test_contact_directory import directory_identity
from tests.srm_test_utils import seed_invoice_parties, auth_headers_for


@contextmanager
def native_writer(db, user, branch):
    previous_write = db.info.get('security_write_request')
    previous_branch = getattr(user, '_suite_branch_id', None)
    db.info['security_write_request'] = True
    user._suite_branch_id = branch
    cleanup = install(db, user, context(db, user, 1, str(branch)))
    try:
        from app.access.service import background_scope
        with background_scope(db,user,'srm','create',branch_id=branch):
            yield
    finally:
        cleanup()
        user._suite_branch_id = previous_branch
        if previous_write is None: db.info.pop('security_write_request', None)
        else: db.info['security_write_request'] = previous_write


def basket(catalog, *, follow_up=False):
    key = uuid4().hex
    _, _, products = catalog
    return SRMSalesOrderCreate.model_validate({
        'order_number': 'POS-TX-' + key, 'title': 'Native mixed sale', 'customer_id': 101, 'currency': 'INR',
        'metadata_json': {'source': 'pos', 'pos_sale_id': key},
        'lines': [
            {'product_id': products[0], 'quantity': 1, 'unit_price': 100, 'description': 'Tracked product'},
            {'product_id': products[1], 'quantity': 1, 'unit_price': 100, 'description': 'Service',
             **({'metadata_json': {'follow_up': {'required': True, 'type': 'days',
                'reference': 'purchase', 'interval_days': 45, 'timezone': 'Asia/Kolkata'}}} if follow_up else {})},
        ],
    })


def make_invoice(db, user, order):
    item = db.get(SRMSalesOrder, order['id'])
    invoice = _create_invoice_from_lines(db, user, 'sales_order', item.id, None, item,
        [{'source_type': 'sales_order_line', 'source_id': line.id, 'description': line.description,
          'quantity': line.quantity, 'unit_price': line.unit_price, 'discount_amount': line.discount_amount,
          'tax_amount': line.tax_amount} for line in item.lines], item.currency)
    db.flush()
    return invoice


def test_noncommitting_order_and_invoice_issue_are_rolled_back_with_outer_transaction(client, db, catalog):
    seed_invoice_parties(db)
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    actor.organization_id = 1
    branch = int(catalog[0]['X-Suite-Branch'])
    models = [SRMSalesOrder, SRMSalesOrderLine, SRMInventoryMovement, SRMInvoice, SRMInvoiceDraft,
        SRMInvoiceLine, SRMInvoiceHistory, SRMAuditLog, InvoiceContext, ServicePolicy,
        FollowUp, FollowUpActivity, Notification, FAMVoucher, FAMLedgerEntry, SRMEngagement]
    before = {model: db.query(model).count() for model in models}
    product = db.get(SRMProduct, catalog[2][0])
    before_stock = product.current_quantity
    class AbortCheckout(Exception): pass
    with native_writer(db, actor, branch):
        with pytest.raises(AbortCheckout):
            with db.begin_nested():
                order = create_sales_order_operation(basket(catalog, follow_up=True), db, actor, commit=False)
                assert db.in_nested_transaction()
                assert db.get(SRMProduct, catalog[2][0]).current_quantity == before_stock - 1
                assert db.query(FollowUp).count() == before[FollowUp] + 1
                invoice = make_invoice(db, actor, order)
                issued = approve_invoice_operation(invoice.id, db, actor, commit=False)
                assert db.in_nested_transaction()
                assert issued['status'] == 'approved' and invoice.approved_at
                assert db.get(InvoiceContext, invoice.id).issued_at
                assert db.query(SRMInvoiceLine).count() == before[SRMInvoiceLine] + 2
                raise AbortCheckout()
    db.expire_all()
    assert {model: db.query(model).count() for model in models} == before
    assert db.get(SRMProduct, catalog[2][0]).current_quantity == before_stock


def test_native_operations_commit_once_when_the_outer_caller_commits_and_replay_no_side_effects(client, db, catalog):
    seed_invoice_parties(db)
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    actor.organization_id = 1
    data = basket(catalog)
    branch = int(catalog[0]['X-Suite-Branch'])
    before_moves = db.query(SRMInventoryMovement).count()
    with native_writer(db, actor, branch):
        order = create_sales_order_operation(data, db, actor, commit=False)
        repeated = create_sales_order_operation(data, db, actor, commit=False)
        assert repeated['id'] == order['id']
        assert db.query(SRMInventoryMovement).count() == before_moves + 1
        invoice = make_invoice(db, actor, order)
        issued = approve_invoice_operation(invoice.id, db, actor, commit=False)
        history_count = db.query(SRMInvoiceHistory).filter_by(invoice_id=invoice.id).count()
        snapshot = db.get(InvoiceContext, invoice.id).customer_snapshot.copy()
        assert approve_invoice_operation(invoice.id, db, actor, commit=False)['id'] == issued['id']
        assert db.query(SRMInvoiceHistory).filter_by(invoice_id=invoice.id).count() == history_count
        assert db.get(InvoiceContext, invoice.id).customer_snapshot == snapshot
        db.commit()
    db.expire_all()
    assert db.get(SRMSalesOrder, order['id']) is not None
    assert db.get(SRMInvoice, issued['id']).status == 'approved'
    assert db.get(SRMProduct, catalog[2][0]).current_quantity == Decimal('4')
    assert db.query(SRMEngagement).count() == 0


@pytest.mark.parametrize('operation', ['order', 'approval'])
@pytest.mark.parametrize('case', ['missing_permission', 'read_only_request', 'inactive_actor'])
def test_direct_python_operations_recheck_native_write_authority(client, db, catalog, operation, case):
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    actor.organization_id = 1
    if case == 'missing_permission':
        email = 'native-no-permission-' + uuid4().hex + '@example.com'
        auth_headers_for(client, db, email, 'srm_viewer', permissions=['srm_view'])
        actor = db.query(User).filter_by(email=email).one()
    elif case == 'inactive_actor':
        actor.is_active = False; db.flush()
    previous_write = db.info.get('security_write_request')
    if case == 'read_only_request': db.info['security_write_request'] = False
    try:
        with pytest.raises(HTTPException) as error:
            if operation == 'order': create_sales_order_operation(basket(catalog), db, actor, commit=False)
            else: approve_invoice_operation(987654321, db, actor, commit=False)
        assert error.value.status_code == 403
        assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == 0
    finally:
        if previous_write is None: db.info.pop('security_write_request', None)
        else: db.info['security_write_request'] = previous_write


def test_existing_http_order_and_approval_contracts_and_stock_idempotency_are_unchanged(client, db, catalog):
    seed_invoice_parties(db)
    payload = basket(catalog).model_dump(mode='json')
    first = client.post('/api/v1/srm/sales-orders', headers=catalog[0], json=payload)
    assert first.status_code == 201, first.text
    assert first.json()['status'] == 'draft' and len(first.json()['lines']) == 2
    repeated = client.post('/api/v1/srm/sales-orders', headers=catalog[0], json=payload)
    assert repeated.status_code == 201 and repeated.json()['id'] == first.json()['id']
    assert db.get(SRMProduct, catalog[2][0]).current_quantity == Decimal('4')
    draft = client.post('/api/v1/srm/invoices/draft-from-sales-order/' + str(first.json()['id']), headers=catalog[0])
    assert draft.status_code == 201, draft.text
    approved = client.post('/api/v1/srm/invoices/' + str(draft.json()['id']) + '/approve', headers=catalog[0])
    assert approved.status_code == 200 and approved.json()['status'] == 'approved'
    count = db.query(SRMInvoiceHistory).filter_by(invoice_id=draft.json()['id']).count()
    again = client.post('/api/v1/srm/invoices/' + str(draft.json()['id']) + '/approve', headers=catalog[0])
    assert again.status_code == 200 and again.json()['id'] == approved.json()['id']
    assert db.query(SRMInvoiceHistory).filter_by(invoice_id=draft.json()['id']).count() == count


@pytest.mark.parametrize('permission,operation', [('srm_manage', 'approval'), ('srm_invoice_approve', 'order')])
def test_callable_operations_do_not_substitute_one_native_write_permission_for_another(client, db, catalog, permission, operation):
    email = 'native-exact-permission-' + uuid4().hex + '@example.com'
    role = 'srm_sales_manager' if permission == 'srm_manage' else 'srm_finance_manager'
    auth_headers_for(client, db, email, role, permissions=[permission])
    actor = db.query(User).filter_by(email=email).one()
    with pytest.raises(HTTPException) as error:
        if operation == 'approval': approve_invoice_operation(987654321, db, actor, commit=False)
        else: create_sales_order_operation(basket(catalog), db, actor, commit=False)
    assert error.value.status_code == 403
    assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == 0
