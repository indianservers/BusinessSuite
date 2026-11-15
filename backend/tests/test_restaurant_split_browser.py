import json
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMPOSSession, SRMSalesOrder, SRMInvoice, SRMReceipt, SRMPOSCashierClosing
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantKitchenIssue
from app.business_packs.restaurant.split_models import RestaurantBillIssue, RestaurantBillReceipt
from app.business_packs.boundary import install
from app.business_packs.access import resolve_context
from app.business_packs.native_policy import native_srm_policy
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, stock
from tests.test_restaurant_kitchen import staff
from tests.test_srm_native_transaction_operations import native_writer


def test_actual_item_quantity_bills_partial_collections_and_native_shift_close_desktop_mobile(client, db, unpaid, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    case = unpaid
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            register = SRMPOSSession(organization_id=1, session_number='SPLIT-UI-'+uuid4().hex,
                status='open', cashier_user_id=case['manager'].id, created_by=case['manager'].id)
            db.add(register); db.commit(); register_id = register.id
        finally:
            cleanup()
    identities = {}
    for role, headers in [('manager', case['headers']), *[(role, staff(db, case, role)[0]) for role in ('cashier','chef','server')]]:
        identity = client.get('/api/v1/auth/me', headers=headers)
        access = client.get('/api/v1/access/me', headers=headers)
        assert identity.status_code == access.status_code == 200, (identity.text, access.text)
        user = identity.json()
        primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
        identities[role] = {'token': headers['Authorization'].split(' ', 1)[1],
            'user': {**user, 'role': primary, 'primary_role': primary, 'access': access.json()}}
    db.get(CRMCompany, 101).account_type = 'Customer'; db.commit()
    before = stock(db, case)
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'restaurant-split-native.cjs')
    with tempfile.TemporaryDirectory(prefix='restaurant-split-auth-') as temporary:
        auth = Path(temporary)/'identity.json'
        auth.write_text(json.dumps({**identities, 'branch': str(case['branch']), 'context': str(case['context']),
            'product': case['product'], 'register': register_id}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth))
        test_control_center_real_browser(client, db, None, case['headers'])
    assert db.query(SRMSalesOrder).count() == db.query(RestaurantServiceOrder).count() == 1
    assert db.query(RestaurantServiceOrder).one().state == 'served'
    assert db.query(SRMInvoice).count() == db.query(RestaurantBillIssue).count() == 2
    assert db.query(SRMReceipt).count() == db.query(RestaurantBillReceipt).count() == 3
    assert all(invoice.balance_amount == 0 and invoice.paid_amount == Decimal('59') for invoice in db.query(SRMInvoice))
    assert db.query(SRMPOSCashierClosing).count() == 1 and db.query(SRMPOSCashierClosing).one().cash_sales == 79
    assert db.query(RestaurantKitchenIssue).count() == 1 and stock(db, case) == before-1
