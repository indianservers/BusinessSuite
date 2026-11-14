"""Create/reuse 15 fictional local tenants through native platform APIs.

Credentials stay in ignored .local; public evidence never contains bearer tokens.
No global credentials, existing company records or delivery settings are changed.
"""
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient
from app.core.config import settings

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.local/industry-qa15/credentials.json'
OUTPUT = ROOT / 'output/business-profile-15-companies/companies.json'
MARK = 'INDUSTRY-QA15-20261114'
INDUSTRIES = [
    ('salon', 'Lotus Salon'), ('hospital', 'Carewell Hospital'),
    ('construction', 'Skyline Construction'), ('retail', 'Corner Retail'),
    ('pharma', 'Greenleaf Pharma'), ('education', 'Brightpath Academy'),
    ('consulting', 'Clearview Consulting'), ('repairs', 'Quickfix Services'),
    ('restaurant', 'Garden Cafe'), ('manufacturing', 'Precision Manufacturing'),
    ('logistics', 'Swift Logistics'), ('real_estate', 'Horizon Properties'),
    ('hospitality', 'Harbor Hotel'), ('fitness', 'Active Life Fitness'),
    ('legal', 'Justice Legal Services'),
]
MODULES = ['hrms', 'crm', 'project_management', 'srm', 'fam']


def local_guard():
    for value in [settings.SQLALCHEMY_DATABASE_URI, settings.PLATFORM_DATABASE_URL]:
        url = make_url(str(value))
        if url.get_backend_name() != 'postgresql' or url.host not in {'127.0.0.1', 'localhost', '::1'}:
            raise RuntimeError('Loopback PostgreSQL required; no remote database is allowed')
    if not settings.TENANT_DATABASES_ENABLED:
        raise RuntimeError('Native dedicated-company routing must be enabled')
    from app.platform_owner.session import platform_factory
    from app.platform_owner.models import PlatformDatabaseServer
    with platform_factory()() as db:
        if any(row.host not in {'127.0.0.1', 'localhost', '::1'} for row in db.query(PlatformDatabaseServer)):
            raise RuntimeError('All provisioning servers must be local for this runner')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def call(client, method, path, headers=None, data=None, status=200):
    response = client.request(method, '/api/v1' + path, headers=headers, json=data)
    if response.status_code != status:
        # Do not print request bodies, headers, response records or private URLs.
        raise RuntimeError(f'{method} {path.split("?")[0]} returned {response.status_code}, expected {status}')
    return response.json()


def run():
    local_guard()
    # The manual platform endpoint does not send application acknowledgements;
    # native approval invitations are retained as held_local by provisioning.
    from app.main import app
    from app.db.tenant import lookup_route, tenant_session
    from sqlalchemy import text
    private = json.loads(PRIVATE.read_text()) if PRIVATE.exists() else {'marker': MARK, 'password': 'LocalQa@' + secrets.token_hex(14), 'companies': {}}
    if private.get('marker') != MARK:
        raise RuntimeError('Unexpected local credential manifest')
    evidence = []
    with_private = lambda: save(PRIVATE, private)
    with_private()
    client = TestClient(app, raise_server_exceptions=False)
    try:
        auth = call(client, 'POST', '/auth/platform/login', data={'email': os.environ.get('INDUSTRY_QA_OWNER_EMAIL', 'owner@indianservers.com'), 'password': os.environ.get('INDUSTRY_QA_OWNER_PASSWORD', 'Admin@123456')})
        owner = {'Authorization': 'Bearer ' + auth['access_token']}
        for index, (industry, name) in enumerate(INDUSTRIES, 1):
            email = f'industryqa15.{industry}@example.com'
            found = call(client, 'GET', '/platform/signups?status=all&search=' + email, owner)['items']
            row = next((item for item in found if item['email'] == email), None)
            if row is None:
                row = call(client, 'POST', '/platform/signups', owner, {
                    'applicant_type': 'company', 'name': 'Local QA Administrator',
                    'company_name': '[Local QA] ' + name, 'email': email,
                    'phone': f'900001{index:04d}', 'requested_modules': MODULES,
                    'consent': True, 'consent_evidence': 'User-authorized fictional local industry flow testing',
                    'source': 'local-industry-qa15', 'campaign': MARK,
                }, 201)
            if row['status'] != 'approved':
                row = call(client, 'PATCH', f'/platform/signups/{row["id"]}', owner, {
                    'version': row['version'], 'reason': 'Local industry QA verification',
                    'checklist': {'identity': True, 'duplicates': True, 'modules': True}})
                result = call(client, 'POST', f'/platform/signups/{row["id"]}/review', owner, {
                    'version': row['version'], 'decision': 'approve', 'reason': 'Approve fictional local QA company',
                    'modules': MODULES, 'trial_days': 90, 'trial_start': 'first_login',
                    'activation_days': 30, 'seats': 20, 'storage_mib': 1024})
                private['companies'][industry] = {'pending_invitation': result.get('invitation_url')}
                with_private()
            databases = call(client, 'GET', '/platform/databases', owner)
            database = next(item for item in databases if item['signup_id'] == row['id'])
            workspace = database['workspace_code']
            pending = private['companies'].get(industry, {}).get('pending_invitation')
            if pending:
                parameters = parse_qs(urlparse(pending).query)
                call(client, 'POST', '/auth/reset-password', {'X-Suite-Tenant': workspace}, {
                    'token': parameters['token'][0], 'new_password': private['password']})
                private['companies'][industry].pop('pending_invitation', None)
                with_private()
            login = call(client, 'POST', '/auth/login', {'X-Suite-Tenant': workspace}, {'email': email, 'password': private['password']})
            headers = {'Authorization': 'Bearer ' + login['access_token'], 'X-Suite-Tenant': workspace}
            identity = call(client, 'GET', '/auth/me', headers)
            access = call(client, 'GET', '/access/me', headers)
            if identity['is_superuser'] or not access.get('isAccessAdmin') or access['companyId'] != database['company_id']:
                raise RuntimeError('Company administrator scope mismatch')
            with tenant_session(lookup_route(workspace)) as db:
                branch = db.execute(text('select id from branches where company_id=:company and is_active=true order by id limit 1'), {'company': database['company_id']}).scalar_one()
                company_count = db.execute(text('select count(*) from companies')).scalar_one()
            if company_count != 1:
                raise RuntimeError('A dedicated QA database must contain one company')
            headers.update({'X-Suite-Organization': str(database['company_id']), 'X-Suite-Branch': str(branch)})
            endpoint = '/access/settings/business-profile/configuration'
            profile = call(client, 'GET', endpoint, headers)
            if profile['overrides'].get('business_type') != industry:
                call(client, 'PUT', endpoint, headers, {'version': profile['version'], 'values': {'business_type': industry}})
            effective = call(client, 'GET', '/access/settings/business-profile/effective', headers)
            if effective['business_type'] != industry:
                raise RuntimeError('Business profile did not persist')
            item = {'industry': industry, 'name': '[Local QA] ' + name, 'email': email,
                    'workspace': workspace, 'company_id': database['company_id'], 'branch_id': branch,
                    'signup_id': row['id'], 'database_id': database['id'], 'database_name': database['database_name'],
                    'profile_verified': True, 'scoped_admin_verified': True}
            private['companies'][industry] = item
            with_private()
            evidence.append(item)
            save(OUTPUT, {'marker': MARK, 'companies': evidence})
            print(f'{index}/15 verified: {name} ({workspace})', flush=True)
    finally:
        client.close()
    print('Verified 15 native local company approvals, activations and business profiles.', flush=True)


if __name__ == '__main__':
    run()
