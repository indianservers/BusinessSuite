"""Distinct delivery documents use certified native sources and independent signoff."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.apps.project_management.models import PMSTask
from app.apps.srm.commercial_models import ProjectCommercial
from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMInvoice, SRMReceipt, SRMReceiptAllocation
from app.branches.models import BranchOwnership
from app.business_packs.models import PackMasterAvailability, PackRecordOwnership
from tests.test_business_pack_construction import construction, construction_approver, scenario, catalog, directory_identity
from tests.test_construction_documents import documents, upload

ROOT = '/api/v1/srm/industry'


def post(client, headers, path, body, status=201):
    response = client.post(ROOT + path, headers=headers, json=body)
    assert response.status_code == status, response.text
    return response.json()


def review(client, headers, ident, revision=1, status='approved', expected=200, reason=''):
    return post(client, headers, f'/delivery/{ident}/review',
        {'expected_revision': revision, 'status': status, 'reason': reason}, expected)


@pytest.fixture
def delivery(client, db, construction, construction_approver, catalog):
    actor, branch, context, project = construction
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context)}
    db.add(ProjectCommercial(project_id=project, customer_id=101, seller_id=1, currency='INR', updated_by=actor.id))
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context,
        resource_table='crm_companies', resource_key='101', active=True))
    db.commit()
    boq = post(client, headers, '/boq', {'request_id': str(uuid4()), 'title': 'Certified delivery scope',
        'project_id': project, 'code': 'DELIVERY', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1000', 'tax_rate': '18'})
    post(client, construction_approver[0], f'/records/{boq["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    measurement = post(client, headers, '/measurements', {'request_id': str(uuid4()), 'title': 'Actual certified delivery',
        'boq_id': boq['id'], 'quantity': '6', 'measured_on': '2026-11-16'})
    measurement = post(client, construction_approver[0], f'/records/{measurement["id"]}/transition',
        {'expected_revision': 1, 'status': 'approved'}, 200)
    invoice = post(client, headers, f'/records/{measurement["id"]}/invoice',
        {'expected_revision': measurement['revision'], 'retention_percent': '5'})
    return {'actor': actor, 'branch': branch, 'context': context, 'project': project,
        'headers': headers, 'reviewer': construction_approver[0], 'measurement': measurement['id'], 'invoice': invoice['id']}


def test_distinct_payment_certificate_requires_issued_source_and_independent_approval(client, db, delivery):
    case = delivery
    payload = {'request_id': str(uuid4()), 'title': 'Interim payment certificate', 'measurement_id': case['measurement']}
    post(client, case['headers'], '/payment-certificates', payload, 409)
    issued = client.post(f'/api/v1/srm/invoices/{case["invoice"]}/approve', headers=case['headers'])
    assert issued.status_code == 200, issued.text
    from app.apps.fam.models import FAMLedgerEntry
    before = (db.query(SRMInvoice).count(), db.query(SRMReceipt).count(), db.query(SRMReceiptAllocation).count(), db.query(FAMLedgerEntry).count())
    row = post(client, case['headers'], '/payment-certificates', payload)
    assert row['kind'] == 'payment_certificate' and row['invoice_id'] == case['invoice']
    assert row['data']['document_type'] == 'Construction payment certificate'
    source = row['data']['source_snapshot']
    assert Decimal(source['invoice_total']) == 7080 and Decimal(source['retention_amount']) == 300
    assert Decimal(source['certified_net_payable']) == 6780 and source['currency'] == 'INR'
    assert post(client, case['headers'], '/payment-certificates', payload)['id'] == row['id']
    post(client, case['headers'], '/payment-certificates', {**payload, 'title': 'Changed retry'}, 409)
    post(client, case['headers'], '/payment-certificates', {**payload, 'request_id': str(uuid4())}, 409)
    review(client, case['headers'], row['id'], expected=403)
    draft = client.get(ROOT + f'/delivery/{row["id"]}/export', headers=case['headers'])
    assert draft.status_code == 409, draft.text
    approved = review(client, case['reviewer'], row['id'])
    assert approved['approved_by'] != approved['created_by'] and approved['revision'] == 2
    review(client, case['reviewer'], row['id'], expected=409)
    final = client.get(ROOT + f'/delivery/{row["id"]}/export', headers=case['headers'])
    assert final.status_code == 200 and final.json()['kind'] == 'payment_certificate', final.text
    csv = client.get(ROOT + f'/delivery/{row["id"]}/export', headers=case['headers'], params={'format': 'csv'})
    assert csv.status_code == 200 and 'certified_net_payable' in csv.text
    assert (db.query(SRMInvoice).count(), db.query(SRMReceipt).count(), db.query(SRMReceiptAllocation).count(), db.query(FAMLedgerEntry).count()) == before


def test_native_member_certificate_retry_and_approved_snapshot_cannot_be_rewritten(client, db, delivery):
    from fastapi import HTTPException
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.construction import project_for_action
    from tests.test_srm_native_transaction_operations import native_writer
    from tests.test_construction_site_workflows import native_member
    case = delivery
    issued = client.post(f'/api/v1/srm/invoices/{case["invoice"]}/approve', headers=case['headers'])
    assert issued.status_code == 200, issued.text
    headers, actor = native_member(db, case['branch'], case['context'], case['project'], 'Manager')
    assert not actor.is_superuser
    payload = {'request_id': str(uuid4()), 'title': 'Native member certificate', 'measurement_id': case['measurement']}
    row = post(client, headers, '/payment-certificates', payload)
    assert post(client, headers, '/payment-certificates', payload)['id'] == row['id']
    approved = review(client, case['reviewer'], row['id'])
    assert approved['approved_by'] != actor.id
    with native_writer(db, actor, case['branch']):
        scope = resolve_context(db, actor, db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            project_for_action(db, actor, case['project'])
            with pytest.raises(HTTPException) as denied:
                with db.begin_nested():
                    record = db.get(IndustryRecord, row['id'])
                    snapshot = {**record.data['source_snapshot'], 'currency': 'USD'}
                    record.data = {**record.data, 'source_snapshot': snapshot}
                    db.flush()
            assert denied.value.status_code == 403
        finally:
            cleanup()


def test_native_certificate_authority_revoked_after_writer_wait_rolls_back_and_retries(client, db, delivery, monkeypatch):
    from sqlalchemy import update
    from app.access.models import AccessPolicy
    from app.apps.srm import industry_api
    from tests.test_construction_site_workflows import native_member
    case = delivery
    issued = client.post(f'/api/v1/srm/invoices/{case["invoice"]}/approve', headers=case['headers'])
    assert issued.status_code == 200, issued.text
    headers, actor = native_member(db, case['branch'], case['context'], case['project'], 'Manager')
    original = industry_api.context
    def revoke_after_wait(session, principal, *args, **kwargs):
        result = original(session, principal, *args, **kwargs)
        if principal.id == actor.id:
            table = AccessPolicy.__table__
            session.connection().execute(update(table).where(table.c.company_id == 1, table.c.user_id == actor.id)
                .values(status='suspended', version=table.c.version + 1))
        return result
    payload = {'request_id': str(uuid4()), 'title': 'Retry after native authority failure', 'measurement_id': case['measurement']}
    with monkeypatch.context() as fault:
        fault.setattr(industry_api, 'context', revoke_after_wait)
        post(client, headers, '/payment-certificates', payload, 403)
    assert db.query(IndustryRecord).filter_by(kind='payment_certificate').count() == 0
    # The failed request's synthetic revocation was part of its rolled-back
    # transaction. The identical request key can now complete exactly once.
    row = post(client, headers, '/payment-certificates', payload)
    assert post(client, headers, '/payment-certificates', payload)['id'] == row['id']


def test_certificates_do_not_collect_money_and_client_report_tracks_native_partial_payment(client, db, delivery):
    from app.access.models import AccessPolicy
    from app.apps.project_management.models import PMSProjectMember
    from app.business_packs.models import PackContext
    from tests.test_business_pack_http_integration import native_actor, grant
    from tests.test_srm_native_transaction_operations import native_writer
    from app.business_packs.access import resolve_context
    from app.business_packs.boundary import install
    from app.business_packs.native_policy import native_srm_policy
    from app.business_packs.construction_delivery import client_report
    case = delivery
    issued = client.post(f'/api/v1/srm/invoices/{case["invoice"]}/approve', headers=case['headers'])
    assert issued.status_code == 200, issued.text
    row = post(client, case['headers'], '/payment-certificates', {'request_id': str(uuid4()),
        'title': 'Collection-independent certificate', 'measurement_id': case['measurement']})
    review(client, case['reviewer'], row['id'])
    headers, collector = native_actor(db, case['branch'])
    grant(db, collector, case['branch'], 'construction', 'billing_officer', db.get(PackContext, case['context']))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=collector.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True,
        'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'organization'}}
    db.add(PMSProjectMember(project_id=case['project'], user_id=collector.id, role='Viewer'))
    db.commit()
    payment = post(client, {**headers, 'X-Suite-Pack-Context': str(case['context'])},
        f'/records/{case["measurement"]}/payments', {'request_id': str(uuid4()), 'amount': '2000',
            'payment_method': 'bank_transfer', 'reference': 'Actual collection after certificate'})
    assert Decimal(str(payment['invoice']['balance_amount'])) == 5080
    final = client.get(ROOT + f'/delivery/{row["id"]}/export', headers=case['headers'])
    assert final.status_code == 200 and Decimal(final.json()['data']['source_snapshot']['certified_net_payable']) == 6780
    with native_writer(db, case['actor'], case['branch']):
        scope = resolve_context(db, case['actor'], db.info['branch_context'], case['context'])
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            report = client_report(db, case['actor'], case['project'])
        finally:
            cleanup()
    assert report['document_type'] == 'Construction client progress report'
    assert Decimal(report['native_invoices'][0]['collected']) == 2000
    assert Decimal(report['native_invoices'][0]['outstanding']) == 5080
    assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 1


def task(db, case, *, complete):
    row = PMSTask(project_id=case['project'], task_key=uuid4().hex[:20], title='Canonical handover task',
        status='Done' if complete else 'In Progress', completed_at=datetime.now(timezone.utc) if complete else None)
    db.add(row); db.flush()
    db.add(PackRecordOwnership(company_id=1, branch_id=case['branch'], context_id=case['context'],
        resource_table='pms_tasks', resource_key=str(row.id), source='explicit-test-enrollment'))
    if db.get(BranchOwnership, ('pms_tasks', str(row.id))) is None:
        db.add(BranchOwnership(company_id=1, branch_id=case['branch'], resource_table='pms_tasks',
            resource_key=str(row.id), source='explicit-test-enrollment'))
    db.commit()
    return row


def test_handover_requires_complete_checklist_actual_all_tasks_and_canonical_documents(client, db, documents, construction_approver):
    case = documents
    document = upload(client, case, b'Actual handover evidence').json()
    completed = task(db, case, complete=True)
    open_task = task(db, case, complete=False)
    payload = {'request_id': str(uuid4()), 'title': 'Project handover', 'project_id': case['project'],
        'file_ids': [document['id']], 'task_ids': [completed.id], 'checklist': [{'label': 'Safety inspection', 'complete': False}],
        'blockers': 'Final inspection outstanding'}
    row = post(client, case['headers'], '/handovers', payload)
    assert post(client, case['headers'], '/handovers', payload)['id'] == row['id']
    review(client, case['headers'], row['id'], expected=403)
    review(client, construction_approver[0], row['id'], expected=409)
    revised = client.put(ROOT + f'/handovers/{row["id"]}', headers=case['headers'], json={
        'expected_revision': 1, 'file_ids': [document['id']], 'task_ids': [completed.id],
        'checklist': [{'label': 'Safety inspection', 'complete': True}], 'blockers': ''})
    assert revised.status_code == 200 and revised.json()['revision'] == 2, revised.text
    # The omitted open task still blocks approval; caller task_ids is no loophole.
    review(client, construction_approver[0], row['id'], revision=2, expected=409)
    open_task.status = 'Done'; open_task.completed_at = datetime.now(timezone.utc); db.commit()
    approved = review(client, construction_approver[0], row['id'], revision=2)
    assert {item['id'] for item in approved['data']['approved_sources']['tasks']} == {completed.id, open_task.id}
    exported = client.get(ROOT + f'/delivery/{row["id"]}/export', headers=case['headers'])
    assert exported.status_code == 200 and exported.json()['kind'] == 'handover'
    assert exported.json()['data']['approved_sources']['files'][0]['id'] == document['id']
    changed = client.put(ROOT + f'/handovers/{row["id"]}', headers=case['headers'], json={
        'expected_revision': 3, 'file_ids': [document['id']], 'task_ids': [],
        'checklist': [{'label': 'Changed after signature', 'complete': True}], 'blockers': ''})
    assert changed.status_code == 409, changed.text


def test_handover_rejects_foreign_document_and_required_rejection_reason(client, db, documents, construction_approver):
    case = documents
    document = upload(client, case).json()
    payload = {'request_id': str(uuid4()), 'title': 'Reviewable handover', 'project_id': case['project'],
        'file_ids': [999999], 'checklist': [{'label': 'Checked', 'complete': True}]}
    post(client, case['headers'], '/handovers', payload, 404)
    row = post(client, case['headers'], '/handovers', {**payload, 'file_ids': [document['id']]})
    review(client, construction_approver[0], row['id'], status='rejected', expected=422)
    rejected = review(client, construction_approver[0], row['id'], status='rejected', reason='Client checklist requires correction')
    assert rejected['status'] == 'rejected'
    exported = client.get(ROOT + f'/delivery/{row["id"]}/export', headers=case['headers'])
    assert exported.status_code == 409


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_specialists_cannot_prepare_delivery_records(client, db, construction, catalog, pack, role):
    from tests.test_business_pack_http_integration import grant
    actor, branch, _, project = construction
    context, _ = grant(db, actor, branch, pack, role)
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context.id)}
    post(client, headers, '/payment-certificates', {'request_id': str(uuid4()), 'title': 'Forbidden', 'measurement_id': 1}, 403)
    post(client, headers, '/handovers', {'request_id': str(uuid4()), 'title': 'Forbidden', 'project_id': project,
        'file_ids': [1], 'checklist': [{'label': 'Forbidden', 'complete': True}]}, 403)


def test_delivery_csv_prevents_spreadsheet_formula_execution():
    from app.business_packs.construction_delivery import export_data
    content, mime, name = export_data({'title': '=HYPERLINK("bad")', 'number': 12}, 'certificate', 'csv')
    assert mime.startswith('text/csv') and name == 'certificate.csv'
    assert "'=HYPERLINK" in content.decode('utf-8-sig')
