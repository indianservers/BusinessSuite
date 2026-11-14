"""Native helpdesk creation validation and persisted status lifecycle."""
import pytest
from app.models.helpdesk import HelpdeskCategory, HelpdeskTicket
from tests.test_ticket_actions import seed
from tests.rich_text_test_utils import organization_context
from tests.test_ai_operator import isolate_generic_http_audit

ROOT = '/api/v1/helpdesk/tickets'


def create(client, headers, endpoint, payload):
    return client.post(ROOT + endpoint, headers=headers,
                       **({'json': payload} if endpoint else {'params': payload}))


@pytest.mark.parametrize('endpoint', ['', '/json'])
@pytest.mark.parametrize('category', ['missing', 'inactive'])
def test_invalid_category_rejected_without_ticket(client, db, endpoint, category):
    headers, _, _ = seed(client, db)
    row = HelpdeskCategory(name='Inactive synthetic category', is_active=False)
    db.add(row); db.commit()
    count = db.query(HelpdeskTicket).count()
    response = create(client, headers, endpoint, {'subject': 'Synthetic request',
        'description': 'Synthetic category validation',
        'category_id': row.id if category == 'inactive' else 2147483647})
    assert response.status_code == 422, response.text
    assert db.query(HelpdeskTicket).count() == count


@pytest.mark.parametrize('endpoint', ['', '/json'])
@pytest.mark.parametrize('invalid', [{'subject': ' '}, {'description': ' '},
    {'subject': 'x' * 301}, {'priority': 'Unknown'}, {'category_id': 0}])
def test_invalid_creation_fields_rejected(client, db, endpoint, invalid):
    headers, _, _ = seed(client, db)
    count = db.query(HelpdeskTicket).count()
    response = create(client, headers, endpoint,
        {'subject': 'Synthetic request', 'description': 'Synthetic request details', **invalid})
    assert response.status_code == 422, response.text
    assert db.query(HelpdeskTicket).count() == count


def test_category_sla_status_close_and_reopen_persist(client, db):
    headers, _, _ = seed(client, db)
    category = HelpdeskCategory(name='Synthetic payroll support', sla_hours=8, is_active=True)
    db.add(category); db.commit()
    response = create(client, headers, '/json', {'subject': 'Synthetic lifecycle request',
        'description': 'Persisted support lifecycle', 'category_id': category.id, 'priority': 'High'})
    assert response.status_code == 201, response.text
    row = response.json(); ident = row['id']
    from datetime import datetime
    first = datetime.fromisoformat(row['first_response_due_at'])
    resolution = datetime.fromisoformat(row['resolution_due_at'])
    assert (resolution - first).total_seconds() == 4 * 3600
    assert row['status'] == 'Open' and row['priority'] == 'High'
    for status in ['In Progress', 'Pending', 'Resolved', 'Closed', 'Open']:
        response = client.put(f'{ROOT}/{ident}/status/json', headers=headers,
            json={'status': status, 'expected_version': row['version']})
        assert response.status_code == 200, response.text
        fresh = client.get(f'{ROOT}/{ident}', headers=headers)
        assert fresh.status_code == 200, fresh.text
        row = fresh.json()
        assert row['status'] == status
        if status == 'Resolved': assert row['resolved_at'] and not row['closed_at']
        if status == 'Closed': assert row['resolved_at'] and row['closed_at']
        if status in ['In Progress', 'Pending', 'Open']:
            assert not row['resolved_at'] and not row['closed_at']
        db.expire_all()
        assert db.get(HelpdeskTicket, ident).status == status
