"""Dashboard-only statistics preserve full scoped totals with less SQL work."""
from sqlalchemy import event
from app.apps.crm.models import CRMLead
from app.models.user import User
from tests.test_contact_directory import directory_identity


def test_statistics_only_preserves_totals_and_avoids_legacy_summary_work(client, db, superuser_headers, directory_identity):
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    db.add_all([CRMLead(organization_id=1, branch_id=directory_identity.id, owner_user_id=actor.id,
                       first_name='Synthetic', full_name=f'Synthetic dashboard lead {i}', source='Referral', status='New')
                for i in range(121)])
    db.commit()
    url = '/api/v1/crm/dashboard'
    # Warm shared authorization/metadata caches before comparing endpoint work.
    assert client.get(url, headers=superuser_headers, params={'period': 'all'}).status_code == 200
    statements = []
    def collect(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith('select'):
            statements.append(statement)
    engine = db.get_bind().engine
    event.listen(engine, 'before_cursor_execute', collect)
    try:
        full = client.get(url, headers=superuser_headers, params={'period': 'all'})
        full_selects = len(statements); statements.clear()
        lean = client.get(url, headers=superuser_headers, params={'period': 'all', 'statistics_only': True})
        lean_selects = len(statements)
    finally:
        event.remove(engine, 'before_cursor_execute', collect)
    assert full.status_code == lean.status_code == 200
    full, lean = full.json(), lean.json()
    assert 'summary' in full and set(lean) == {'period_statistics', 'context'}
    assert lean['period_statistics']['leads_created'] == 121  # Not the first100 list rows.
    assert {k: v for k, v in full['period_statistics'].items() if k != 'context'} == {k: v for k, v in lean['period_statistics'].items() if k != 'context'}
    assert lean['context']['period'] == 'all'
    assert full_selects - lean_selects >= 5
    invalid = client.get(url, headers=superuser_headers, params={'period': 'invalid', 'statistics_only': True})
    assert invalid.status_code == 422


def test_dashboard_records_match_native_lists_and_keep_entity_denials(client, db, superuser_headers, directory_identity, monkeypatch):
    import importlib
    from app.apps.crm.models import CRMCompany
    actor = db.query(User).filter_by(email='testadmin@test.com').one()
    db.add_all([CRMCompany(organization_id=1, branch_id=directory_identity.id,
                          owner_user_id=actor.id, name=f'Dashboard company {i}') for i in range(121)])
    db.commit()
    router = importlib.import_module('app.apps.crm.api.router')
    response = client.get('/api/v1/crm/dashboard/records', headers=superuser_headers)
    assert response.status_code == 200, response.text
    resources = response.json()['resources']
    assert set(resources) == {'companies', 'deals', 'tasks', 'activities', 'pipeline-stages'}
    assert resources['companies']['total'] == 121
    assert len(resources['companies']['items']) == 100
    for entity, actual in resources.items():
        params = {'page': 1, 'per_page': 100}
        if entity == 'pipeline-stages':
            params.update(sort_by='position', sort_order='asc')
        native = client.get(f'/api/v1/crm/{entity}', headers=superuser_headers, params=params)
        assert native.status_code == 200, native.text
        assert actual == native.json()
    from fastapi import HTTPException
    original = router._assert_entity_permission
    def permission(entity, user, action):
        if entity == 'tasks':
            raise HTTPException(403, 'Tasks restricted')
        return original(entity, user, action)
    monkeypatch.setattr(router, '_assert_entity_permission', permission)
    denied = client.get('/api/v1/crm/dashboard/records', headers=superuser_headers)
    assert denied.status_code == 200
    assert denied.json()['resources']['tasks'] == {'items': [], 'status': 403, 'error': 'Tasks restricted'}
    for entity in set(resources) - {'tasks'}:
        assert denied.json()['resources'][entity] == resources[entity]
