"""Actual non-superuser configuration requests must roll back the whole birth."""
import pytest
from fastapi import HTTPException
from sqlalchemy import event

from tests.test_restaurant_customer_assignment import walkin, unpaid, scenario, catalog, directory_identity
from tests.test_business_pack_http_integration import native_actor, grant


def counts(db):
    from app.apps.crm.models import CRMCompany, CRMContact
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails, BusinessRelationship, ContactChannel
    from app.apps.srm.commercial_models import CustomerLink
    from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
    from app.business_packs.models import PackMasterAvailability
    from app.models.audit import AuditLog
    result = {model.__tablename__: db.query(model).count() for model in (
        CRMCompany, CRMContact, ContactIdentityLink, CompanyMasterDetails,
        BusinessRelationship, ContactChannel, CustomerLink, AnonymousCashAccount, PackMasterAvailability)}
    result['canonical_audit'] = db.query(AuditLog).filter_by(action='COMPANY_MASTER_SAVED').count()
    return result


@pytest.mark.parametrize('phase', ['after_enrollment', 'typed_account', 'final_audit'])
def test_real_http_late_configuration_failure_leaves_no_born_graph(client, db, walkin, monkeypatch, phase):
    from app.business_packs.models import PackContext
    from app.business_packs import anonymous_birth as birth, anonymous_definitions as definitions
    from app.apps.srm.anonymous_cash_models import AnonymousCashAccount
    case = walkin
    headers, admin = native_actor(db, case['branch'], admin=True,
        actions=('view', 'create', 'edit', 'approve', 'configure'))
    assert not admin.is_superuser
    grant(db, admin, case['branch'], 'restaurant', 'business_owner', db.get(PackContext, case['context']))
    before = counts(db)
    reached = []
    def fail():
        reached.append(phase)
        raise HTTPException(409, 'Injected isolated late configuration failure')
    listener = None
    if phase == 'after_enrollment':
        original = birth.enroll_born_account
        def enrolled(*args, **kwargs):
            original(*args, **kwargs)
            fail()
        monkeypatch.setattr(birth, 'enroll_born_account', enrolled)
    elif phase == 'typed_account':
        def listener(*args):
            fail()
        event.listen(AnonymousCashAccount, 'before_insert', listener)
    else:
        from app.apps.srm.api import router
        original = router._audit
        def audited(db, user, kind, *args, **kwargs):
            if kind == 'anonymous_cash_account':
                fail()
            return original(db, user, kind, *args, **kwargs)
        monkeypatch.setattr(router, '_audit', audited)
    try:
        response = client.put('/api/v1/srm/anonymous-cash/configuration', headers={**headers,
            'X-Suite-Organization': '1', 'X-Suite-Branch': str(case['branch']),
            'X-Suite-Pack-Context': str(case['context'])}, json={
                'action': 'create', 'label': 'Rollback counter control', 'jurisdiction_country': 'IN',
                'reason': 'Prove atomic isolated canonical account rollback'})
    finally:
        if listener is not None:
            event.remove(AnonymousCashAccount, 'before_insert', listener)
    assert reached == [phase]
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'Injected isolated late configuration failure'
    assert counts(db) == before
    assert not birth._active and not definitions._leases
    assert db.info.get('business_pack_scope') is None
    assert db.info.get('business_pack_policy') is None
