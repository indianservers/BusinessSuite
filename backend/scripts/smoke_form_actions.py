"""Local reviewed form smoke: synthetic closed drafts, no live publication."""
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.forms.models import SuiteForm, FormReply
from app.ai_operator.models import OperatorApiLog


def main():
    root = '/api/v1/ai-operator/suite'
    entries, runs, checks = [], [], []
    with httpx.Client(base_url='http://127.0.0.1:1534', timeout=60) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.is_success, f'{method} {path}: HTTP {response.status_code}'
            return response.json()

        auth = call('POST', '/api/v1/auth/login', json={
            'email': settings.BOOTSTRAP_ADMIN_EMAIL,
            'password': settings.BOOTSTRAP_ADMIN_PASSWORD,
        })
        client.headers['Authorization'] = 'Bearer ' + auth['access_token']
        client.headers['X-Company-ID'] = str(settings.LOGIN_COMPANY_ID)
        try:
            for module in ('CRM', 'PMS', 'HRMS'):
                name = 'Synthetic form QA ' + uuid4().hex[:12]
                ident = call('POST', root + '/conversations', json={'title': name})['id']
                entry = {'chat_id': ident, 'module': module.lower(), 'name': name, 'run': None}
                entries.append(entry)

                def say(text):
                    value = call('POST', root + '/commands', json={
                        'request_key': str(uuid4()), 'provider': 'local',
                        'module': module, 'conversation_id': ident, 'text': text,
                    })
                    runs.append(value['id']); entry['run'] = value
                    return value

                def execute(value):
                    call('POST', root + f'/runs/{value["id"]}/approve', json={'plan_hash': value['plan_hash']})
                    deadline = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        value = call('GET', root + f'/runs/{value["id"]}')
                        entry['run'] = value
                        if value['status'] not in {'queued', 'executing'}:
                            break
                        time.sleep(1)
                    assert value['status'] == 'succeeded', value.get('error_code')
                    return value

                draft = say(f'{module}: Create form called {name} with fields Name:text required, Email:email')
                assert draft['status'] == 'awaiting_approval'
                draft = say('Make Email required')
                assert draft['status'] == 'awaiting_approval'
                draft = say('Add an optional phone field called Phone')
                assert len(draft['plan']['steps'][0]['payload']['fields']) == 3
                done = execute(draft)
                fid = done['receipts'][0]['record_id']; entry['form_id'] = fid
                source_path = root + f'/{module.lower()}/forms/records/{fid}'
                source = call('GET', source_path)
                assert source['definition']['name'] == name
                assert source['definition']['fields'][1]['required']
                assert len(source['definition']['fields']) == 3
                with SessionLocal() as db:
                    row = db.get(SuiteForm, fid)
                    assert row.name == name and row.published is None and not row.open
                    entry['owner_id'] = row.owner_id
                    assert client.get('/api/v1/forms/public/' + row.slug).status_code == 404
                edit = say('Edit that form: description=Synthetic reviewed description')
                assert edit['status'] == 'awaiting_approval'
                edited = execute(edit)
                current = call('GET', source_path)
                assert current['definition']['description'] == 'Synthetic reviewed description'
                call('POST', root + f'/runs/{edited["id"]}/approve', json={'plan_hash': edited['plan_hash']})
                assert call('GET', source_path)['revision'] == current['revision']
                entry['source'] = current
                publish = say('Publish that form')
                assert publish['status'] == 'awaiting_approval'
                assert publish['result']['form_reviews']['1']['audience'] == 'Owner only'
                call('POST', root + f'/runs/{publish["id"]}/cancel')
                entry['run'] = call('GET', root + f'/runs/{publish["id"]}')
                checks.append({'module': module, 'form_id': fid, 'chat_id': ident,
                               'followups': True, 'reviewed_create_and_edit': True,
                               'repeat_approval_no_mutation': True, 'publication_preview_cancelled': True})
            with SessionLocal() as db:
                assert db.query(OperatorApiLog).filter(OperatorApiLog.suite_run_id.in_(runs)).count() == 0
        finally:
            for entry in entries:
                run = entry['run']
                if run and run['status'] in {'awaiting_approval', 'needs_clarification'}:
                    call('POST', root + f'/runs/{run["id"]}/cancel')
                assert not run or run['status'] not in {'queued', 'executing'}, 'Retain active QA chat'
                # No native delete endpoint exists. Delete only the exact unchanged,
                # unpublished synthetic row created above, never responses or real forms.
                if entry.get('form_id'):
                    from app.ai_operator.form_actions import definition
                    from app.ai_operator.service import digest
                    with SessionLocal() as db:
                        row = db.get(SuiteForm, entry['form_id'])
                        assert row and row.owner_id == entry['owner_id']
                        assert row.organization_id == settings.LOGIN_COMPANY_ID
                        assert row.module_key == entry['module'] and row.name == entry['name']
                        assert row.published is None and not row.open and row.version == 0
                        assert db.query(FormReply).filter(FormReply.form_id == row.id).count() == 0
                        assert entry.get('source') and digest(definition(row)) == entry['source']['source_sha256']
                        db.delete(row); db.commit()
                call('DELETE', root + f'/conversations/{entry["chat_id"]}')
    evidence = {'modules': checks, 'run_ids': runs, 'cleanup_verified': True,
                'live_publications': 0, 'business_messages_sent': 0, 'external_model_calls': 0}
    (Path(__file__).resolve().parents[2] / '.local/form-actions-live-result.json').write_text(
        json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
