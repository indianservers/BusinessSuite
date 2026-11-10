from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.ai_operator.reporting import ReportFilters, aggregate, csv_cell, validate_report
from app.ai_operator.suite_tools import InvoiceDraft, CRMTaskInput, minimize_source
from tests.test_ai_operator import isolate_generic_http_audit
from tests.test_suite_operator import setup_suite, prepare, approve, tick
from app.apps.crm.models import CRMTask

ROOT = '/api/v1/ai-operator/suite'


def test_financial_reports_separate_currencies_and_preserve_decimal_precision():
    filters = ReportFilters(entity='invoices', group_by=['currency'], measures=['count', 'amount'])
    result = aggregate([{'currency': 'INR', 'total_amount': '0.10'}, {'currency': 'INR', 'total_amount': '0.20'},
                        {'currency': 'USD', 'total_amount': '5.01'}, {'total_amount': '12'}], filters)
    assert result[0] == {'currency': 'INR', 'count': 2, 'amount': '0.30', 'missing_amounts': 0}
    assert result[1]['currency'] == 'USD' and result[1]['amount'] == '5.01'
    assert result[2]['missing_amounts'] == 1
    with pytest.raises(HTTPException):
        validate_report('SRM', ReportFilters(entity='invoices', measures=['amount']))
    assert csv_cell(' =HYPERLINK("https://example.com")').startswith("'")


@pytest.mark.parametrize('changes', [
    {'lines': []}, {'lines': [{'description': 'Bad', 'quantity': -1, 'unit_price': 1}]},
    {'lines': [{'description': 'Bad', 'quantity': 1, 'unit_price': 1, 'line_total': 999}]},
    {'lines': [{'description': 'Bad', 'quantity': 1, 'unit_price': 1, 'discount_amount': 2}]},
    {'status': 'Issued'}, {'issue_date': '2030-01-10', 'due_date': '2030-01-01'},
])
def test_invoice_draft_contract_rejects_unsafe_or_inconsistent_payloads(changes):
    with pytest.raises(ValueError):
        InvoiceDraft.model_validate({'customer_id': 1, 'lines': [{'description': 'Good', 'quantity': 1, 'unit_price': 10}], **changes})


def test_reminder_timezone_and_published_policy_minimization():
    with pytest.raises(ValueError):
        CRMTaskInput(title='Check', reminder_at='2030-01-01T10:00:00')
    with pytest.raises(ValueError):
        CRMTaskInput(title='Check', due_date='2030-01-01T10:00:00Z', reminder_at='2030-01-02T10:00:00Z')
    rows = minimize_source('hrms.policies', [{'id': 1, 'title': 'Published', 'is_published': True, 'content': 'Policy text'},
                                           {'id': 2, 'title': 'Private', 'is_published': False, 'content': 'Do not disclose'}])
    assert len(rows) == 1 and rows[0]['content'] == 'Policy text'


def test_report_scans_pages_and_computes_exact_filtered_totals(client, db):
    headers, user, _, _ = setup_suite(client, db)
    seeded = client.post('/api/v1/crm/tasks', headers=headers, json={'title': 'Seed', 'status': 'To Do'}).json()
    for index in range(60):
        created = client.post('/api/v1/crm/tasks', headers=headers, json={'title': f'Report {index}',
            'status': 'To Do' if index < 30 else 'Done', 'due_date': '2030-01-10T12:00:00Z'})
        assert created.status_code in (200, 201), created.text
    response = client.get(ROOT + '/reports/CRM', headers=headers, params={'entity': 'tasks', 'max_records': 100})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report['complete'] is True and report['scanned_records'] == 61 and report['pages'] == 2, report
    assert sum(group['count'] for group in report['groups']) == 61
    filtered = client.get(ROOT + '/reports/CRM', headers=headers, params={'entity': 'tasks', 'status': 'Done', 'date_from': '2030-01-01', 'date_to': '2030-01-31'})
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()['matched_records'] == 30 and filtered.json()['complete'] is True
    limited = client.get(ROOT + '/reports/CRM', headers=headers, params={'entity': 'tasks', 'max_records': 10})
    assert limited.json()['complete'] is False and limited.json()['scanned_records'] == 10
    boundary = client.get(ROOT + '/reports/CRM', headers=headers, params={'entity': 'tasks', 'max_records': 60})
    assert boundary.json()['complete'] is False and boundary.json()['scanned_records'] == 60
    csv = client.get(ROOT + '/reports/CRM', headers=headers, params={'entity': 'tasks', 'format': 'csv'})
    assert csv.status_code == 200 and csv.headers['content-type'].startswith('text/csv'), csv.text
    assert 'coverage,retrieved_at,filters' in csv.text and 'complete' in csv.text


def test_report_invalid_filters_and_unprivileged_export_are_rejected(client, db):
    from ai_test_utils import auth_headers
    headers, _, _, _ = setup_suite(client, db)
    for params in ({'entity': 'invoices'}, {'entity': 'tasks', 'unexpected': 'field'}, {'date_from': '2030-02-01', 'date_to': '2030-01-01'}, {'group_by': 'salary'}):
        assert client.get(ROOT + '/reports/CRM', headers=headers, params=params).status_code == 422
    assert client.get(ROOT + '/reports/PMS', headers=headers).status_code == 422
    restricted, _ = auth_headers(client, db, email=f'{uuid4()}@example.com', permissions=['ai_assistant', 'crm_view'])
    assert client.get(ROOT + '/reports/CRM', headers=restricted, params={'format': 'csv'}).status_code == 403


def test_cloud_context_can_use_filtered_native_report_without_writes(client, db):
    headers, _, _, _ = setup_suite(client, db)
    client.post('/api/v1/crm/tasks', headers=headers, json={'title': 'High task', 'priority': 'High'})
    response = client.post(ROOT + '/commands', headers=headers, json={'request_key': str(uuid4()), 'provider': 'local',
        'text': 'Summarize the report', 'context': [{'tool': 'crm.report', 'payload': {'entity': 'tasks', 'priority': 'High', 'group_by': ['status']}}]})
    assert response.status_code == 200 and response.json()['status'] == 'answered', response.text
    assert response.json()['result']['evidence_count'] == 1


def test_reviewed_crm_task_stores_owner_and_reminder(client, db):
    headers, user, _, _ = setup_suite(client, db)
    run = prepare(client, headers, [{'tool': 'crm.create_task', 'payload': {'title': 'Call customer', 'owner_user_id': user.id,
        'due_date': '2030-01-10T12:00:00Z', 'reminder_at': '2030-01-10T10:00:00Z'}}])
    assert run['status'] == 'awaiting_approval', run
    assert db.query(CRMTask).count() == 0
    approve(client, headers, run); tick(client, db)
    task = db.query(CRMTask).one()
    assert task.owner_user_id == user.id and task.reminder_at.hour == 10


def test_pms_milestone_and_assigned_task_use_canonical_reviewed_execution(client, db):
    from app.apps.project_management.models import PMSMilestone, PMSTask
    headers, user, project, _ = setup_suite(client, db)
    run = prepare(client, headers, [
        {'tool': 'pms.create_milestone', 'record_id': project, 'payload': {'name': 'Reviewed launch', 'due_date': '2030-01-10'}},
        {'tool': 'pms.create_task', 'record_id': project, 'payload': {'title': 'Launch QA', 'task_key': 'LAUNCH-QA',
            'assignee_user_ids': [user.id], 'milestone_id': {'$step': 1, 'field': 'id'}, 'due_date': '2030-01-10'}},
    ])
    assert run['status'] == 'awaiting_approval', run
    assert db.query(PMSMilestone).count() == 0
    approve(client, headers, run); tick(client, db)
    final = client.get(ROOT + f'/runs/{run["id"]}', headers=headers).json()
    assert final['status'] == 'succeeded', final
    task = db.query(PMSTask).filter_by(task_key='LAUNCH-QA').one()
    assert task.milestone_id == db.query(PMSMilestone).one().id and user.id in task.assignee_user_ids


def test_invoice_plan_creates_only_a_canonical_draft_after_approval(client, db):
    from app.apps.srm.models import SRMInvoice
    from app.apps.fam.models import FAMVoucher
    headers, _, _, _ = setup_suite(client, db)
    customer = client.post('/api/v1/crm/companies', headers=headers, json={'name': 'Reviewed customer'}).json()['id']
    run = prepare(client, headers, [{'tool': 'srm.draft_invoice', 'payload': {'customer_id': customer, 'currency': 'INR',
        'lines': [{'description': 'Reviewed service', 'quantity': 2, 'unit_price': '12.50', 'discount_amount': '5', 'tax_amount': '4'}]}}])
    assert run['status'] == 'awaiting_approval', run
    assert db.query(SRMInvoice).count() == 0
    approve(client, headers, run); tick(client, db)
    final = client.get(ROOT + f'/runs/{run["id"]}', headers=headers).json()
    assert final['status'] == 'succeeded', final
    invoice = db.query(SRMInvoice).one()
    assert invoice.status.lower() == 'draft' and str(invoice.total_amount) == '24.00'
    assert db.query(FAMVoucher).count() == 0


def test_policy_answer_never_sends_unpublished_policy_to_provider(client, db, monkeypatch):
    from tests.test_ai_operator import mock_provider
    headers, _, _, _ = setup_suite(client, db)
    for title, published in [('Public policy', True), ('UNPUBLISHED POLICY', False)]:
        response = client.post('/api/v1/documents/policies', headers=headers, json={'title': title, 'content': title, 'is_published': published})
        assert response.status_code in (200, 201), response.text
    calls = mock_provider(monkeypatch, {'summary': 'Policy summary', 'steps': []})
    result = client.post(ROOT + '/commands', headers=headers, json={'request_key': str(uuid4()), 'provider': 'gemini',
        'text': 'Summarize policies', 'context': [{'tool': 'hrms.policies'}]})
    assert result.status_code == 200 and result.json()['status'] == 'answered', result.text
    assert b'Public policy' in calls[0].content and b'UNPUBLISHED POLICY' not in calls[0].content
