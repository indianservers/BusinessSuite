"""Native aggregate facts are scoped to one selected Construction context."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.branches.models import BranchOwnership
from app.business_packs.models import PackContext, PackRecordOwnership
from app.shared.follow_ups import FollowUp
from tests.test_business_pack_construction import construction, scenario, catalog, directory_identity

URL = '/api/v1/follow-ups/statistics'


def seed(db, actor, branch, context_id, *, status='Scheduled', days=2,
         company=1, creator=None, assigned=None, team=None, native_branch=None, pack_context=None):
    row = FollowUp(organization_id=company, customer_id=101, title='Private site follow-up',
        assigned_user_id=assigned or actor.id, created_by=creator or actor.id, assigned_team_id=team,
        due_at=datetime.now(timezone.utc) + timedelta(days=days), timezone='UTC', status=status,
        source_key='site-statistics:' + uuid4().hex, configuration={})
    db.add(row); db.flush()
    key = dict(resource_table='service_follow_ups', resource_key=str(row.id))
    existing = db.get(BranchOwnership, ('service_follow_ups', str(row.id)))
    if existing is None:
        db.add(BranchOwnership(**key, company_id=1, branch_id=native_branch or branch, source='explicit-test-enrollment'))
    else:
        existing.company_id = 1
        existing.branch_id = native_branch or branch
    db.add(PackRecordOwnership(**key, company_id=1, branch_id=branch,
        context_id=pack_context or context_id, source='explicit-test-enrollment'))
    db.commit()
    return row.id


def test_selected_native_statistics_returns_actual_counts_and_filters_both_ownership_layers(client, db, construction, catalog):
    from app.models.company import Branch, Company
    from tests.test_business_pack_http_integration import grant
    actor, branch, context_id, _ = construction
    other_context, _ = grant(db, actor, branch, 'retail', 'store_manager')
    foreign_branch = Branch(company_id=1, name='Other statistics branch', code='OTHER-STATS', is_active=True)
    foreign_company = Company(name='Other statistics company')
    db.add_all([foreign_branch, foreign_company]); db.commit()
    seed(db, actor, branch, context_id, days=-1)
    seed(db, actor, branch, context_id, status='Completed', days=-1)
    seed(db, actor, branch, context_id, status='Rescheduled', days=3)
    seed(db, actor, branch, context_id, pack_context=other_context.id)
    seed(db, actor, branch, context_id, native_branch=foreign_branch.id)
    seed(db, actor, branch, context_id, company=foreign_company.id)
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    before = db.query(FollowUp).count()
    response = client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {'Total': 3, 'Due': 0, 'Overdue': 1, 'Completed': 1,
        'Rescheduled': 1, 'Missed': 0, 'Upcoming 7 Days': 1, 'Conversion Rate': 33.3}
    assert client.get(URL, headers=headers).json() == response.json()
    assert db.query(FollowUp).count() == before


def test_native_non_admin_visibility_and_revoked_view_are_not_replaced_by_pack_role(client, db, construction):
    from app.access.models import AccessPolicy
    from tests.test_business_pack_http_integration import native_actor, grant
    actor, branch, context_id, _ = construction
    headers, reader = native_actor(db, branch)
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=reader.id).one()
    policy.grants = {'srm': {'enabled': True, 'permissions': ['srm_view'], 'actions': ['view'], 'scope': 'organization'}}
    db.commit()
    grant(db, reader, branch, 'construction', 'project_manager', db.get(PackContext, context_id))
    seed(db, actor, branch, context_id, creator=reader.id, assigned=reader.id)
    seed(db, actor, branch, context_id)
    headers = {**headers, 'X-Suite-Pack-Context': str(context_id)}
    response = client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['Total'] == 1
    # Native team ownership remains a real source, rather than substituting
    # pack role or broad organization visibility for visible()'s predicate.
    from app.apps.crm.models import CRMTeam, CRMOwner
    team = CRMTeam(organization_id=1, name='Construction follow-up team', owner_user_id=reader.id)
    db.add(team); db.flush()
    owner = CRMOwner(organization_id=1, user_id=reader.id, team_id=team.id,
        full_name='Native team reader', email='statistics-' + uuid4().hex + '@example.com')
    db.add(owner); db.commit()
    seed(db, actor, branch, context_id, team=team.id)
    policy.grants = {**policy.grants, 'crm': {'enabled': True, 'permissions': ['crm_view'],
        'actions': ['view'], 'scope': 'organization'}}
    db.commit()
    team_response = client.get(URL, headers=headers)
    assert team_response.status_code == 200 and team_response.json()['Total'] == 2, team_response.text
    owner.deleted_at = datetime.now(timezone.utc); db.commit()
    assert client.get(URL, headers=headers).json()['Total'] == 1
    policy.grants = {'srm': {'enabled': False, 'permissions': [], 'actions': [], 'scope': 'organization'}}
    policy.version += 1
    db.commit()
    denied = client.get(URL, headers=headers)
    assert denied.status_code == 403, denied.text


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_same_actor_specialist_context_cannot_read_construction_statistics(client, db, construction, catalog, pack, role):
    from tests.test_business_pack_http_integration import grant
    actor, branch, context_id, _ = construction
    seed(db, actor, branch, context_id)
    other, _ = grant(db, actor, branch, pack, role)
    response = client.get(URL, headers={**catalog[0], 'X-Suite-Pack-Context': str(other.id)})
    assert response.status_code == 403, response.text


def test_resource_rejects_callable_substitution_and_keeps_operational_boundary(db, construction):
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.construction_followups import statistics
    from tests.test_srm_native_transaction_operations import native_writer
    actor, branch, context_id, _ = construction
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            transaction = db.connection().get_transaction()
            with pytest.raises(HTTPException) as denied:
                statistics(db, actor, lambda *_: {'Total': 999})
            assert denied.value.status_code == 403
            assert statistics(db, actor)['Total'] == 0
            assert db.info['business_pack_scope'] is scope
            assert db.connection().get_transaction() is transaction and transaction.is_active
            from app.apps.project_management.models import PMSProject
            with pytest.raises(HTTPException):
                db.query(PMSProject).all()
        finally:
            cleanup()


def test_native_resource_denies_extra_sources_raw_connection_and_writes(client, db, construction, catalog, monkeypatch):
    from sqlalchemy import select, text
    from app.apps.project_management.models import PMSProject
    from app.shared import follow_ups
    _, _, context_id, _ = construction
    original = follow_ups._statistics_operation
    def inspect_reader(native, principal):
        for attempt in (lambda: native.query(PMSProject).all(), lambda: native.execute(text('SELECT 1')),
                        lambda: native.connection().execute(select(PMSProject.__table__)), lambda: native.get_bind(),
                        lambda: native.bind, lambda: native.commit(), lambda: native.begin_nested()):
            with pytest.raises(HTTPException) as denied:
                attempt()
            assert denied.value.status_code == 403
        return original(native, principal)
    monkeypatch.setattr(follow_ups, '_statistics_operation', inspect_reader)
    response = client.get(URL, headers={**catalog[0], 'X-Suite-Pack-Context': str(context_id)})
    assert response.status_code == 200, response.text
    assert response.json()['Total'] == 0


def test_statistics_rechecks_pack_grant_after_aggregate(client, db, construction, catalog, monkeypatch):
    from sqlalchemy import update
    from app.business_packs.models import PackUserGrant
    from app.shared import follow_ups
    actor, _, context_id, _ = construction
    original = follow_ups._statistics_operation
    def revoke_after_read(native, principal):
        result = original(native, principal)
        table = PackUserGrant.__table__
        db.connection().execute(update(table).where(table.c.context_id == context_id, table.c.user_id == actor.id).values(active=False))
        return result
    monkeypatch.setattr(follow_ups, '_statistics_operation', revoke_after_read)
    response = client.get(URL, headers={**catalog[0], 'X-Suite-Pack-Context': str(context_id)})
    assert response.status_code == 403, response.text
