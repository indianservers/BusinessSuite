"""Actual canonical schedules, WBS cost budgets and certified physical progress."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import update

from app.apps.project_management.models import PMSProject, PMSWorkspaceMember
from app.apps.srm.industry_models import IndustryRecord
from app.apps.project_management.scheduling import BaselineInput
from app.business_packs import construction_planning as planning
from tests.test_construction_planning import site_plan, selected, construction, scenario, catalog, directory_identity
from tests.test_business_pack_construction import independent_approver

ROOT = '/api/v1/srm/industry'


def post(client, headers, path, data, status=201):
    response = client.post(ROOT + path, headers=headers, json=data)
    assert response.status_code == status, response.text
    return response.json()


@pytest.fixture
def controls(client, db, site_plan, catalog):
    case, tasks, _ = site_plan
    actor, branch, context_id, project_id = case
    project = db.get(PMSProject, project_id)
    project.estimated_cost, project.actual_cost = Decimal('1000'), Decimal('400')
    db.commit()
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    reviewer, approver = independent_approver(db, branch, context_id, project_id)
    db.add(PMSWorkspaceMember(workspace_id=project.workspace_id, user_id=approver.id, role='Admin'))
    db.commit()
    boq = post(client, headers, '/boq', {'request_id': str(uuid4()), 'title': 'Contract selling scope',
        'project_id': project_id, 'code': 'EVM', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1200', 'tax_rate': '0'})
    post(client, reviewer, f'/records/{boq["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    packages = []
    for task_id, quantity, budget in zip(tasks, ('6', '4'), ('600', '400')):
        packages.append(post(client, headers, '/work-packages', {'request_id': str(uuid4()),
            'title': f'WBS budget {task_id}', 'project_id': project_id, 'task_id': task_id,
            'boq_id': boq['id'], 'quantity': quantity, 'budget_cost': budget}))
    with selected(db, case) as native_actor:
        current = planning.analysis(db, native_actor, project_id)
        baseline = planning.capture(db, native_actor, project_id,
            BaselineInput(name='Canonical dated schedule', expected_revision=current['revision']))
    return {'case': case, 'headers': headers, 'reviewer': reviewer, 'approver': approver,
        'tasks': tasks, 'boq': boq, 'packages': packages, 'native_baseline': baseline}


def prepare(client, case, **extra):
    return post(client, case['headers'], '/planning-baselines', {'request_id': str(uuid4()),
        'title': 'Approved cost and physical scope', 'project_id': case['case'][3],
        'native_baseline_id': case['native_baseline']['id'], **extra})


def approve(client, case, baseline):
    return post(client, case['reviewer'], f'/planning-baselines/{baseline["id"]}/review',
        {'expected_revision': 1, 'status': 'approved'}, 200)


def test_independent_cost_baseline_and_actual_earned_value_not_selling_value(client, db, controls):
    case = controls
    baseline = prepare(client, case)
    assert Decimal(baseline['data']['budget_at_completion']) == 1000
    assert Decimal(baseline['data']['budget_at_completion']) != 12000, 'Sales price is not an EVM cost budget'
    post(client, case['headers'], f'/planning-baselines/{baseline["id"]}/review',
        {'expected_revision': 1, 'status': 'approved'}, 403)
    approved = approve(client, case, baseline)
    assert approved['approved_by'] == case['approver'].id
    measured = post(client, case['headers'], '/measurements', {'request_id': str(uuid4()),
        'title': 'Actual WBS physical quantity', 'boq_id': case['boq']['id'],
        'work_package_id': case['packages'][0]['id'], 'quantity': '3', 'measured_on': date.today().isoformat()})
    post(client, case['reviewer'], f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    for workforce in (8, 8):
        post(client, case['headers'], '/site-diaries', {'request_id': str(uuid4()), 'title': 'Daily site headcount',
            'project_id': case['case'][3], 'entry_date': date.today().isoformat(), 'work_done': 'Measured works', 'workforce': workforce})
    response = client.get(ROOT + f'/projects/{case["case"][3]}/performance', headers=case['headers'],
        params={'baseline_id': baseline['id'], 'as_of': date.today().isoformat()})
    assert response.status_code == 200, response.text
    result = response.json()
    assert Decimal(result['BAC']) == 1000 and Decimal(result['EV']) == 300 and Decimal(result['AC']) == 400
    assert Decimal(result['CPI']) == Decimal('0.75')
    assert Decimal(result['CV']) == -100 and Decimal(result['EAC']) == Decimal('1333.33')
    assert Decimal(result['ETC']) == Decimal('933.33')
    assert result['workforce_days'] == (8 if date.today() >= date(2026, 11, 16) else 0), 'Same-day site counts must not double count the same workforce'
    export = client.get(ROOT + f'/projects/{case["case"][3]}/client-report', headers=case['headers'],
        params={'baseline_id': baseline['id'], 'as_of': date.today().isoformat(), 'format': 'csv'})
    assert export.status_code == 200, export.text
    assert b'planning.EV,300.00' in export.content and b'planning.BAC,1000.00' in export.content


def test_unapproved_stale_and_incomplete_budget_baselines_fail_closed(client, db, controls):
    case = controls
    baseline = prepare(client, case)
    response = client.get(ROOT + f'/projects/{case["case"][3]}/performance', headers=case['headers'],
        params={'baseline_id': baseline['id'], 'as_of': '2026-11-16'})
    assert response.status_code == 409, response.text
    package = case['packages'][0]
    changed = client.put(ROOT + f'/work-packages/{package["id"]}', headers=case['headers'], json={
        'expected_revision': 1, 'quantity': '6', 'budget_cost': '599', 'notes': 'Budget still needs review'})
    assert changed.status_code == 200, changed.text
    post(client, case['reviewer'], f'/planning-baselines/{baseline["id"]}/review',
        {'expected_revision': 1, 'status': 'approved'}, 409)
    post(client, case['headers'], '/planning-baselines', {'request_id': str(uuid4()), 'title': 'Incomplete allocation',
        'project_id': case['case'][3], 'native_baseline_id': case['native_baseline']['id']}, 409)


def test_historical_cost_missing_and_zero_earned_value_are_explicit(client, db, controls):
    case = controls
    baseline = prepare(client, case)
    approve(client, case, baseline)
    path = ROOT + f'/projects/{case["case"][3]}/performance'
    result = client.get(path, headers=case['headers'], params={'baseline_id': baseline['id'], 'as_of': date.today().isoformat()})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['EV'] == '0.00' and data['CPI'] == '0.00' and data['EAC'] is None
    historical = client.get(path, headers=case['headers'], params={'baseline_id': baseline['id'], 'as_of': '2020-01-01'})
    assert historical.status_code == 200, historical.text
    assert historical.json()['AC'] is None and historical.json()['cost_unavailable_reason']
    db.get(PMSProject, case['case'][3]).actual_cost = None; db.commit()
    missing = client.get(path, headers=case['headers'], params={'baseline_id': baseline['id'], 'as_of': date.today().isoformat()})
    assert missing.status_code == 200 and missing.json()['AC'] is None, missing.text


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_other_pack_same_actor_cannot_read_cost_or_prepare_baseline(client, db, controls, pack, role):
    from tests.test_business_pack_http_integration import grant
    case = controls
    actor, branch, _, project_id = case['case']
    context, _ = grant(db, actor, branch, pack, role)
    headers = {**case['headers'], 'X-Suite-Pack-Context': str(context.id)}
    response = client.get(ROOT + f'/projects/{project_id}/planning-baselines', headers=headers)
    assert response.status_code == 403, response.text
    post(client, headers, '/planning-baselines', {'request_id': str(uuid4()), 'title': 'Forbidden baseline',
        'project_id': project_id, 'native_baseline_id': case['native_baseline']['id']}, 403)


def _own_controls_workspace(db, case):
    from app.apps.project_management.models import PMSWorkspace
    from tests.test_construction_planning import own
    project = db.get(PMSProject, case['case'][3])
    own(db, case['case'], db.get(PMSWorkspace, project.workspace_id))
    db.commit()


def test_dated_native_cost_actual_history_drives_exact_historical_ac_and_rejects_currency(client, db, controls):
    from datetime import timedelta
    case = controls
    _own_controls_workspace(db, case)
    baseline = approve(client, case, prepare(client, case))
    pid = case['case'][3]
    path = f'/projects/{pid}'
    dates = [date.today() - timedelta(days=2), date.today() - timedelta(days=1)]
    prior = '400'
    for day, amount in zip(dates, ('125', '175')):
        result = post(client, case['headers'], path + '/cost-actuals', {
            'request_id': str(uuid4()), 'expected_actual_cost': prior, 'cumulative_actual_cost': amount,
            'currency': 'INR', 'as_of': day.isoformat(), 'reason': 'Dated supplier and workforce costs'}, 200)
        assert Decimal(str(result['actual_cost'])) == Decimal(amount)
        prior = amount
    post(client, case['headers'], path + '/cost-actuals', {
        'request_id': str(uuid4()), 'expected_actual_cost': '175', 'cumulative_actual_cost': '250',
        'currency': 'USD', 'as_of': date.today().isoformat(), 'reason': 'Wrong currency is rejected'}, 409)
    for day, amount in zip(dates + [date.today()], ('125', '175', '175')):
        response = client.get(ROOT + path + '/performance', headers=case['headers'],
            params={'baseline_id': baseline['id'], 'as_of': day.isoformat()})
        assert response.status_code == 200, response.text
        assert response.json()['AC'] == amount + '.00'
        assert response.json()['currency'] == 'INR'
        assert response.json()['cost_unavailable_reason'] is None
        if day < date.today():
            assert 'Dated canonical PMS actual-cost change #' in response.json()['actual_cost_source']
    history = db.query(IndustryRecord).filter_by(project_id=pid, kind='cost_actual').all()
    assert len(history) == 2
    assert [row.data['source_before'] for row in history] == ['400.00', '125.00']
    assert db.get(PMSProject, pid).actual_cost == Decimal('175')


@pytest.mark.parametrize('mutation', ['approved_snapshot', 'kind_switch', 'delete'])
def test_approved_baseline_snapshot_and_kind_identity_are_immutable(client, db, controls, mutation):
    from fastapi import HTTPException
    case = controls
    baseline = approve(client, case, prepare(client, case))
    with selected(db, case['case']):
        row = db.get(IndustryRecord, baseline['id'])
        if mutation == 'approved_snapshot':
            row.data = {**row.data, 'budget_at_completion': '1'}
        elif mutation == 'kind_switch':
            row.kind = 'appointment'
        else:
            db.delete(row)
        with pytest.raises(HTTPException) as denied:
            db.flush()
        assert denied.value.status_code == 403
        db.rollback()
    original = db.get(IndustryRecord, baseline['id'])
    assert original.kind == 'planning_baseline' and original.status == 'approved'
    assert Decimal(original.data['budget_at_completion']) == 1000


def test_native_new_wbs_task_requires_revised_schedule_and_cost_baseline(client, db, controls):
    from tests.test_construction_definition import task_body
    case = controls
    _own_controls_workspace(db, case)
    baseline = approve(client, case, prepare(client, case))
    pid = case['case'][3]
    created = post(client, case['headers'], f'/projects/{pid}/wbs-tasks', task_body())
    assert created['project_id'] == pid
    performance = client.get(ROOT + f'/projects/{pid}/performance', headers=case['headers'],
        params={'baseline_id': baseline['id'], 'as_of': date.today().isoformat()})
    assert performance.status_code == 409, performance.text
    assert 'actual WBS task set changed' in performance.json()['detail']
    post(client, case['headers'], '/planning-baselines', {'request_id': str(uuid4()),
        'title': 'Old native task set cannot be approved again', 'project_id': pid,
        'native_baseline_id': case['native_baseline']['id']}, 409)
    original = db.get(IndustryRecord, baseline['id'])
    assert original.status == 'approved' and Decimal(original.data['budget_at_completion']) == 1000


def test_baseline_audit_hook_native_revocation_after_flush_prevents_commit(client, db, controls, monkeypatch):
    from app.apps.srm import industry_api
    from app.models.user import User
    from app.apps.srm.models import SRMAuditLog
    case = controls
    actor = case['case'][0]
    native_audit = industry_api.audit
    retained = db.query(IndustryRecord).filter_by(kind='planning_baseline').count()
    retained_audit = db.query(SRMAuditLog).filter_by(entity_type='industry_planning_baseline').count()
    touched = []
    def revoke_after_audit(session, principal, row, action):
        native_audit(session, principal, row, action)
        if row.kind == 'planning_baseline' and action == 'baseline_prepared':
            touched.append(row.id)
            table = User.__table__
            session.connection().execute(update(table).where(table.c.id == actor.id).values(is_active=False))
    with monkeypatch.context() as fault:
        fault.setattr(industry_api, 'audit', revoke_after_audit)
        rejected = client.post(ROOT + '/planning-baselines', headers=case['headers'], json={
            'request_id': str(uuid4()), 'title': 'Authority revoked after native flush', 'project_id': case['case'][3],
            'native_baseline_id': case['native_baseline']['id']})
    assert rejected.status_code == 403, rejected.text
    assert touched and db.query(IndustryRecord).filter_by(kind='planning_baseline').count() == retained
    assert db.query(SRMAuditLog).filter_by(entity_type='industry_planning_baseline').count() == retained_audit
    db.expire_all()
    assert db.get(User, actor.id).is_active
