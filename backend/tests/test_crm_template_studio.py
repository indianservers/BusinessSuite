"""Persistence, safe rendering, tenant boundaries and real mail merge."""
import copy
import pytest
from tests.test_crm_associations_merge import superuser_headers, contact
from app.apps.crm.template_models import CRMVisualTemplate
from app.apps.communication.models import CommunicationEmailTemplate
from app.apps.crm.template_studio import RenderInput, render

ROOT = '/api/v1/crm/template-studio'


def test_migration_creates_and_removes_visual_template_schema():
    from sqlalchemy import create_engine, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.apps.crm.template_schema import upgrade, downgrade
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        upgrade(operations)
        assert {'design', 'organization_id', 'version', 'email_template_id'} <= {c['name'] for c in inspect(connection).get_columns('crm_visual_templates')}
        assert inspect(connection).get_indexes('crm_visual_templates')[0]['column_names'] == ['organization_id']
        downgrade(operations)
        assert 'crm_visual_templates' not in inspect(connection).get_table_names()
    engine.dispose()


def template(category='email', document_type='email'):
    return {'name': 'Welcome design', 'category': category, 'document_type': document_type,
            'module': 'contact', 'subject': 'Welcome {{name}}', 'folder': 'Onboarding', 'status': 'ready', 'version': 1,
            'design': {'accent': '#6554c0', 'background': '#ffffff', 'font': 'Arial', 'blocks': [
                {'id': 'intro', 'type': 'heading', 'text': 'Hello {{name}}', 'size': 32},
                {'id': 'body', 'type': 'text', 'text': 'We are happy to help {{company}}.'}]}}


def test_persistence_version_conflict_and_email_publication(client, db, superuser_headers):
    h = superuser_headers
    data = template()
    created = client.post(ROOT+'/templates', headers=h, json=data)
    assert created.status_code == 201, created.text
    saved = created.json(); identity = saved['id']
    listed = client.get(ROOT+'/templates', headers=h).json()['items']
    assert listed[0]['design']['blocks'][0]['text'] == 'Hello {{name}}'
    data['name'] = 'Welcome updated'
    updated = client.put(f'{ROOT}/templates/{identity}', headers=h, json=data)
    assert updated.status_code == 200, updated.text
    assert updated.json()['version'] == 2
    assert client.put(f'{ROOT}/templates/{identity}', headers=h, json=data).status_code == 409
    published = client.post(f'{ROOT}/templates/{identity}/publish-email', headers=h)
    assert published.status_code == 200, published.text
    again = client.post(f'{ROOT}/templates/{identity}/publish-email', headers=h).json()
    assert again == published.json()
    email = db.get(CommunicationEmailTemplate, again['email_template_id'])
    assert email.organization_id == db.get(CRMVisualTemplate, identity).organization_id
    assert 'font-size:32px' in email.body_html and '{{name}}' in email.body_html
    assert client.delete(f'{ROOT}/templates/{identity}', headers=h).status_code == 204
    assert client.get(ROOT+'/templates', headers=h).json()['items'] == []
    assert db.get(CommunicationEmailTemplate, email.id) is not None


def test_render_escapes_values_and_distinguishes_samples():
    data = template()
    data['design']['blocks'].extend([{'id': 'items', 'type': 'items'}, {'id': 'totals', 'type': 'totals'}])
    actual = render(RenderInput(template=data, values={'name': '<script>alert(1)</script>'}))
    assert '<script>' not in actual['html']
    assert '&lt;script&gt;' in actual['html']
    assert 'company' in actual['unresolved'] and 'document.items' in actual['unresolved']
    sample = render(RenderInput(template=data, sample=True))
    assert not sample['unresolved']
    assert 'Ananya Rao' in sample['html']
    assert '25,000.00' in sample['html']
    assert actual['blocks'][0]['html'] in actual['html']


def test_shared_rich_text_roundtrip_escapes_merge_values(client, superuser_headers):
    data = template()
    data['design']['blocks'][1]['html'] = '<p><strong>Hello {{name}}</strong></p><p><em>Welcome aboard.</em></p><script>bad()</script>'
    created = client.post(ROOT+'/templates', headers=superuser_headers, json=data)
    assert created.status_code == 201, created.text
    saved = created.json()
    assert '<script>' not in saved['design']['blocks'][1]['html']
    rendered = render(RenderInput(template={k: saved[k] for k in data}, values={'name': '<img src=x onerror=alert(1)>', 'company':'Northstar'}))
    assert '<strong>Hello &lt;img' in rendered['body']
    assert '<em>Welcome aboard.</em>' in rendered['body']
    assert '<img src=x' not in rendered['body']


@pytest.mark.parametrize('count', [2, 3])
def test_columns_render_for_email_and_exports(count):
    data = template()
    data['design']['blocks'].append({'id':'columns', 'type':'columns','columns':count,'text':'First {{name}}\n---\nSecond\n---\nThird'})
    result = render(RenderInput(template=data, sample=True))
    fragment = result['blocks'][-1]['html']
    assert fragment.count('<td ') == count
    assert 'First Ananya Rao' in fragment
    assert fragment in result['html']


def test_published_email_reaches_delivery_with_visual_markup(client, db, superuser_headers, monkeypatch):
    from app.apps.communication.api import router as communication
    h = superuser_headers
    person = contact(client, h, full_name='Visual Recipient', email='visual-recipient@example.com')
    saved = client.post(ROOT+'/templates', headers=h, json=template()).json()
    published = client.post(f'{ROOT}/templates/{saved["id"]}/publish-email', headers=h).json()
    email = db.get(CommunicationEmailTemplate, published['email_template_id'])
    delivered = []
    def capture(_db, message, _user):
        delivered.append(message.body)
        message.status = 'sent'
    monkeypatch.setattr(communication, 'deliver_email', capture)
    response = client.post('/api/v1/communication/emails/send', headers=h, json={
        'related_record_type':'contact','related_record_id':person['id'],'to_email':'visual-recipient@example.com',
        'subject':'Welcome Visual Recipient','body':email.body_html.replace('{{name}}','Visual Recipient').replace('{{company}}','Northstar')})
    assert response.status_code in (200,201), response.text
    assert len(delivered) == 1 and 'data-suite-template="v1"' in delivered[0]
    assert 'font-size:32px' in delivered[0] and 'Visual Recipient' in delivered[0]


def test_email_delivery_retains_layout_and_strips_active_content():
    from app.core.rich_text import email_body_parts
    data = template()
    data['design']['blocks'].append({'id': 'button', 'type': 'button', 'url': 'https://example.com', 'text': 'Get started'})
    rendered = render(RenderInput(template=data, sample=True))
    plain, formatted = email_body_parts(rendered['body'])
    assert 'Ananya Rao' in plain
    assert 'font-size:32px' in formatted.replace(' ', '')
    assert 'padding:12px24px' in formatted.replace(' ', '')
    assert 'background-color:#6554c0' in formatted.replace(' ', '')
    _, sanitized = email_body_parts(rendered['body'] + '<script>alert(1)</script><img src="javascript:alert(1)" onerror="alert(2)"><div style="position:fixed;background-image:url(https://evil.test)">Bad</div>')
    assert '<script>' not in sanitized and 'onerror' not in sanitized and 'javascript:' not in sanitized
    assert 'position:' not in sanitized and 'background-image:' not in sanitized


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'data:text/html,test', 'http://example.com/a.png', 'https://example.com/" onerror="alert(1)'])
def test_unsafe_image_urls_rejected(client, superuser_headers, url):
    data = template(); data['design']['blocks'].append({'id': 'image', 'type': 'image', 'url': url})
    response = client.post(ROOT+'/templates', headers=superuser_headers, json=data)
    assert response.status_code == 422, response.text


def test_tenant_isolation_and_merge_visibility(client, db, superuser_headers):
    h = superuser_headers
    person = contact(client, h, full_name='Asha Merge', email='asha@example.com')
    choices = client.get(ROOT+'/records', headers=h, params={'module': 'contact', 'search': 'Asha'})
    assert choices.status_code == 200, choices.text
    assert choices.json()['items'] == [{'id': person['id'], 'name': 'Asha Merge'}]
    assert client.get(ROOT+'/records', headers=h, params={'module': 'contact', 'search': 'no such recipient'}).json()['items'] == []
    data = template('mail_merge', 'letter')
    saved = client.post(ROOT+'/templates', headers=h, json=data).json()
    response = client.post(f'{ROOT}/templates/{saved["id"]}/merge', headers=h, json={'entity': 'contacts', 'record_ids': [person['id']], 'values': {'company': 'Northstar'}})
    assert response.status_code == 200, response.text
    merged = response.json()['items'][0]
    assert 'Asha Merge' in merged['html'] and 'Northstar' in merged['html']
    assert not merged['unresolved']
    missing = client.post(f'{ROOT}/templates/{saved["id"]}/merge', headers=h, json={'entity': 'contacts', 'record_ids': [person['id'], 999999]})
    assert missing.status_code == 404
    row = db.get(CRMVisualTemplate, saved['id'])
    from app.models.company import Company
    other = Company(name='Other template tenant', is_active=True); db.add(other); db.flush()
    row.organization_id = other.id; db.commit()
    assert client.get(ROOT+'/templates', headers=h).json()['items'] == []
    assert client.put(f'{ROOT}/templates/{saved["id"]}', headers=h, json=data).status_code == 404
    assert client.delete(f'{ROOT}/templates/{saved["id"]}', headers=h).status_code == 404


def test_category_validation_duplicate_blocks_and_draft_publish(client, superuser_headers):
    h = superuser_headers
    data = template('inventory', 'email')
    assert client.post(ROOT+'/templates', headers=h, json=data).status_code == 422
    data = template(); data['design']['blocks'].append(copy.deepcopy(data['design']['blocks'][0]))
    assert client.post(ROOT+'/templates', headers=h, json=data).status_code == 422
    data = template(); data['status'] = 'draft'
    saved = client.post(ROOT+'/templates', headers=h, json=data).json()
    assert client.post(f'{ROOT}/templates/{saved["id"]}/publish-email', headers=h).status_code == 422


@pytest.mark.parametrize(('category','kind'), [('inventory','invoice'),('inventory','quotation'),('inventory','sales_order'),('inventory','purchase_order'),('mail_merge','letter'),('mail_merge','agreement'),('mail_merge','form'),('mail_merge','label'),('mail_merge','envelope')])
def test_all_document_types_save(client, superuser_headers, category, kind):
    response = client.post(ROOT+'/templates', headers=superuser_headers, json=template(category, kind))
    assert response.status_code == 201, response.text
    assert response.json()['document_type'] == kind
