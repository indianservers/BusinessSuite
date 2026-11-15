from uuid import uuid4
import pytest
from app.access.models import AccessPolicy
from app.apps.project_management.models import PMSProject, PMSProjectMember, PMSTimeLog
from app.apps.srm.models import SRMEngagement
from app.branches.models import BranchOwnership
from app.business_packs.models import PackRecordOwnership
from tests.test_accounts_periods import accounts, scenario, catalog, directory_identity, create, revision, send
from tests.test_srm_native_transaction_operations import native_writer


@pytest.fixture
def delivery(db, accounts):
    case = accounts
    manager_policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=case['manager'].id).one()
    manager_policy.grants = manager_policy.grants | {'project_management': {'enabled': True,
        'permissions': ['pms_admin'], 'actions': ['view', 'create', 'edit'], 'scope': 'organization'}}
    db.commit()
    with native_writer(db, case['manager'], case['branch']):
        project = PMSProject(organization_id=1, branch_id=case['branch'], name='Canonical client delivery',
            project_key=uuid4().hex[:16], manager_user_id=case['manager'].id)
        db.add(project); db.flush()
        project_id = project.id
    db.add(PackRecordOwnership(company_id=1, branch_id=case['branch'], context_id=case['context'],
        resource_table='pms_projects', resource_key=str(project_id), source='explicit-test-enrollment'))
    if db.get(BranchOwnership, ('pms_projects', str(project_id))) is None:
        db.add(BranchOwnership(company_id=1, branch_id=case['branch'], resource_table='pms_projects',
            resource_key=str(project_id), source='explicit-test-enrollment'))
    # This is an existing native link, not an Accounts birth or a new master.
    db.get(SRMEngagement, case['engagement']).pms_project_id = project_id
    user = case['preparer']['user']
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=user.id).one()
    policy.grants = policy.grants | {'project_management': {'enabled': True,
        'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'own'}}
    db.add(PMSProjectMember(project_id=project_id, user_id=user.id, role='Member'))
    reviewer = case['reviewer']['user']
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=reviewer.id).one()
    policy.grants = policy.grants | {'project_management': {'enabled': True,
        'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'own'}}
    db.add(PMSProjectMember(project_id=project_id,user_id=reviewer.id,role='Viewer'))
    db.commit()
    return project_id


def test_explicit_actual_time_uses_canonical_pms_log_with_retry(client, db, accounts, delivery):
    row = create(client, accounts)
    data = revision(row) | {'log_date': '2026-01-15', 'duration_minutes': 75, 'description': 'Actual reconciliation work'}
    result = send(client, accounts['preparer']['headers'], f"/{row['id']}/time", data, status=201)
    assert send(client, accounts['preparer']['headers'], f"/{row['id']}/time", data, status=201) == result
    assert db.query(PMSTimeLog).count() == 1
    log = db.query(PMSTimeLog).one()
    assert log.project_id == delivery and log.user_id == accounts['preparer']['user'].id
    assert log.duration_minutes == 75 and log.approval_status == 'Pending' and log.timesheet_id is None
    assert db.query(PackRecordOwnership).filter_by(resource_table='pms_time_logs', resource_key=str(log.id),
        context_id=accounts['context']).count() == 1


@pytest.mark.parametrize('fault', ['native_module', 'membership', 'pack_owner', 'stale', 'outside_period'])
def test_assignment_never_overrides_native_project_time_rights(client, db, accounts, delivery, fault):
    row = create(client, accounts)
    status = 403
    data = revision(row) | {'log_date': '2026-01-15', 'duration_minutes': 75, 'description': 'Actual work'}
    user_id = accounts['preparer']['user'].id
    if fault == 'native_module':
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=user_id).one()
        policy.grants = {key: value for key, value in policy.grants.items() if key != 'project_management'}
    elif fault == 'membership':
        db.query(PMSProjectMember).filter_by(project_id=delivery, user_id=user_id).delete()
    elif fault == 'pack_owner':
        db.query(PackRecordOwnership).filter_by(resource_table='pms_projects', resource_key=str(delivery)).delete()
        status = 404
    elif fault == 'stale': data['expected_revision'] = 999; status = 409
    else: data['log_date'] = '2026-02-15'; status = 422
    db.commit()
    send(client, accounts['preparer']['headers'], f"/{row['id']}/time", data, status=status)
    assert db.query(PMSTimeLog).count() == 0


def test_native_time_late_failure_rolls_back_actual_log_and_retry(client, db, accounts, delivery, monkeypatch):
    from app.business_packs.accounting_firm import actual_time
    from fastapi import HTTPException
    row = create(client, accounts)
    data = revision(row) | {'log_date': '2026-01-15', 'duration_minutes': 30, 'description': 'Actual work'}
    original = actual_time.create_actual_time
    def fail_after_native(*args, **kwargs):
        original(*args, **kwargs)
        raise HTTPException(409, 'Injected late time failure')
    monkeypatch.setattr(actual_time, 'create_actual_time', fail_after_native)
    send(client, accounts['preparer']['headers'], f"/{row['id']}/time", data, status=409)
    assert db.query(PMSTimeLog).count() == 0
    assert db.query(PackRecordOwnership).filter_by(resource_table='pms_time_logs').count() == 0
    monkeypatch.setattr(actual_time, 'create_actual_time', original)
    send(client, accounts['preparer']['headers'], f"/{row['id']}/time", data, status=201)
    assert db.query(PMSTimeLog).count() == 1


def test_unchanged_subscription_expiring_during_native_write_rolls_back(client, db, accounts, delivery, monkeypatch):
    from datetime import datetime, timezone, timedelta
    from app.enterprise import controls
    from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
    from app.access.catalog import MODULES
    from app.apps.project_management.api import router
    now = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    clock = {'now': now}
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock['now'].astimezone(tz) if tz else clock['now'].replace(tzinfo=None)
    monkeypatch.setattr(controls, 'datetime', Clock)
    plan = TenantSubscriptionPlan(code=uuid4().hex, name='Native expiry test', config_json={
        'enforce': True, 'modules': list(MODULES), 'expiry_policy': 'restrict',
        'grace_until': (now + timedelta(minutes=1)).isoformat()})
    db.add(plan); db.flush()
    subscription = db.query(TenantSubscription).filter_by(company_id=1).one_or_none()
    if subscription is None:
        subscription = TenantSubscription(company_id=1)
        db.add(subscription)
    subscription.plan_id = plan.id
    subscription.status = 'active'
    subscription.config_json = {}
    db.commit()
    row = create(client, accounts)
    original = router.create_time_log_operation
    def expire_after_native(*args, **kwargs):
        result = original(*args, **kwargs)
        clock['now'] = now + timedelta(minutes=2)
        return result
    monkeypatch.setattr(router, 'create_time_log_operation', expire_after_native)
    send(client, accounts['preparer']['headers'], f"/{row['id']}/time", revision(row) | {
        'log_date': '2026-01-15', 'duration_minutes': 30, 'description': 'Actual work'}, status=403)
    assert db.query(PMSTimeLog).count() == 0
    assert db.query(PackRecordOwnership).filter_by(resource_table='pms_time_logs').count() == 0
