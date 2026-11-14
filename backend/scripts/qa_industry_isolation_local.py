"""Verify local QA tenant tokens cannot cross company database boundaries."""
import json
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.qa_industry_companies_local import local_guard, ROOT, PRIVATE, OUTPUT, save


def run():
    local_guard()
    origin = json.loads((ROOT / '.local/industry-qa15/api.json').read_text())['origin']
    if not origin.startswith('http://127.0.0.1:'):
        raise RuntimeError('Owned loopback QA API required')
    companies = json.loads(OUTPUT.read_text())['companies']
    password = json.loads(PRIVATE.read_text())['password']
    report = {'checks': []}
    destination = ROOT / 'output/business-profile-15-companies/isolation.json'
    for index, company in enumerate(companies):
        other = companies[(index + 1) % len(companies)]
        headers = {'X-Suite-Tenant': company['workspace'], 'X-Suite-Organization': str(company['company_id']), 'X-Suite-Branch': str(company['branch_id'])}
        response = requests.post(origin + '/api/v1/auth/login', headers=headers, json={'email': company['email'], 'password': password}, timeout=90)
        response.raise_for_status()
        headers['Authorization'] = 'Bearer ' + response.json()['access_token']
        own = requests.get(origin + '/api/v1/access/settings/business-profile/effective', headers=headers, timeout=90)
        assert own.status_code == 200 and own.json()['business_type'] == company['industry']
        foreign = {**headers, 'X-Suite-Tenant': other['workspace'], 'X-Suite-Organization': str(other['company_id'])}
        response = requests.get(origin + '/api/v1/access/settings/business-profile/effective', headers=foreign, timeout=90)
        check = {'industry': company['industry'], 'target_industry': other['industry'], 'status': response.status_code, 'passed': response.status_code in (401, 403, 404)}
        report['checks'].append(check)
        save(destination, report)
        assert check['passed'], 'Foreign tenant request was not rejected'
        print(company['industry'] + ': own profile verified; foreign tenant rejected', flush=True)
    report['status'] = 'passed'
    save(destination, report)


if __name__ == '__main__':
    run()
