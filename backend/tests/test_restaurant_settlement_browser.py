import json
import tempfile
from pathlib import Path
from decimal import Decimal
from uuid import uuid4
from app.apps.srm.models import SRMPOSSession, SRMSalesOrder, SRMInvoice, SRMReceipt
from app.apps.crm.models import CRMCompany
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantKitchenIssue
from app.business_packs.boundary import install
from app.business_packs.access import resolve_context
from app.business_packs.native_policy import native_srm_policy
from tests.test_restaurant_tabs import unpaid, scenario, catalog, directory_identity, stock
from tests.test_restaurant_kitchen import staff
from tests.test_restaurant_settlement import finance_actor
from tests.test_srm_native_transaction_operations import native_writer


def run_native_browser(client, db, unpaid, monkeypatch, *, walkin=False):
    from tests.test_control_browser import test_control_center_real_browser
    case = unpaid
    with native_writer(db, case['manager'], case['branch']):
        scope = resolve_context(db, case['manager'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            register = SRMPOSSession(organization_id=1, session_number='TAB-BROWSER-'+uuid4().hex,
                status='open', created_by=case['manager'].id)
            db.add(register); db.commit()
            register_id = register.id
        finally:
            cleanup()
    case = {**case, 'register': register_id}
    cashier, _ = finance_actor(db, case)
    chef, _ = staff(db, case, 'chef')
    server, _ = staff(db, case, 'server')
    db.get(CRMCompany, 101).account_type = 'Customer'
    db.commit()
    identities = {}
    for role, headers in [('manager', case['headers']), ('cashier', cashier), ('chef', chef), ('server', server)]:
        identity = client.get('/api/v1/auth/me', headers=headers)
        access = client.get('/api/v1/access/me', headers=headers)
        assert identity.status_code == access.status_code == 200, (identity.text, access.text)
        user = identity.json()
        primary = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
        user.update(role=primary, primary_role=primary, access=access.json())
        identities[role] = {'token': headers['Authorization'].split(' ', 1)[1], 'user': user}
    before = stock(db, case)
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'restaurant-settlement-native.cjs')
    # Four complete genuine access responses exceed Windows' per-env-value limit.
    # This private temporary fixture is removed even when the managed browser fails.
    with tempfile.TemporaryDirectory(prefix='restaurant-native-auth-') as temporary:
        auth_file = Path(temporary) / 'identity.json'
        auth_file.write_text(json.dumps({**identities, 'branch': str(case['branch']),
            'context': str(case['context']), 'product': case['product'], 'register': register_id, 'walkin': walkin}), encoding='utf-8')
        monkeypatch.setenv('SUITE_QA_AUTH_FILE', str(auth_file))
        test_control_center_real_browser(client, db, None, case['headers'])
    assert db.query(RestaurantServiceOrder).one().state == 'served'
    assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == 1
    assert db.query(SRMReceipt).count() == 2 and db.query(RestaurantKitchenIssue).count() == 1
    assert db.query(SRMInvoice).one().paid_amount == Decimal('118')
    assert stock(db, case) == before-1


def test_actual_app_named_customer_split_settlement_and_bootstrap(client, db, unpaid, monkeypatch):
    run_native_browser(client, db, unpaid, monkeypatch)


def test_actual_app_walkin_assigns_customer_then_split_settles(client, db, unpaid, monkeypatch):
    run_native_browser(client, db, unpaid, monkeypatch, walkin=True)
