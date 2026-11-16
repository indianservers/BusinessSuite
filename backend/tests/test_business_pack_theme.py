"""Company theme selection over canonical activations, using real HTTP auth."""
import re
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.access.models import AccessAudit
from app.business_packs import service
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership
from app.models.company import Company
from app.shared.models import ServicePolicy
from app.shared.business_profile import resolve
from tests.test_business_pack_configuration import owner, pack_client

ROOT = '/api/v1/access/settings/business-packs'


@pytest.fixture
def theme(pack_client, db, owner):
    from app.core.security import create_access_token
    actor, branch, other_branch, target = owner
    headers = {'Authorization': 'Bearer ' + create_access_token(actor.id),
        'X-Suite-Organization': '1', 'X-Suite-Branch': str(branch.id)}
    # Published runtime and actual schema/licensing proof, never a readiness
    # monkeypatch or a test-only activation exemption.
    for key in ('hospital', 'salon'):
        proof = service.readiness(db, actor, key)
        assert proof['ready'] is True, proof
    return {'client': pack_client, 'headers': headers, 'actor': actor.id,
        'branch': branch.id, 'other_branch': other_branch.id, 'target': target.id}


def current(case):
    response = case['client'].get(ROOT + '/theme', headers=case['headers'])
    assert response.status_code == 200, response.text
    value = response.json()
    assert re.fullmatch('[0-9a-f]{64}', value['selection_revision'])
    return value


def choose(case, key, *, token=None, status=200, headers=None):
    token = token or current(case)['selection_revision']
    response = case['client'].post(ROOT + '/theme', headers=headers or case['headers'],
        json={'pack_key': key, 'expected_selection': token, 'reason': 'Reviewed company theme choice'})
    assert response.status_code == status, response.text
    return response.json()


def active(db, company=1):
    return [row.pack_key for row in db.query(PackActivation).filter_by(company_id=company, state='active').all()]


def records(db, model):
    return tuple(tuple(row) for row in db.connection().execute(select(model.__table__).order_by(model.__table__.c.id)))


def test_default_general_get_is_readonly_and_does_not_create_configuration(db, theme):
    before = {model: records(db, model) for model in (PackActivation, PackContext, PackUserGrant, ServicePolicy, AccessAudit)}
    value = current(theme)
    assert value['company_id'] == 1 and value['active_key'] == 'general'
    assert value['multiple_active'] is False
    assert value['terminology']['business_type'] == 'general'
    assert value['terminology']['terms'] == resolve([])['terms']
    assert {model: records(db, model) for model in before} == before


def test_select_a_then_b_then_general_keeps_exactly_one_active_and_changes_terms(db, theme):
    first = choose(theme, 'hospital')
    assert first['active_key'] == 'hospital' and active(db) == ['hospital']
    assert first['terminology']['terms'] == resolve([{'business_type': 'hospital'}])['terms']
    second = choose(theme, 'salon')
    assert second['active_key'] == 'salon' and active(db) == ['salon']
    assert second['terminology']['terms'] == resolve([{'business_type': 'salon'}])['terms']
    assert second['selection_revision'] != first['selection_revision']
    general = choose(theme, 'general')
    assert general['active_key'] == 'general' and active(db) == []
    assert general['terminology']['terms'] == resolve([])['terms']
    assert db.query(PackActivation).count() == 2
    assert db.query(ServicePolicy).filter_by(organization_id=1, kind='business_pack_theme').count() == 1
    assert db.query(PackContext).count() == db.query(PackUserGrant).count() == 0


def test_switch_preserves_existing_contexts_grants_anchors_and_foreign_company(db, theme):
    from app.apps.crm.models import CRMCompany
    choose(theme, 'hospital')
    parent = db.query(PackActivation).filter_by(company_id=1, pack_key='hospital').one()
    context = PackContext(company_id=1, branch_id=theme['branch'], activation_id=parent.id,
        pack_key='hospital', pack_version=1, state='active', ever_activated=True)
    db.add(context); db.flush()
    db.add(PackContext(company_id=1, branch_id=theme['other_branch'], activation_id=parent.id,
        pack_key='hospital', pack_version=1, state='draft'))
    db.add(PackUserGrant(company_id=1, branch_id=theme['branch'], context_id=context.id,
        user_id=theme['target'], role='doctor', active=True))
    native_customer = db.query(CRMCompany).filter_by(organization_id=1, branch_id=theme['branch']).first()
    assert native_customer is not None
    db.add(PackRecordOwnership(company_id=1, branch_id=theme['branch'], context_id=context.id,
        resource_table='crm_companies', resource_key=str(native_customer.id), source='explicit-test-history'))
    foreign = Company(name='Foreign theme company', is_active=True)
    db.add(foreign); db.flush()
    foreign_activation = PackActivation(company_id=foreign.id, pack_key='hospital', pack_version=1, state='active')
    db.add(foreign_activation); db.commit()
    foreign_id = foreign_activation.id
    retained = {model: records(db, model) for model in (PackContext, PackUserGrant, PackRecordOwnership)}
    foreign_before = tuple(db.connection().execute(select(PackActivation.__table__).where(PackActivation.id == foreign_id)).one())
    choose(theme, 'salon')
    assert {model: records(db, model) for model in retained} == retained
    assert tuple(db.connection().execute(select(PackActivation.__table__).where(PackActivation.id == foreign_id)).one()) == foreign_before
    assert active(db) == ['salon']


def test_stale_selection_cannot_overwrite_winning_choice_and_can_retry_fresh(db, theme):
    token = current(theme)['selection_revision']
    choose(theme, 'hospital', token=token)
    before = records(db, PackActivation)
    choose(theme, 'salon', token=token, status=409)
    assert records(db, PackActivation) == before and active(db) == ['hospital']
    assert choose(theme, 'salon')['active_key'] == 'salon'


def test_legacy_multiple_active_is_reported_without_silent_migration(db, theme):
    db.add_all([PackActivation(company_id=1, pack_key=key, pack_version=1, state='active')
        for key in ('hospital', 'salon')])
    db.commit()
    before = records(db, PackActivation)
    value = current(theme)
    assert value['active_key'] is None and value['multiple_active'] is True
    assert records(db, PackActivation) == before
    assert choose(theme, 'salon')['active_key'] == 'salon' and active(db) == ['salon']


def test_selection_cas_includes_other_company_activation_rows(db, theme):
    token = current(theme)['selection_revision']
    drafted = theme['client'].post(ROOT + '/activations', headers=theme['headers'], json={
        'pack_key': 'accounting_firm', 'expected_revision': 0, 'reason': 'Concurrent reviewed draft'})
    assert drafted.status_code == 201, drafted.text
    choose(theme, 'hospital', token=token, status=409)
    assert active(db) == []
    assert choose(theme, 'hospital')['active_key'] == 'hospital'


def test_automatic_theme_profile_overrides_legacy_branch_terms_without_rewriting_them(db, theme):
    from app.models.user import User
    from app.branches.service import context
    from app.business_packs.presentation import effective_profile
    from app.shared.business_profile import scope_key, CATALOG
    term = next(iter(CATALOG['terms']))
    legacy = ServicePolicy(scope_key=scope_key(1, theme['branch']), organization_id=1,
        module_key='*', kind='business_profile', updated_by=theme['actor'],
        values_json={'business_type': 'general', 'terms': {term: ['Legacy label', 'Legacy labels']}})
    db.add(legacy); db.commit()
    before = records(db, ServicePolicy)
    choose(theme, 'hospital')
    actor = db.get(User, theme['actor'])
    profile = effective_profile(db, actor, context(db, actor, 1, str(theme['branch'])))
    assert profile['business_type'] == 'hospital'
    assert profile['terms'] == resolve([{'business_type': 'hospital'}])['terms']
    assert tuple(db.connection().execute(select(ServicePolicy.__table__).where(ServicePolicy.id == legacy.id)).one()) in before


def test_strict_selection_payload_cannot_set_branch_context_or_native_grants(db, theme):
    token = current(theme)['selection_revision']
    for extra in ({'branch_id': theme['other_branch']}, {'state': 'active'}, {'role': 'company_admin'}):
        response = theme['client'].post(ROOT + '/theme', headers=theme['headers'], json={
            'pack_key': 'hospital', 'expected_selection': token, 'reason': 'Rejected extra authority', **extra})
        assert response.status_code == 422, response.text
    assert active(db) == [] and db.query(PackContext).count() == db.query(PackUserGrant).count() == 0


@pytest.mark.parametrize('key', ['restaurant', 'pharma', 'retail'])
def test_upcoming_selection_is_blocked_without_suspending_current_pack(db, theme, key):
    choose(theme, 'hospital')
    before = records(db, PackActivation)
    choose(theme, key, status=409)
    assert records(db, PackActivation) == before and active(db) == ['hospital']


def test_nonadmin_and_foreign_company_cannot_select_or_read_company_theme(db, theme):
    from app.core.security import create_access_token
    peer = {**theme['headers'], 'Authorization': 'Bearer ' + create_access_token(theme['target'])}
    token = current(theme)['selection_revision']
    assert theme['client'].get(ROOT + '/theme', headers=peer).status_code == 403
    choose(theme, 'hospital', token=token, headers=peer, status=403)
    foreign = Company(name='Unauthorized theme tenant', is_active=True)
    db.add(foreign); db.commit()
    headers = {**theme['headers'], 'X-Suite-Organization': str(foreign.id)}
    assert theme['client'].get(ROOT + '/theme', headers=headers).status_code == 403
    choose(theme, 'hospital', token=token, headers=headers, status=403)
    assert active(db) == []


def test_late_commit_failure_rolls_back_choice_and_all_activation_states_then_fresh_retry(db, theme):
    choose(theme, 'hospital')
    token = current(theme)['selection_revision']
    before = {model: records(db, model) for model in (PackActivation, ServicePolicy, AccessAudit)}
    def fail(session):
        raise RuntimeError('Late theme commit failure')
    event.listen(db, 'before_commit', fail)
    try:
        with pytest.raises(RuntimeError, match='Late theme commit failure'):
            choose(theme, 'salon', token=token)
    finally:
        event.remove(db, 'before_commit', fail)
        db.rollback()
    assert {model: records(db, model) for model in before} == before
    assert choose(theme, 'salon', token=token)['active_key'] == 'salon'


def test_existing_activation_route_cannot_leave_two_active_packs(db, theme):
    choose(theme, 'hospital')
    response = theme['client'].post(ROOT + '/activations', headers=theme['headers'], json={
        'pack_key': 'salon', 'expected_revision': 0, 'reason': 'Reviewed native draft'})
    assert response.status_code == 201, response.text
    draft = response.json()
    activated = theme['client'].post(ROOT + f'/activations/{draft["id"]}/activate', headers=theme['headers'],
        json={'expected_revision': draft['revision'], 'reason': 'Reviewed native activation'})
    assert activated.status_code == 200, activated.text
    assert active(db) == ['salon'] and current(theme)['active_key'] == 'salon'


def test_only_exact_theme_get_and_post_are_control_routes():
    from app.business_packs.request_scope import classify_route, RouteKind
    for method in ('GET', 'POST'):
        assert classify_route(method, ROOT + '/theme') is RouteKind.CONTROL
        assert classify_route(method, ROOT + '/theme/private-records') is RouteKind.OPERATIONAL
        assert classify_route(method, ROOT + '/theme-forged') is RouteKind.OPERATIONAL
    for method in ('PUT', 'PATCH', 'DELETE'):
        assert classify_route(method, ROOT + '/theme') is RouteKind.OPERATIONAL


def test_theme_activation_does_not_grant_ordinary_user_native_or_operational_access(db, theme):
    from app.access.models import AccessMembership, AccessPolicy
    from app.core.security import create_access_token
    headers = {**theme['headers'], 'Authorization': 'Bearer ' + create_access_token(theme['target'])}
    before = {model: records(db, model) for model in (AccessMembership, AccessPolicy, PackContext, PackUserGrant)}
    denied_before = theme['client'].get('/api/v1/srm/invoices', headers=headers)
    assert denied_before.status_code == 403, denied_before.text
    choose(theme, 'hospital')
    denied_after = theme['client'].get('/api/v1/srm/invoices', headers=headers)
    assert denied_after.status_code == 403, denied_after.text
    assert theme['client'].get(ROOT + '/theme', headers=headers).status_code == 403
    assert {model: records(db, model) for model in before} == before
