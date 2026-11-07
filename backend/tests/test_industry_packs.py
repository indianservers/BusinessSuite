import copy
from datetime import timedelta
import pytest
from app.apps.industry_packs import service
from app.apps.crm.models import CRMDeal, CRMTask, CRMCustomField, CRMPipeline
from app.apps.analytics.models import AnalyticsReport
from app.apps.automation.models import AutomationWorkflow, AutomationScheduledJob
from app.shared.models import ServiceEvent, WorkflowVersion
from app.shared import runtime
from app.models.user import Permission, User
from app.models.notification import Notification
from app.forms.models import SuiteForm
from app.access.models import AccessTemplate, AccessPolicy
from tests.test_shared_services import shared_setup, access_account
from tests.test_suite_access import login

ROOT = '/api/v1/industry-packs'


@pytest.fixture
def setup(shared_setup, db):
    h, executor, lead = shared_setup
    # Report roles use already provisioned native permission names.
    for name in ['analytics_view', 'analytics_report_builder', 'automation_manage']:
        if not db.query(Permission).filter_by(name=name).first():
            db.add(Permission(name=name, module=name.split('_')[0]))
    db.commit()
    return h, executor


def install(client, setup, key='salon-spa', **extra):
    h, executor = setup
    response = client.post(f'{ROOT}/{key}/install', headers=h, json={'run_as_user_id': executor.id, 'modules': ['crm'], **extra})
    assert response.status_code == 200, response.text
    return response.json()


def asset(pack, kind, key=None):
    return next(a['id'] for a in pack['assets'] if a['kind'] == kind and (key is None or a['key'] == key))


def create_deal(client, setup, pack, name='Real booking', **extra):
    h, executor = setup
    response = client.post('/api/v1/crm/deals', headers=h, json={
        'name': name, 'pipeline_id': asset(pack, 'pipeline'), 'stage_id': asset(pack, 'stage', '0'),
        'amount': 100, 'status': 'Open', 'owner_user_id': executor.id, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def process(db, loops=12):
    for _ in range(loops):
        runtime.process_batch(db, 100)


def test_install_is_atomic_repeatable_and_clean(client, db, setup):
    pack = install(client, setup)
    again = install(client, setup)
    assert again['assets'] == pack['assets']
    assert db.query(CRMDeal).count() == 0
    assert db.query(AutomationWorkflow).count() == 3
    assert db.query(WorkflowVersion).count() == 3
    assert db.query(AnalyticsReport).count() == 3
    fields = db.query(CRMCustomField).all()
    assert len({f.field_key for f in fields}) == len(fields)
    assert all(not f.is_required for f in fields)  # Never impose pack inputs on other pipelines.
    assert pack['version'] == 1 and pack['status'] == 'Enabled'


def test_installed_workflows_execute_native_tasks_and_stage_handoffs(client, db, setup):
    h, executor = setup
    pack = install(client, setup)
    deal = create_deal(client, setup, pack)
    process(db)
    tasks = db.query(CRMTask).filter_by(deal_id=deal['id']).all()
    jobs = db.query(AutomationScheduledJob).filter_by(job_type='shared_workflow').all()
    assert len(tasks) == 1, [(j.status, j.last_error) for j in jobs]
    assert tasks[0].owner_user_id == executor.id
    changed = client.patch(f'/api/v1/crm/deals/{deal["id"]}', headers=h, json={'stage_id': asset(pack, 'stage', '1')})
    assert changed.status_code == 200, changed.text
    process(db)
    assert db.query(CRMTask).filter_by(deal_id=deal['id']).count() == 2
    client.patch(f'/api/v1/crm/deals/{deal["id"]}', headers=h, json={'stage_id': asset(pack, 'stage', '1')})
    process(db)
    assert db.query(CRMTask).filter_by(deal_id=deal['id']).count() == 2


def test_reports_return_scoped_rows_custom_fields_and_real_totals(client, db, setup):
    h, _ = setup
    pack = install(client, setup)
    custom = next(a['key'] for a in pack['assets'] if a['kind'] == 'field')
    deal = create_deal(client, setup, pack, customFields={custom: 'Bridal'})
    create_deal(client, setup, pack, name='Second booking', amount=250)
    other = install(client, setup, 'automobile-service')
    create_deal(client, setup, other, name='Unrelated repair', amount=999)
    response = client.post(f'/api/v1/analytics/reports/{asset(pack,"report","0")}/run', headers=h, json={})
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 2
    assert next(row for row in response.json()['items'] if row['id'] == deal['id'])['custom:'+custom] == 'Bridal'
    totals = client.post(f'/api/v1/analytics/reports/{asset(pack,"report","1")}/run', headers=h, json={})
    assert totals.status_code == 200, totals.text
    assert totals.json()['items'][0]['record_count'] == 2
    assert totals.json()['items'][0]['total_value'] == 350
    forbidden = client.post(f'/api/v1/analytics/reports/{asset(pack,"report","0")}/run', headers=h, json={'filters_json': {'pipeline_id': asset(other,'pipeline')}})
    assert forbidden.status_code == 422


def test_reminder_executes_after_delay_and_ignores_closed_records(client, db, setup):
    pack = install(client, setup)
    deal = create_deal(client, setup, pack)
    process(db)
    waiting = db.query(AutomationScheduledJob).filter_by(job_type='shared_workflow', status='scheduled').all()
    assert len(waiting) == 1
    waiting[0].run_at = runtime.now()-timedelta(seconds=1)
    db.commit()
    process(db)
    assert db.query(Notification).filter_by(title='Salon & Spa: open record follow-up').count() == 1
    second = create_deal(client, setup, pack, name='Closed before reminder')
    process(db)
    closed = client.patch(f'/api/v1/crm/deals/{second["id"]}', headers=setup[0], json={'stage_id': asset(pack, 'stage', '4')})
    assert closed.status_code == 200, closed.text
    for job in db.query(AutomationScheduledJob).filter_by(status='scheduled').all():
        job.run_at = runtime.now()-timedelta(seconds=1)
    db.commit()
    process(db)
    assert db.query(Notification).filter_by(title='Salon & Spa: open record follow-up').count() == 1


def test_disable_cancels_jobs_preserves_records_and_can_reenable(client, db, setup):
    h, _ = setup
    pack = install(client, setup)
    deal = create_deal(client, setup, pack)
    process(db)
    result = client.post(f'{ROOT}/salon-spa/disable', headers=h)
    assert result.status_code == 200, result.text
    assert db.get(CRMDeal, deal['id']) is not None
    assert db.query(CRMTask).filter_by(deal_id=deal['id']).count() == 1
    remaining = db.query(AutomationScheduledJob).filter_by(status='scheduled', job_type='shared_workflow').all()
    assert not remaining, [(job.id, job.payload_json, job.last_error) for job in remaining]
    assert all(not w.is_active for w in db.query(AutomationWorkflow).all())
    assert client.post(f'/api/v1/analytics/reports/{asset(pack,"report","0")}/run', headers=h, json={}).status_code == 409
    again = install(client, setup, expected_version=1)
    assert asset(again, 'pipeline') == asset(pack, 'pipeline')
    assert db.query(AutomationWorkflow).count() == 3
    assert db.query(WorkflowVersion).count() == 6


def test_upgrade_preserves_assets_and_business_data(client, db, setup, monkeypatch):
    pack = install(client, setup)
    deal = create_deal(client, setup, pack)
    newer = copy.deepcopy(service.CATALOG['salon-spa'])
    newer['version'] = 2
    newer['fields'].append('Preferred language')
    monkeypatch.setitem(service.CATALOG, 'salon-spa', newer)
    stale = client.post(f'{ROOT}/salon-spa/install', headers=setup[0], json={'run_as_user_id': setup[1].id, 'expected_version': 2})
    assert stale.status_code == 409
    upgraded = install(client, setup, expected_version=1)
    assert upgraded['version'] == 2
    assert asset(upgraded, 'pipeline') == asset(pack, 'pipeline')
    assert db.query(CRMPipeline).count() == 1 and db.query(AnalyticsReport).count() == 3
    assert db.get(CRMDeal, deal['id']).name == 'Real booking'
    assert db.query(AccessTemplate).count() == 2
    assert db.query(WorkflowVersion).count() == 6
    install(client, setup, expected_version=2)
    assert db.query(WorkflowVersion).count() == 6


def test_customer_edits_are_not_overwritten_even_after_disable(client, db, setup):
    pack = install(client, setup)
    report = db.get(AnalyticsReport, asset(pack, 'report'))
    report.name = 'My custom report'
    db.commit()
    result = client.post(f'{ROOT}/salon-spa/install', headers=setup[0], json={'run_as_user_id': setup[1].id})
    assert result.status_code == 409
    assert report.name == 'My custom report'
    assert client.post(f'{ROOT}/salon-spa/disable', headers=setup[0]).status_code == 200
    assert client.post(f'{ROOT}/salon-spa/install', headers=setup[0], json={'run_as_user_id': setup[1].id}).status_code == 409


def test_failed_install_rolls_back_every_asset(client, db, setup, monkeypatch):
    original = service.publish_definition
    calls = []
    def fail_second(*args):
        calls.append(1)
        if len(calls) == 2:
            from fastapi import HTTPException
            raise HTTPException(422, 'Injected publication failure')
        return original(*args)
    monkeypatch.setattr(service, 'publish_definition', fail_second)
    result = client.post(f'{ROOT}/salon-spa/install', headers=setup[0], json={'run_as_user_id': setup[1].id})
    assert result.status_code == 422, result.text
    assert db.query(CRMPipeline).count() == 0
    assert db.query(AutomationWorkflow).count() == 0
    assert db.query(WorkflowVersion).count() == 0
    assert db.query(SuiteForm).count() == 0
    assert service.get_install(db, 1, 'salon-spa', required=False) is None


def test_sample_data_is_separate_idempotent_and_does_not_trigger_work(client, db, setup):
    pack = install(client, setup)
    before = db.query(ServiceEvent).count()
    first = client.post(f'{ROOT}/salon-spa/sample-data', headers=setup[0])
    assert first.status_code == 200, first.text
    second = client.post(f'{ROOT}/salon-spa/sample-data', headers=setup[0])
    assert second.status_code == 200 and not second.json()['created']
    assert second.json()['ids'] == first.json()['ids']
    assert all(db.get(CRMDeal, identifier).name.startswith('[Sample]') for identifier in first.json()['ids'])
    assert db.query(ServiceEvent).count() == before
    process(db)
    assert db.query(CRMTask).count() == 0


def test_install_requires_step_up_governance_and_managed_identity(client, db, setup):
    h, executor = setup
    no_step = {key: value for key, value in h.items() if key != 'X-Access-Step-Up'}
    assert client.post(f'{ROOT}/salon-spa/install', headers=no_step, json={'run_as_user_id': executor.id}).status_code == 403
    assert client.post(f'{ROOT}/salon-spa/install', headers=login(client), json={'run_as_user_id': executor.id}).status_code == 403
    admin = db.query(User).filter_by(is_superuser=True).first()
    assert client.post(f'{ROOT}/salon-spa/install', headers=h, json={'run_as_user_id': admin.id}).status_code == 422
    assert db.query(AutomationWorkflow).count() == 0
    candidates = client.get(ROOT+'/execution-identities', headers=h)
    assert candidates.status_code == 200, candidates.text
    assert executor.id in [person['id'] for person in candidates.json()['items']]


@pytest.mark.parametrize('key', ['bike-repair', 'bike-sales', 'ca-firm', 'accounting-firm', 'logistics', 'msme-trading', 'manufacturing'])
def test_target_industries_install_published_workflows_reports_and_private_forms(client, db, setup, key):
    pack = install(client, setup, key)
    assert len([a for a in pack['assets'] if a['kind'] == 'report']) == 3
    assert len([a for a in pack['assets'] if a['kind'] == 'workflow']) == 3
    assert all(row.is_active and row.published_version for row in db.query(AutomationWorkflow).all())
    form = db.get(SuiteForm, asset(pack, 'form'))
    assert form.open and form.version == 1 and not form.published['settings']['public']
    assert db.query(AccessTemplate).count() == 2


def test_company_isolation_and_foreign_execution_identity(client, db, setup):
    from tests.customization_test_utils import customization_headers
    pack = install(client, setup)
    beta = customization_headers(client, db, 'beta-pack@example.com', permissions=['crm_view', 'analytics_view'], company_id=2)
    result = client.get(ROOT+'/installed', headers=beta)
    assert result.status_code == 200, result.text
    assert result.json()['items'] == []
    # A report owner can legitimately administer more than one company. That
    # must not turn owner-based legacy ORM visibility into pack metadata access.
    from app.access.models import AccessMembership
    owner = db.get(AnalyticsReport, asset(pack, 'report', '0')).owner_id
    db.add(AccessMembership(user_id=owner, company_id=2, active=True, is_admin=True))
    db.commit()
    assert client.get(f'/api/v1/analytics/reports/{asset(pack,"report","0")}', headers=beta).status_code == 404
    listing = client.get('/api/v1/analytics/reports', headers=beta)
    assert listing.status_code == 200 and listing.json()['items'] == []
    report = client.post(f'/api/v1/analytics/reports/{asset(pack,"report","0")}/run', headers=beta, json={})
    assert report.status_code == 404, report.text
    beta_user = db.query(User).filter_by(email='beta-pack@example.com').one()
    denied = client.post(f'{ROOT}/bike-repair/install', headers=setup[0], json={'run_as_user_id': beta_user.id})
    assert denied.status_code in {403, 422}, denied.text


def test_pack_report_exports_use_native_export_engine(client, db, setup, tmp_path, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    pack = install(client, setup)
    create_deal(client, setup, pack, name='Export booking')
    response = client.post(f'/api/v1/analytics/reports/{asset(pack,"report","0")}/export', headers=setup[0], json={'export_type': 'csv'})
    assert response.status_code == 201, response.text
    assert response.json()['status'] == 'completed', response.text
    download = client.get(f'/api/v1/analytics/exports/{response.json()["id"]}/download', headers=setup[0])
    assert download.status_code == 200 and b'Export booking' in download.content


def test_legacy_domain_pack_endpoint_cannot_partially_disable_industry_pack(client, db, setup):
    pack = install(client, setup)
    response = client.put(f'/api/v1/enterprise/domain-packs/{pack["id"]}/disable', headers=setup[0])
    assert response.status_code == 409, response.text
    assert all(row.is_active for row in db.query(AutomationWorkflow).all())


def test_every_catalog_template_compiles_to_executable_graphs():
    for key, pack in service.CATALOG.items():
        assert key == pack['key'] and pack['version'] >= 1
        for operation in range(3):
            runtime.validate_graph(service.graph(1, 2, 3, pack['name'], operation))


def test_destructive_pack_changes_require_explicit_migration(client, db, setup, monkeypatch):
    pack = install(client, setup)
    newer = copy.deepcopy(service.CATALOG['salon-spa'])
    newer['version'] = 2
    newer['fields'] = []
    newer['customFields'] = []
    monkeypatch.setitem(service.CATALOG, 'salon-spa', newer)
    response = client.post(f'{ROOT}/salon-spa/install', headers=setup[0], json={'run_as_user_id': setup[1].id, 'expected_version': 1})
    assert response.status_code == 409, response.text
    assert service.get_install(db, 1, 'salon-spa').config_json['version'] == 1
    assert db.query(WorkflowVersion).count() == 3
    assert db.query(CRMCustomField).count() == len([a for a in pack['assets'] if a['kind'] == 'field'])


def test_revoked_identity_does_not_execute_installed_workflow(client, db, setup):
    pack = install(client, setup)
    deal = create_deal(client, setup, pack)
    policy = db.query(AccessPolicy).filter_by(user_id=setup[1].id, company_id=1).one()
    policy.status = 'suspended'
    db.commit()
    process(db)
    assert db.query(CRMTask).filter_by(deal_id=deal['id']).count() == 0
    assert db.query(AutomationScheduledJob).filter_by(status='dead_letter').count() >= 1


def test_native_field_adapter_rejects_cross_pack_writes(client, db, setup):
    salon = install(client, setup)
    repair = install(client, setup, 'bike-repair')
    field = next(a['key'] for a in salon['assets'] if a['kind'] == 'field')
    response = client.post('/api/v1/crm/deals', headers=setup[0], json={
        'name': 'Wrong industry fields', 'pipeline_id': asset(repair, 'pipeline'), 'stage_id': asset(repair, 'stage', '0'),
        'amount': 10, 'status': 'Open', 'owner_user_id': setup[1].id, 'customFields': {field: 'Bridal'}})
    assert response.status_code == 422, response.text
    assert db.query(CRMDeal).filter_by(name='Wrong industry fields').count() == 0


def test_catalog_changes_require_a_version_bump(client, db, setup, monkeypatch):
    install(client, setup)
    changed = copy.deepcopy(service.CATALOG['salon-spa'])
    changed['fields'].append('Unversioned field')
    monkeypatch.setitem(service.CATALOG, 'salon-spa', changed)
    response = client.post(f'{ROOT}/salon-spa/install', headers=setup[0], json={'run_as_user_id': setup[1].id})
    assert response.status_code == 409, response.text
