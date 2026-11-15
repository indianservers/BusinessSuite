from contextlib import contextmanager
from dataclasses import replace
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
from app.models.user import User
from app.business_packs.restaurant import references, tabs
from app.business_packs.restaurant.models import RestaurantServiceOrder, RestaurantTabLine
from app.business_packs.models import PackContext
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from tests.test_restaurant_tabs import unpaid, data, stock, nothing_billed, scenario, catalog, directory_identity
from tests.test_restaurant_kitchen import post, staff
from tests.test_srm_native_transaction_operations import native_writer

BASE = '/api/v1/srm/restaurant'


def addition(case, order):
    return {'request_key': str(uuid4()), 'expected_revision': order['revision'], 'lines': data(case)['lines']}


def test_independent_server_adds_native_charges_without_reassigning_original_creator(client, db, unpaid):
    order = post(client, unpaid['headers'], '/tabs', data(unpaid))
    headers, actor = staff(db, unpaid, 'server')
    before = stock(db, unpaid)
    result = post(client, headers, f"/tabs/{order['id']}/items", addition(unpaid, order))
    native = db.get(SRMSalesOrder, order['sales_order_id'])
    assert native.assigned_user_id == native.created_by == unpaid['manager'].id != actor.id
    assert len(result['items']) == 2 and native.total_amount == 236
    assert nothing_billed(db) == (0, 0, 0) and stock(db, unpaid) == before
    assert not references._leases


@pytest.mark.parametrize('fault', ['assignment', 'other_field', 'line', 'revision'])
def test_header_certificate_rejects_unplanned_changes_atomically(client, db, unpaid, monkeypatch, fault):
    order = post(client, unpaid['headers'], '/tabs', data(unpaid))
    headers, _ = staff(db, unpaid, 'server')
    original = references.header_update
    @contextmanager
    def poisoned(db, actor, scope, epoch, native, root, totals):
        with original(db, actor, scope, epoch, native, root, totals):
            if fault == 'assignment':
                native.assigned_user_id = actor.id
            elif fault == 'other_field':
                native.terms = 'An unplanned change'
            elif fault == 'line':
                native.lines[0].unit_price = 1
            else:
                root.revision += 1
            yield
    monkeypatch.setattr(references, 'header_update', poisoned)
    before = stock(db, unpaid)
    response = client.post(BASE+f"/tabs/{order['id']}/items", headers=headers, json=addition(unpaid, order))
    assert response.status_code == 403, response.text
    assert db.query(SRMSalesOrderLine).count() == db.query(RestaurantTabLine).count() == 1
    actual = db.connection().execute(select(SRMSalesOrder.assigned_user_id, SRMSalesOrder.total_amount, SRMSalesOrder.terms).where(SRMSalesOrder.id == order['sales_order_id'])).one()
    assert tuple(actual) == (unpaid['manager'].id, 118, None)
    assert stock(db, unpaid) == before and not references._leases


def test_certificate_does_not_cross_session_scope_source_or_fk(client, db, unpaid):
    order = post(client, unpaid['headers'], '/tabs', data(unpaid))
    _, actor = staff(db, unpaid, 'server')
    with native_writer(db, actor, unpaid['branch']):
        scope = resolve_context(db, actor, db.info['branch_context'], unpaid['context'])
        cleanup = install(db, scope, policy=native_srm_policy('restaurant').policy)
        try:
            scope, epoch = tabs.writer(db, actor)
            native = db.get(SRMSalesOrder, order['sales_order_id'])
            root = db.get(RestaurantServiceOrder, order['id'])
            pair = (('assigned_user_id', User.__table__.c.id),)
            db.info['restaurant_header_certificate'] = True  # Not an authority source.
            assert references.reference(db, scope, native, User.__table__, pair) is False
            with references.header_update(db, actor, scope, epoch, native, root,
                    (native.subtotal, native.discount_amount, native.tax_amount, native.total_amount)):
                with Session(bind=db.connection()) as other:
                    other.info['business_pack_scope'] = scope
                    assert references.reference(other, scope, native, User.__table__, pair) is False
                assert references.reference(db, replace(scope, context_id=999999), native, User.__table__, pair) is False
                assert references.reference(db, scope, root, User.__table__, pair) is False
                assert references.reference(db, scope, native, User.__table__, (('created_by', User.__table__.c.id),)) is False
            assert references.reference(db, scope, native, User.__table__, pair) is False
            assert not references._leases
        finally:
            db.info.pop('restaurant_header_certificate', None)
            cleanup()


@pytest.mark.parametrize('fault', ['foreign_assignment', 'revoked_assignee_company'])
def test_unchanged_corrupt_assignee_is_not_blessed_by_header_certificate(client, db, unpaid, fault):
    from app.access.models import AccessMembership
    order = post(client, unpaid['headers'], '/tabs', data(unpaid))
    headers, actor = staff(db, unpaid, 'server')
    if fault == 'foreign_assignment':
        from tests.test_settings_hub import actor as account
        from app.models.company import Company
        _, foreign = account(db, role='foreign-tab-'+uuid4().hex, permissions=['srm_view'])
        if db.get(Company, 991) is None:
            db.add(Company(id=991, name='Unrelated assignee company'))
            db.flush()
        db.query(AccessMembership).filter_by(user_id=foreign.id, company_id=1).delete(synchronize_session=False)
        db.add(AccessMembership(user_id=foreign.id, company_id=991, active=True))
        db.flush()
        db.connection().execute(SRMSalesOrder.__table__.update().where(SRMSalesOrder.id == order['sales_order_id']).values(assigned_user_id=foreign.id))
    else:
        member = db.query(AccessMembership).filter_by(company_id=1, user_id=unpaid['manager'].id).one()
        member.active = False
    db.commit()
    response = client.post(BASE+f"/tabs/{order['id']}/items", headers=headers, json=addition(unpaid, order))
    assert response.status_code == 403, response.text
    assert db.query(SRMSalesOrderLine).count() == db.query(RestaurantTabLine).count() == 1
    assert not references._leases
