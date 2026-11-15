from dataclasses import replace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from app.business_packs.boundary import PackSourceLink, install
from app.apps.communication.customer_models import CustomerEvent
from app.apps.srm.models import SRMSalesOrder
from tests.test_business_pack_boundary import native, POLICY
from tests.test_business_pack_access import packs


def source_policy():
    return replace(POLICY, record_tables=POLICY.record_tables | {'communication_customer_events'},
        source_links=(PackSourceLink('communication_customer_events', 'source_type', 'source_id',
                                    (('order', 'srm_sales_orders'),)),))


def event(n, source_id, kind='order'):
    return CustomerEvent(organization_id=1, branch_id=n.scope.branch_id,
                         source_type=kind, source_id=source_id, event_key=uuid4().hex,
                         trigger='order.changed', snapshot={})


def test_native_event_has_its_own_anchor_and_private_source_proof(native):
    n = native; cleanup = install(n.db, n.scope, policy=source_policy())
    try:
        row = event(n, n.ids['own'])
        row._suite_source_record = n.db.get(SRMSalesOrder, n.ids['own'])
        n.db.add(row); n.db.flush()
        assert [e.id for e in n.db.query(CustomerEvent)] == [row.id]
        row.status = 'processed'; n.db.flush()
        assert n.db.get(CustomerEvent, row.id).status == 'processed'
        with pytest.raises(HTTPException) as error, n.db.begin_nested():
            row.source_id = n.ids['foreign']
            n.db.flush()
        assert error.value.status_code == 403
    finally:
        cleanup()


@pytest.mark.parametrize('case', ['foreign', 'legacy', 'missing', 'unknown_kind', 'boolean', 'spoof_marker'])
def test_source_cross_context_or_unowned_reference_rolls_back_event(native, case):
    n = native; cleanup = install(n.db, n.scope, policy=source_policy())
    try:
        before = n.db.query(CustomerEvent).count()
        source_id = {'foreign': n.ids['foreign'], 'legacy': n.ids['legacy'],
                     'missing': 2147483647, 'boolean': True}.get(case, n.ids['own'])
        with pytest.raises(HTTPException) as error, n.db.begin_nested():
            row = event(n, source_id, kind='lead' if case == 'unknown_kind' else 'order')
            if case == 'spoof_marker':
                row._suite_source_record = object()
            n.db.add(row); n.db.flush()
        assert error.value.status_code == 403
        assert n.db.query(CustomerEvent).count() == before
    finally:
        cleanup()


def test_shared_customer_is_not_an_operational_event_source(native):
    bad = replace(POLICY, record_tables=POLICY.record_tables | {'communication_customer_events'},
                  source_links=(PackSourceLink('communication_customer_events', 'source_type', 'source_id',
                                               (('customer', 'crm_companies'),)),))
    assert 'crm_companies' in bad.master_tables
    # Installation, rather than a public body, validates the registered graph.
    with pytest.raises(ValueError):
        install(native.db, native.scope, policy=bad)
