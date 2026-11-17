"""Exercise the isolated action_agent_qa_server over real HTTP, without mocks.

Uses only its fixed synthetic login and refuses a different server identity.
No external message delivery or financial posting is attempted.
"""
import json
from datetime import date, timedelta
from pathlib import Path
import time
from uuid import uuid4
import httpx

ROOT = '/api/v1/ai-operator/suite'
evidence = {'checks': [], 'environment': 'disposable loopback QA', 'external_provider_calls': 0}
output = Path(__file__).resolve().parents[1] / 'outputs/action-agent-live.json'


def check(name, **details):
    evidence['checks'].append({'name': name, 'status': 'passed', **details})
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('PASS', name, flush=True)


def main():
    with httpx.Client(base_url='http://127.0.0.1:1558', timeout=120) as client:
        def call(method, path, body=None):
            response = client.request(method, path, json=body)
            assert response.is_success, f'{method} {path}: {response.status_code} {response.text[:300]}'
            return response.json()

        login = call('POST', '/api/v1/auth/login', {'email': 'admin@suiteqa.example.com', 'password': 'SuiteQA@12345'})
        client.headers['Authorization'] = 'Bearer ' + login['access_token']
        me = call('GET', '/api/v1/auth/me')
        assert me['email'] == 'admin@suiteqa.example.com'
        # Company-wide read must not need a transaction destination.
        tools = call('GET', ROOT + '/tools')['tools']
        assert {'crm.create_task', 'pms.create_project', 'srm.draft_invoice', 'fam.draft_voucher', 'hrms.request_leave'} <= {t['name'] for t in tools}
        check('Company-wide capability discovery', tools=len(tools))
        client.headers['X-Suite-Branch'] = '1'

        def prepare(steps, **extra):
            return call('POST', ROOT + '/commands', {'request_key': str(uuid4()), 'provider': 'local',
                'text': 'Synthetic live action verification', 'local_plan': {'summary': 'Review synthetic QA records', 'steps': steps}, **extra})

        def execute(run):
            assert run['status'] == 'awaiting_approval', (run['status'], run.get('error_code'), run.get('result', {}).get('planning_issue'))
            # An incorrect approval must not dispatch any action.
            bad = client.post(ROOT + f'/runs/{run["id"]}/approve', json={'plan_hash': '0' * 64})
            assert bad.status_code == 409
            call('POST', ROOT + f'/runs/{run["id"]}/approve', {'plan_hash': run['plan_hash']})
            for _ in range(120):
                final = call('GET', ROOT + f'/runs/{run["id"]}')
                if final['status'] == 'succeeded':
                    return final
                assert final['status'] not in {'failed', 'paused', 'needs_reconciliation', 'cancelled'}, (final['status'], final.get('error_code'))
                time.sleep(.5)
            raise AssertionError('Worker did not finish')

        stamp = uuid4().hex[:7].upper()
        run = prepare([
            {'tool': 'crm.create_task', 'payload': {'title': 'Action QA ' + stamp}},
            {'tool': 'crm.update_task', 'record_id': {'$step': 1, 'field': 'id'}, 'payload': {'priority': 'High'}},
            {'tool': 'pms.create_project', 'payload': {'name': 'Action QA ' + stamp, 'project_key': 'QA' + stamp}},
            {'tool': 'hrms.create_ticket', 'payload': {'subject': 'Action QA ' + stamp, 'description': 'Synthetic verification', 'priority': 'Medium'}},
            {'tool': 'srm.draft_invoice', 'payload': {'customer_id': 101, 'currency': 'INR', 'lines': [{'description': 'Synthetic QA', 'quantity': 1, 'unit_price': 1}]}},
            {'tool': 'fam.create_cost_center', 'payload': {'code': 'QA' + stamp, 'name': 'Action QA ' + stamp}},
        ])
        final = execute(run)
        assert len(final['receipts']) == 6
        task_id = final['receipts'][0]['record_id']
        task = call('GET', f'/api/v1/crm/tasks/{task_id}')
        assert task['priority'] == 'High'
        invoice_id = final['receipts'][4]['record_id']
        invoice = call('GET', f'/api/v1/srm/invoices/{invoice_id}')
        assert invoice['status'] == 'draft'
        check('Reviewed five-module actions and dependent record references', run_id=final['id'], receipts=len(final['receipts']))
        before = final['receipts']
        repeated = call('POST', ROOT + f'/runs/{final["id"]}/approve', {'plan_hash': final['plan_hash']})
        assert repeated['receipts'] == before
        check('Approval replay preserves completed receipts')

        natural = call('POST', ROOT + '/commands', {'request_key': str(uuid4()), 'provider': 'local', 'module': 'CRM',
            'text': 'CRM: Create task called Natural QA ' + stamp})
        natural = execute(natural)
        assert natural['receipts'][0]['tool'] == 'crm.create_task'
        check('Natural-language local planning through live execution', run_id=natural['id'])

        cancelled = prepare([{'tool': 'crm.create_task', 'payload': {'title': 'Must not execute ' + stamp}}], module='CRM')
        cancelled = call('POST', ROOT + f'/runs/{cancelled["id"]}/cancel')
        assert cancelled['status'] == 'cancelled' and not cancelled['receipts']
        check('Cancellation before execution')

        for module in ['CRM', 'HRMS', 'SRM', 'FAM']:
            memory = call('POST', ROOT + '/memories', {'module': module, 'text': 'Synthetic QA preference ' + stamp, 'category': 'preference'})
            rows = call('GET', ROOT + '/memories?module=' + module)['items']
            assert any(row['id'] == memory['id'] for row in rows)
            call('DELETE', ROOT + f'/memories/{memory["id"]}')
        check('Private module memory save, read and forget')

        form = call('POST', ROOT + '/commands', {'request_key': str(uuid4()), 'provider': 'local', 'module': 'CRM',
            'text': 'CRM: Create form called Synthetic live intake with fields Name:text required, Email:email'})
        form = execute(form)
        form_id = form['receipts'][0]['record_id']
        record = call('GET', ROOT + f'/crm/forms/records/{form_id}')
        assert 'responses' not in record and 'slug' not in record
        check('Natural-language form draft creation', form_id=form_id)

        definition = record['definition']
        definition['description'] = 'Reviewed synthetic change'
        edit = execute(prepare([{'tool': 'crm.edit_form', 'payload': {**definition, 'form_id': form_id,
            'expected_revision': record['revision'], 'source_sha256': record['source_sha256']}}], module='CRM'))
        for operation in ['publish', 'close']:
            record = call('GET', ROOT + f'/crm/forms/records/{form_id}')
            execute(prepare([{'tool': f'crm.{operation}_form', 'payload': {'form_id': form_id,
                'expected_revision': record['revision'], 'source_sha256': record['source_sha256']}}], module='CRM'))
        assert not call('GET', ROOT + f'/crm/forms/records/{form_id}')['open']
        check('Reviewed form editing, publication and closure')

        call('GET', '/api/v1/fam/dashboard')
        ledgers = call('GET', '/api/v1/fam/ledgers')['items']
        types = call('GET', '/api/v1/fam/voucher-types')['items']
        voucher = execute(prepare([{'tool': 'fam.draft_voucher', 'payload': {
            'voucher_type_id': types[0]['id'], 'voucher_date': date.today().isoformat(), 'narration': 'Synthetic draft ' + stamp,
            'lines': [{'ledger_id': ledgers[0]['id'], 'debit_amount': 1, 'credit_amount': 0},
                      {'ledger_id': ledgers[1]['id'], 'debit_amount': 0, 'credit_amount': 1}]}}]))
        saved = call('GET', '/api/v1/fam/vouchers/' + str(voucher['receipts'][0]['record_id']))
        assert saved['status'] == 'draft' and saved['total_debit'] == saved['total_credit']
        check('Balanced finance voucher remains an unposted draft')

        kind = call('POST', '/api/v1/leave/types', {'name': 'Synthetic leave ' + stamp, 'code': 'QA' + stamp, 'days_allowed': 30})
        call('POST', f'/api/v1/leave/balance/allocate?employee_id={login["employee_id"]}&leave_type_id={kind["id"]}&year={date.today().year}&days=30')
        day = (date.today() + timedelta(days=1)).isoformat()
        leave = execute(prepare([{'tool': 'hrms.request_leave', 'payload': {'leave_type_id': kind['id'],
            'from_date': day, 'to_date': day, 'is_half_day': False, 'reason': 'Synthetic QA'}}], module='HRMS'))
        requests = call('GET', '/api/v1/leave/my-requests')
        assert next(row for row in requests if row['id'] == leave['receipts'][0]['record_id'])['status'] == 'Pending'
        check('Leave submission through employee self-service', run_id=leave['id'])
        evidence['status'] = 'passed'


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        evidence['status'] = 'failed'
        evidence['error'] = str(exc)
        raise
    finally:
        output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
