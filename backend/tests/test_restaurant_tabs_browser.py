import json
from decimal import Decimal
from app.apps.srm.models import SRMSalesOrder, SRMInvoice, SRMReceipt
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantTabLine, RestaurantKitchenIssue
from tests.test_restaurant_tabs import unpaid, stock, scenario, catalog, directory_identity
from tests.test_restaurant_kitchen import staff


def test_unpaid_tab_additions_preparation_and_serving_in_existing_ui(client, db, unpaid, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    chef, _ = staff(db, unpaid, 'chef')
    server, _ = staff(db, unpaid, 'server')
    before = stock(db, unpaid)
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'restaurant-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({'branch': str(unpaid['branch']), 'context': str(unpaid['context']),
        'unpaid': True, 'product': unpaid['product'], 'manager': unpaid['headers']['Authorization'].split(' ', 1)[1],
        'chef': chef['Authorization'].split(' ', 1)[1], 'server': server['Authorization'].split(' ', 1)[1]}))
    test_control_center_real_browser(client, db, None, unpaid['headers'])
    assert db.query(RestaurantServiceOrder).one().state == 'open'
    assert db.query(RestaurantServiceOrder).one().source_kind == 'unpaid_tab'
    assert db.query(RestaurantTabLine).count() == 3 and db.query(RestaurantKitchenIssue).count() == 2
    assert db.query(SRMSalesOrder).one().total_amount == Decimal('354')
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
    assert stock(db, unpaid) == before-2


def test_native_cashier_discovers_unpaid_tabs_through_production_app_shell(client, db, unpaid, monkeypatch):
    from tests.test_control_browser import test_control_center_real_browser
    from tests.test_restaurant_tabs import data, post, BASE, native_actor, grant, PackContext
    from app.access.models import AccessPolicy
    from app.models.user import Permission
    from app.branches.models import BranchGrant
    from app.db.init_db import SYSTEM_PERMISSIONS
    order = post(client, unpaid['headers'], '/tabs', data(unpaid))
    headers, actor = native_actor(db, unpaid['branch'], actions=('view',))
    grant(db, actor, unpaid['branch'], 'restaurant', 'cashier', db.get(PackContext, unpaid['context']))
    permission = db.query(Permission).filter_by(name='srm_collection_view').one_or_none()
    if permission is None:
        definition = next(value for value in SYSTEM_PERMISSIONS if value[0] == 'srm_collection_view')
        permission = Permission(name=definition[0], description=definition[1], module=definition[2])
        db.add(permission)
    actor.role.permissions = [permission]
    db.query(AccessPolicy).filter_by(company_id=1, user_id=actor.id).one().grants = {
        'srm': {'enabled': True, 'permissions': ['srm_collection_view'], 'actions': ['view'], 'scope': 'organization'}}
    db.query(BranchGrant).filter_by(company_id=1, branch_id=unpaid['branch'], user_id=actor.id).one().can_write = False
    db.commit()
    headers['X-Suite-Pack-Context'] = str(unpaid['context'])
    identity = client.get('/api/v1/auth/me', headers=headers)
    access = client.get('/api/v1/access/me', headers=headers)
    assert identity.status_code == access.status_code == 200, (identity.text, access.text)
    user = identity.json()
    role = user['role'] if isinstance(user['role'], str) else (user['role'] or {}).get('name')
    user.update(role=role, primary_role=role, access=access.json())
    monkeypatch.setenv('CONTROL_BROWSER_SCRIPT', 'restaurant-shell-native.cjs')
    monkeypatch.setenv('SUITE_QA_AUTH', json.dumps({'token': headers['Authorization'].split(' ', 1)[1], 'user': user,
        'branch': str(unpaid['branch']), 'context': str(unpaid['context']), 'order': order['id'], 'create': data(unpaid)}))
    test_control_center_real_browser(client, db, None, headers)
    assert db.query(RestaurantServiceOrder).count() == 1
    assert db.query(SRMInvoice).count() == db.query(SRMReceipt).count() == 0
