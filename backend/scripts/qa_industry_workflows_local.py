"""Run native HRMS/CRM/PMS/appointment/payment flows in the 15 local QA tenants."""
import json
from datetime import datetime, timedelta, time, timezone
from pathlib import Path
import sys
from uuid import uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.qa_industry_companies_local import local_guard, ROOT, PRIVATE, OUTPUT, save, MARK


def items(value):
    if isinstance(value, list): return value
    return value.get('items', value.get('employees', value.get('records', [])))


def run():
    local_guard()
    base = json.loads((ROOT/'.local/industry-qa15/api.json').read_text())['origin']
    if not base.startswith('http://127.0.0.1:'): raise RuntimeError('Owned local QA API required')
    base += '/api/v1'
    private = json.loads(PRIVATE.read_text())
    companies = json.loads(OUTPUT.read_text())['companies']
    result_path = ROOT/'output/business-profile-15-companies/workflows.json'
    state = json.loads(result_path.read_text()) if result_path.exists() else {'marker': MARK, 'companies': {}}
    for company in companies:
        industry = company['industry']
        record = state['companies'].setdefault(industry, {'industry': industry, 'records': {}, 'checks': []})
        record['checks'] = []
        session = requests.Session()
        session.headers.update({'X-Suite-Tenant': company['workspace'], 'X-Suite-Organization': str(company['company_id']), 'X-Suite-Branch': str(company['branch_id'])})
        def call(method, path, data=None, status=200):
            response = session.request(method, base+path, json=data, timeout=90)
            accepted = response.status_code == status or (status == 201 and response.status_code == 200 and path.startswith('/project-management/'))
            check = {'method': method, 'path': path.split('?')[0], 'status': response.status_code, 'passed': accepted}
            record['checks'].append(check)
            save(result_path, state)
            if not accepted:
                try: detail = str(response.json().get('detail', 'Request failed'))[:400]
                except ValueError: detail = 'Non-JSON response'
                raise RuntimeError(f'{method} {path.split("?")[0]}: {response.status_code}: {detail}')
            return response.json()
        def stored(key, operation):
            if key not in record['records']:
                value = operation()
                record['records'][key] = value
                save(result_path, state)
            return record['records'][key]
        def request_key(key): return str(uuid5(NAMESPACE_URL, MARK+industry+key))
        try:
            login = call('POST', '/auth/login', {'email': company['email'], 'password': private['password']})
            session.headers['Authorization'] = 'Bearer '+login['access_token']
            me = call('GET', '/auth/me')
            profile = call('GET', '/access/settings/business-profile/effective')
            if profile['business_type'] != industry: raise RuntimeError('Wrong business profile')
            sample = call('POST', '/imports/sample-data/import', {'confirmation': 'import'})
            record['sample_counts'] = sample.get('batch', {}).get('counts', {})
            staff = items(call('GET', '/employees/'))
            if not staff: raise RuntimeError('No sample HRMS employees returned')
            record['records']['employee_id'] = staff[0]['id']
            call('GET', f'/employees/{staff[0]["id"]}')
            lead = stored('lead_id', lambda: call('POST', '/crm/lead-management/leads', {'values': {'firstName': 'Industry QA', 'lastName': industry, 'fullName': 'Industry QA '+industry, 'email': f'workflow.{industry}@example.com', 'status': 'New'}}, 201)['id'])
            call('GET', f'/crm/leads/{lead}')
            workspaces = items(call('GET', '/project-management/workspaces'))
            if not workspaces: raise RuntimeError('No sample PMS workspace returned')
            record['records']['workspace_id'] = workspaces[0]['id']
            project_key = 'Q15'+industry.upper().replace('_','')[:8]
            def create_project():
                existing = next((row for row in items(call('GET', '/project-management/projects')) if row.get('project_key') == project_key), None)
                return existing['id'] if existing else call('POST', '/project-management/projects', {'name': 'Industry QA delivery - '+industry, 'project_key': project_key, 'workspace_id': workspaces[0]['id'], 'manager_user_id': me['id']}, 201)['id']
            project = stored('project_id', create_project)
            call('GET', f'/project-management/projects/{project}')
            task = stored('task_id', lambda: call('POST', f'/project-management/projects/{project}/tasks', {'task_key': project_key+'-1', 'title': 'Prepare industry QA visit', 'priority': 'Medium'}, 201)['id'])
            call('GET', f'/project-management/tasks/{task}')
            buyer = stored('customer_id', lambda: call('POST', '/master-data/companies?source=srm', {'name': 'Industry QA '+profile['terms']['customer'][0], 'entityKind': 'Individual', 'roles': ['Customer'], 'status': 'Active', 'email': f'customer.{industry}@example.com'}, 201)['id'])
            call('GET', f'/master-data/companies/{buyer}?source=srm')
            services = items(call('GET', '/catalog/items?source=srm&kind=service&status=Active&per_page=50'))
            if not services: raise RuntimeError('No sample catalog services returned')
            service = services[0]['id']
            provider = stored('provider_id', lambda: call('POST', '/srm/industry/resources', {'request_id': request_key('provider'), 'title': 'Industry QA '+profile['terms']['provider'][0], 'resource_type': 'provider', 'employee_id': staff[0]['id'], 'weekdays': list(range(7))}, 201)['id'])
            if 'starts_at' not in record:
                day = datetime.now(ZoneInfo('Asia/Kolkata')).date()+timedelta(days=1)
                record['starts_at'] = datetime.combine(day, time(10), ZoneInfo('Asia/Kolkata')).astimezone(timezone.utc).isoformat()
                save(result_path, state)
            appointment = stored('appointment_id', lambda: call('POST', '/srm/industry/appointments', {'request_id': request_key('appointment'), 'title': 'Industry QA '+profile['terms']['appointment'][0], 'customer_id': buyer, 'service_id': service, 'resource_ids': [provider], 'starts_at': record['starts_at'], 'duration_minutes': 30, 'project_id': project, 'create_pms_task': True}, 201)['id'])
            rows = items(call('GET', '/srm/industry/records?kind=appointment'))
            visit = next(row for row in rows if row['id'] == appointment)
            if not visit['data'].get('pms_task_id'): raise RuntimeError('Appointment did not link to native PMS delivery')
            billing = call('GET', f'/srm/industry/appointments/{appointment}/billing')
            if 'payment_verified' not in record:
                paid = call('POST', f'/srm/industry/appointments/{appointment}/payments', {'request_id': request_key('advance'), 'expected_revision': billing['revision'], 'amount': '100.00', 'payment_method': 'cash', 'reference_number': 'FICTIONAL-LOCAL-QA'}, 201)
                if float(paid['advance']) != 100: raise RuntimeError('Advance was not recorded as native receipt')
                record['payment_verified'] = True
            call('GET', f'/srm/industry/appointments/{appointment}/billing')
            record['status'] = 'passed'
            record.pop('error', None)
            print(industry+': native modules, linked appointment and advance passed', flush=True)
        except Exception as exc:
            record['status'] = 'failed';record['error'] = str(exc)[:500]
            print(industry+': '+str(exc)[:300], flush=True)
        finally:
            session.close();save(result_path, state)
    raise SystemExit(0 if all(x.get('status') == 'passed' for x in state['companies'].values()) else 1)


if __name__ == '__main__': run()
