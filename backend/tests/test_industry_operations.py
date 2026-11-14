"""Real HTTP booking and measured-work billing, with native scope and ledger guards."""
from uuid import uuid4
import os
import pytest
from tests.test_contact_directory import directory_identity
from tests.test_connected_commercial import setup_business, link
from tests.srm_test_utils import auth_headers_for
from app.apps.srm.models import SRMProduct, SRMInvoice
from app.apps.srm.industry_models import IndustryRecord

ROOT = '/api/v1/srm/industry'


def payload(**kw):
    return {'request_id': str(uuid4()), 'title': 'Synthetic work', **kw}


def post(client, headers, path, data, status=201):
    r = client.post(ROOT + path, headers=headers, json=data)
    assert r.status_code == status, r.text
    return r.json()


@pytest.fixture
def business(client, db, superuser_headers, directory_identity):
    buyer, contact, project, team = setup_business(db)
    link(client, superuser_headers, buyer, contact, project, team)
    service = SRMProduct(organization_id=1, sku='SALON-TEST', item_name='Haircut', product_type='service', sales_rate=500, gst_rate=18, track_inventory=False)
    db.add(service)
    db.commit()
    return superuser_headers, buyer, project, service


def stylist(client, h):
    return post(client, h, '/resources', payload(title='Stylist A', resource_type='stylist', weekdays=list(range(7)), opens='09:00', closes='19:00'))


def booking(client, h, buyer, service, resource, **kw):
    return payload(customer_id=buyer.id, service_id=service.id, resource_ids=[resource['id']], starts_at='2026-11-16T10:00:00+05:30', duration_minutes=60, **kw)


def state(client, h, row, status, **kw):
    return post(client, h, f'/records/{row["id"]}/transition', {'expected_revision': row['revision'], 'status': status, **kw}, 200)


def collect(client, h, buyer, invoice):
    r = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=h)
    assert r.status_code == 200, r.text
    receipt = client.post('/api/v1/srm/receipts', headers=h, json={'customer_id': buyer.id, 'currency': 'INR', 'amount': invoice['total_amount']})
    assert receipt.status_code == 201, receipt.text
    applied = client.post(f'/api/v1/srm/receipts/{receipt.json()["id"]}/allocate', headers=h, json={'invoice_id': invoice['id'], 'amount': invoice['total_amount']})
    assert applied.status_code == 200, applied.text
    native = client.get(f'/api/v1/srm/invoices/{invoice["id"]}', headers=h).json()
    assert float(native['balance_amount']) == 0


def test_salon_booking_conflicts_reschedule_lifecycle_and_one_native_invoice(client, db, business):
    h, buyer, project, service = business
    resource = stylist(client, h)
    data = booking(client, h, buyer, service, resource, project_id=project.id, create_pms_task=True)
    booked = post(client, h, '/appointments', data)
    from app.apps.project_management.models import PMSTask
    linked_task = db.get(PMSTask, booked['data']['pms_task_id'])
    assert linked_task.project_id == project.id and linked_task.title == data['title']
    assert post(client, h, '/appointments', data)['id'] == booked['id']
    post(client, h, '/appointments', {**data, 'request_id': str(uuid4())}, 409)
    post(client, h, '/appointments', {**data, 'request_id': str(uuid4()), 'starts_at': '2026-11-16T08:00:00+05:30'}, 409)
    early = client.post(ROOT + f'/records/{booked["id"]}/invoice', headers=h, json={'expected_revision': 1})
    assert early.status_code == 409
    moved = client.put(ROOT + f'/appointments/{booked["id"]}/schedule', headers=h, json={'expected_revision': 1, 'starts_at': '2026-11-16T11:00:00+05:30', 'duration_minutes': 60, 'resource_ids': [resource['id']]})
    assert moved.status_code == 200, moved.text
    row = moved.json()
    stale = client.put(ROOT + f'/appointments/{row["id"]}/schedule', headers=h, json={'expected_revision': 1, 'starts_at': '2026-11-16T12:00:00+05:30', 'duration_minutes': 60, 'resource_ids': [resource['id']]})
    assert stale.status_code == 409
    for status in ['checked_in', 'in_service', 'completed']:
        row = state(client, h, row, status)
    inv = post(client, h, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']})
    again = post(client, h, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']})
    assert inv['id'] == again['id']
    native = db.get(SRMInvoice, inv['id'])
    assert float(native.total_amount) == 590 and native.customer_id == buyer.id
    read = client.get(f'/api/v1/srm/invoices/{native.id}', headers=h)
    assert read.status_code == 200 and float(read.json()['total_amount']) == 590
    collect(client, h, buyer, inv)


def test_cancellation_releases_slot_and_denies_naive_times(client, business):
    h, buyer, _, service = business
    resource = stylist(client, h)
    data = booking(client, h, buyer, service, resource)
    row = post(client, h, '/appointments', data)
    state(client, h, row, 'cancelled', reason='Customer requested')
    assert post(client, h, '/appointments', {**data, 'request_id': str(uuid4())})['status'] == 'booked'
    post(client, h, '/appointments', {**data, 'request_id': str(uuid4()), 'starts_at': '2026-11-16T10:00:00'}, 422)


@pytest.mark.parametrize('provider_type', ['provider', 'doctor', 'consultant', 'technician', 'employee'])
def test_common_appointments_support_non_salon_providers(client, db, business, provider_type):
    h, buyer, project, service = business
    resource = post(client, h, '/resources', payload(title=f'Test {provider_type}', resource_type=provider_type, weekdays=list(range(7)), opens='09:00', closes='19:00'))
    data = booking(client, h, buyer, service, resource, project_id=project.id, create_pms_task=True)
    booked = post(client, h, '/appointments', data)
    assert booked['status'] == 'booked'
    from app.apps.project_management.models import PMSTask
    task = db.get(PMSTask, booked['data']['pms_task_id'])
    assert task.task_key.startswith('APPT-')
    assert '/srm/appointments' in task.description and 'Salon appointment' not in task.description
    post(client, h, '/appointments', {**data, 'request_id': str(uuid4())}, 409)
    moved = client.put(ROOT + f'/appointments/{booked["id"]}/schedule', headers=h, json={'expected_revision': 1, 'starts_at': '2026-11-16T11:00:00+05:30', 'duration_minutes': 30, 'resource_ids': [resource['id']]})
    assert moved.status_code == 200, moved.text


def test_construction_certification_variation_and_shared_invoice(client, db, business):
    h, buyer, project, _ = business
    item = post(client, h, '/boq', payload(project_id=project.id, code='C-01', unit='m3', quantity='10', unit_rate='1000', tax_rate='18'))
    item = state(client, h, item, 'approved')
    duplicate_scope = client.post(f'/api/v1/project-management/projects/{project.id}/invoices', headers=h, json={'request_id': str(uuid4()), 'lines': [{'description': 'Same scope through generic billing', 'quantity': 1, 'unit_price': 1000}]})
    assert duplicate_scope.status_code == 409, duplicate_scope.text
    m = post(client, h, '/measurements', payload(boq_id=item['id'], quantity='6', measured_on='2026-11-16'))
    m = state(client, h, m, 'approved')
    too_much = post(client, h, '/measurements', payload(boq_id=item['id'], quantity='5', measured_on='2026-11-17'))
    post(client, h, f'/records/{too_much["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 409)
    variation = post(client, h, '/boq', payload(project_id=project.id, code='V-01', unit='m3', quantity='5', unit_rate='1200', variation_of=item['id']))
    assert variation['status'] == 'draft'
    post(client, h, '/measurements', payload(boq_id=variation['id'], quantity='1', measured_on='2026-11-17'), 422)
    state(client, h, variation, 'approved')
    inv = post(client, h, f'/records/{m["id"]}/invoice', {'expected_revision': m['revision'], 'retention_percent': '5'})
    assert float(inv['total_amount']) == 7080
    assert post(client, h, f'/records/{m["id"]}/invoice', {'expected_revision': m['revision']})['id'] == inv['id']
    report = client.get(ROOT + f'/projects/{project.id}/summary', headers=h)
    assert report.status_code == 200, report.text
    assert float(report.json()['approved_scope_value']) == 16000
    assert float(report.json()['certified_value']) == 6000
    assert float(report.json()['unbilled_certified_value']) == 0
    assert float(report.json()['retention_tracked']) == 300
    assert db.query(SRMInvoice).count() == 1
    collect(client, h, buyer, inv)


def test_diary_idempotency_record_scope_and_viewer_cannot_write(client, db, business):
    h, _, project, _ = business
    data = payload(project_id=project.id, entry_date='2026-11-16', work_done='Foundation excavation completed', workforce=5)
    row = post(client, h, '/site-diaries', data)
    assert post(client, h, '/site-diaries', data)['id'] == row['id']
    post(client, h, '/site-diaries', {**data, 'request_id': str(uuid4()), 'file_ids': [999999]}, 422)
    viewer = auth_headers_for(client, db, 'industry-viewer@example.com', 'srm_viewer', permissions=['srm_view'])
    post(client, viewer, '/resources', payload(resource_type='chair'), 403)
    caps = client.get(ROOT + '/capabilities', headers=viewer)
    assert caps.status_code == 200 and not caps.json()['manage'] and not caps.json()['invoice']
    from app.models.company import Branch
    branch = Branch(company_id=1, name='Other industry branch', code='OTHER-IND', is_active=True)
    db.add(branch); db.commit()
    other_headers = {**h, 'X-Suite-Branch': str(branch.id)}
    hidden = client.get(ROOT + f'/records?kind=site_diary&project_id={project.id}', headers=other_headers)
    assert hidden.status_code in (403, 404) or hidden.json()['items'] == []
    missing = client.get(ROOT + '/records?kind=boq', headers=h)
    assert missing.status_code == 422


def test_project_materials_reuse_stock_ledger_and_block_overdraw(client, db, business):
    from app.apps.srm.models import SRMWarehouse, SRMInventoryBalance, SRMInventoryMovement
    h, _, project, _ = business
    warehouse = SRMWarehouse(organization_id=1, warehouse_code='SITE', warehouse_name='Site warehouse')
    product = SRMProduct(organization_id=1, sku='CEMENT-TEST', item_name='Cement bags', product_type='stock', track_inventory=True)
    db.add_all([warehouse, product]); db.commit()
    opened = client.post('/api/v1/srm/inventory/opening-stock', headers=h, json={'product_id': product.id, 'warehouse_id': warehouse.id, 'quantity': '10', 'rate': '300'})
    assert opened.status_code == 201, opened.text
    data = payload(project_id=project.id, product_id=product.id, warehouse_id=warehouse.id, quantity='3', issue_date='2026-11-16')
    row = post(client, h, '/material-issues', data)
    assert row['status'] == 'issued' and row['stock_movement_id']
    assert post(client, h, '/material-issues', data)['id'] == row['id']
    db.expire_all()
    balance = db.query(SRMInventoryBalance).filter_by(product_id=product.id, warehouse_id=warehouse.id).one()
    assert float(balance.quantity) == 7
    post(client, h, '/material-issues', {**data, 'request_id': str(uuid4()), 'quantity': '8'}, 409)
    assert db.query(SRMInventoryMovement).filter_by(movement_type='project_consumption').count() == 1
    result = client.get(ROOT + f'/projects/{project.id}/summary', headers=h)
    assert result.status_code == 200, result.text
    assert float(result.json()['actual_material_cost']) == 900


def test_independent_construction_approval_and_finance_only_invoicing(client, db, business):
    h, buyer, project, service = business
    operator = auth_headers_for(client, db, 'industry-operator@example.com', 'srm_sales_manager', permissions=['srm_view', 'srm_manage', 'pms_manage_projects'])
    item = post(client, operator, '/boq', payload(project_id=project.id, code='REVIEW', unit='m2', quantity='5', unit_rate='200'))
    post(client, operator, f'/records/{item["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 403)
    assert state(client, h, item, 'approved')['approved_by']
    resource = stylist(client, h)
    row = post(client, h, '/appointments', booking(client, h, buyer, service, resource))
    for status in ['checked_in', 'in_service', 'completed']:
        row = state(client, h, row, status)
    post(client, operator, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']}, 403)
    finance = auth_headers_for(client, db, 'industry-finance@example.com', 'srm_finance_manager', permissions=['srm_view', 'srm_invoice_create'])
    inv = post(client, finance, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']})
    assert float(inv['total_amount']) == 590
    post(client, finance, '/resources', payload(resource_type='chair'), 403)


def test_both_migration_chains_replay_without_losing_operations(client, db, business):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    from sqlalchemy import inspect
    h, _, project, _ = business
    row = post(client, h, '/site-diaries', payload(project_id=project.id, entry_date='2026-11-16', work_done='Retained migration evidence'))
    root = Path(__file__).resolve().parents[1]
    for path in [root/'alembic_postgresql/versions/pg_20261114_100_industry_operations.py', root/'alembic/versions/20261114_082_industry_operations.py']:
        spec = importlib.util.spec_from_file_location('industry_migration_' + path.stem, path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.op = SimpleNamespace(get_bind=lambda: db.connection())
        module.upgrade(); module.upgrade(); module.downgrade()
        assert db.get(IndustryRecord, row['id']).data['work_done'] == 'Retained migration evidence'
    actual = {c['name'] for c in inspect(db.connection()).get_columns('srm_industry_records')}
    assert actual == set(IndustryRecord.__table__.columns.keys())


def test_native_billing_can_run_before_additive_industry_migration():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from types import SimpleNamespace
    from app.apps.srm.industry_api import guard_billing_mode
    engine = create_engine('sqlite://')
    with Session(engine) as session:
        guard_billing_mode(session, SimpleNamespace(), 'pms_project', project_id=1)
    engine.dispose()


@pytest.mark.skipif(os.environ.get('RUN_INDUSTRY_BROWSER') != '1', reason='Explicit isolated browser integration')
def test_industry_real_browser(client, db, business):
    if db.get_bind().dialect.name != 'sqlite':
        pytest.skip('Browser runs against a disposable copy of the SQLite fixture')
    from tests.workflow_browser_utils import run_browser
    from app.apps.project_management.models import PMSProject
    from test_identity_utils import own_workflow_records
    h, _, project, _ = business
    salon_project = PMSProject(organization_id=1, name='Salon delivery project', project_key='SALONDEL', manager_user_id=project.manager_user_id)
    db.add(salon_project); db.flush(); own_workflow_records(db, salon_project); db.commit()
    before = db.query(IndustryRecord).count()
    run_browser(client, db, 'test-industry-live-workflow.cjs', {
        'INDUSTRY_TOKEN': h['Authorization'].split(' ', 1)[1],
        'INDUSTRY_BRANCH': h['X-Suite-Branch'], 'INDUSTRY_PROJECT': str(project.id),
        'INDUSTRY_SALON_PROJECT': str(salon_project.id),
    }, timeout_seconds=300)
    db.expire_all()
    assert db.query(IndustryRecord).count() == before
