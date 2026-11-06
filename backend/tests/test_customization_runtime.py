"""Business behaviour, not just metadata creation, for universal custom records."""
import pytest
from app.apps.customization.models import CustomizationAuditLog, CustomizationRecord
from app.apps.crm.models import CRMTask
from app.models.approval_os import ApprovalRequest, ApprovalHistory
from app.models.user import User
from tests.customization_test_utils import customization_headers, create_module


def field(client, headers, module, name, kind='number', **config):
    response = client.post('/api/v1/customization/fields', headers=headers, json={
        'module_name': module, 'field_api_name': name, 'field_label': name,
        'field_type': kind, **config})
    assert response.status_code == 201, response.text
    return response.json()


def save(client, headers, module, values, identifier=None):
    path = '/api/v1/custom/' + module + (f'/{identifier}' if identifier else '')
    return (client.put if identifier else client.post)(path, headers=headers, json={'values': values})


def read(client, headers, module, identifier):
    response = client.get(f'/api/v1/custom/{module}/{identifier}', headers=headers)
    assert response.status_code == 200, response.text
    return response.json()['values_json']


def test_formula_defaults_chains_tampering_and_atomic_failure(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'jobs')
    field(client, h, 'jobs', 'price', default_value='100')
    field(client, h, 'jobs', 'quantity')
    field(client, h, 'jobs', 'total', 'formula', formula_expression='price * quantity', editable=False)
    field(client, h, 'jobs', 'half', 'formula', formula_expression='total / 2', editable=False)
    field(client, h, 'jobs', 'reference', 'auto_number', editable=False)
    response = save(client, h, 'jobs', {'quantity': 3})
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['values_json']['total'] == '300'
    assert row['values_json']['half'] == '150'
    assert row['values_json']['reference'].startswith('JOBS-')
    updated = save(client, h, 'jobs', {'price': 20}, row['id'])
    assert updated.status_code == 200, updated.text
    assert updated.json()['values_json']['total'] == '60'
    for key in ('total', 'reference'):
        assert save(client, h, 'jobs', {key: 'forged'}, row['id']).status_code == 422
    assert read(client, h, 'jobs', row['id'])['total'] == '60'
    field(client, h, 'jobs', 'broken', 'formula', formula_expression='price / 0', editable=False)
    failed = save(client, h, 'jobs', {'quantity': 5})
    assert failed.status_code == 400, failed.text
    assert db.query(CustomizationRecord).filter_by(module_api_name='jobs').count() == 1


def test_rollups_follow_edits_reassignment_deletes_and_related_lists(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'customers')
    create_module(client, h, 'orders')
    field(client, h, 'customers', 'name', 'text')
    field(client, h, 'orders', 'customer', 'lookup', lookup_module='customers')
    field(client, h, 'orders', 'amount', 'decimal')
    field(client, h, 'customers', 'spend', 'rollup', editable=False, rollup_config_json={
        'related_module_name': 'orders', 'lookup_field': 'customer', 'aggregate_function': 'sum', 'aggregate_field': 'amount'})
    field(client, h, 'customers', 'double_spend', 'formula', editable=False, formula_expression='spend * 2')
    a = save(client, h, 'customers', {'name': 'A'}).json()['id']
    b = save(client, h, 'customers', {'name': 'B'}).json()['id']
    first = save(client, h, 'orders', {'customer': a, 'amount': '10.10'})
    assert first.status_code == 201, first.text
    order = first.json()['id']
    assert read(client, h, 'customers', a)['double_spend'] == '20.20'
    assert save(client, h, 'orders', {'amount': '12.25'}, order).status_code == 200
    assert read(client, h, 'customers', a)['spend'] == '12.25'
    assert save(client, h, 'orders', {'customer': b}, order).status_code == 200
    assert read(client, h, 'customers', a)['spend'] == '0'
    assert read(client, h, 'customers', b)['spend'] == '12.25'
    related = client.post('/api/v1/customization/related-lists', headers=h, json={
        'module_name': 'customers', 'related_module_name': 'orders', 'lookup_field': 'customer', 'label': 'Orders'}).json()
    response = client.get(f'/api/v1/custom/customers/{b}/related/{related["id"]}', headers=h)
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1
    assert client.delete(f'/api/v1/custom/customers/{b}', headers=h).status_code == 409
    assert client.delete(f'/api/v1/custom/orders/{order}', headers=h).status_code == 204
    assert read(client, h, 'customers', b)['spend'] == '0'
    assert client.delete(f'/api/v1/custom/customers/{b}', headers=h).status_code == 204


def test_lookup_types_missing_targets_and_search_paging(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'vehicles')
    create_module(client, h, 'repairs')
    field(client, h, 'vehicles', 'registration', 'text')
    field(client, h, 'repairs', 'vehicle', 'lookup', lookup_module='vehicles')
    target = save(client, h, 'vehicles', {'registration': 'KA-01'}).json()['id']
    for invalid in (True, str(target), 999999):
        assert save(client, h, 'repairs', {'vehicle': invalid}).status_code in (404, 422)
    assert save(client, h, 'repairs', {'vehicle': target}).status_code == 201
    save(client, h, 'vehicles', {'registration': 'TN-02'})
    save(client, h, 'vehicles', {'registration': 'KA-03'})
    result = client.get('/api/v1/custom/vehicles', headers=h, params={'search': 'KA-', 'per_page': 1, 'page': 2})
    assert result.status_code == 200, result.text
    assert result.json()['total'] == 2
    assert len(result.json()['items']) == 1
    assert client.get('/api/v1/custom/vehicles?per_page=101', headers=h).status_code == 422
    assert client.get('/api/v1/custom/vehicles?search=%25', headers=h).json()['total'] == 0


def test_formula_cycle_is_rejected_and_not_persisted(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'cycles')
    field(client, h, 'cycles', 'a', 'formula', formula_expression='b + 1')
    field(client, h, 'cycles', 'b', 'formula', formula_expression='a + 1')
    assert save(client, h, 'cycles', {}).status_code == 422
    assert db.query(CustomizationRecord).filter_by(module_api_name='cycles').count() == 0


def test_buttons_execute_once_validate_target_and_enforce_native_permissions(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'requests')
    field(client, h, 'requests', 'name', 'text')
    row = save(client, h, 'requests', {'name': 'Repair approval'}).json()['id']
    button = client.post('/api/v1/customization/buttons', headers=h, json={
        'module_name': 'requests', 'label': 'Log handover', 'action_type': 'timeline_event',
        'action_config_json': {'title': {'$record': 'values.name'}}}).json()
    path = f'/api/v1/customization/buttons/{button["id"]}/execute'
    payload = {'record_id': row, 'request_key': 'handover-123'}
    one = client.post(path, headers=h, json=payload)
    assert one.status_code == 200, one.text
    two = client.post(path, headers=h, json=payload)
    assert two.status_code == 200 and two.json() == one.json()
    assert db.query(CustomizationAuditLog).filter_by(action='timeline_event').count() == 1
    assert client.post(path, headers=h, json={**payload, 'payload': {'different': True}}).status_code == 409
    assert client.post(path, headers=h, json={**payload, 'record_id': 999999}).status_code == 404
    task = client.post('/api/v1/customization/buttons', headers=h, json={
        'module_name': 'requests', 'label': 'Create follow-up', 'action_type': 'create_task',
        'action_config_json': {'title': 'Follow up'}}).json()
    denied = client.post(f'/api/v1/customization/buttons/{task["id"]}/execute', headers=h, json={'record_id': row, 'request_key': 'denied-task-123'})
    assert denied.status_code == 403, denied.text
    assert db.query(CRMTask).count() == 0


def test_task_and_approval_buttons_reuse_existing_modules(client, db, superuser_headers):
    h = superuser_headers
    create_module(client, h, 'engagements')
    field(client, h, 'engagements', 'name', 'text')
    row = save(client, h, 'engagements', {'name': 'Review books'}).json()['id']
    task = client.post('/api/v1/customization/buttons', headers=h, json={
        'module_name': 'engagements', 'label': 'Follow up', 'action_type': 'create_task',
        'action_config_json': {'title': {'$record': 'values.name'}}}).json()
    response = client.post(f'/api/v1/customization/buttons/{task["id"]}/execute', headers=h, json={'record_id': row, 'request_key': 'create-task-123'})
    assert response.status_code == 200, response.text
    created = db.get(CRMTask, response.json()['task_id'])
    assert created.title == 'Review books' and created.task_details['customRecordId'] == row
    customization_headers(client, db, 'reviewer@example.com')
    reviewer = db.query(User).filter_by(email='reviewer@example.com').one()
    button = client.post('/api/v1/customization/buttons', headers=h, json={
        'module_name': 'engagements', 'label': 'Request review', 'action_type': 'submit_approval',
        'action_config_json': {'title': 'Review books', 'assigned_to_user_id': reviewer.id}}).json()
    result = client.post(f'/api/v1/customization/buttons/{button["id"]}/execute', headers=h, json={'record_id': row, 'request_key': 'approval-123'})
    assert result.status_code == 200, result.text
    request = db.get(ApprovalRequest, result.json()['approval_id'])
    assert request.status == 'Pending' and request.entity_id == row
    assert db.query(ApprovalHistory).filter_by(request_id=request.id, event_type='created').count() == 1


def test_company_isolation_lookup_owner_and_readonly_permissions(client, db):
    alpha = customization_headers(client, db)
    beta = customization_headers(client, db, 'beta-custom@example.com', company_id=2)
    create_module(client, alpha, 'alpha_customers')
    create_module(client, beta, 'beta_jobs')
    field(client, alpha, 'alpha_customers', 'name', 'text')
    a = save(client, alpha, 'alpha_customers', {'name': 'Private alpha'}).json()['id']
    assert client.get(f'/api/v1/custom/alpha_customers/{a}', headers=beta).status_code == 404
    assert client.post('/api/v1/customization/fields', headers=beta, json={
        'module_name': 'beta_jobs', 'field_api_name': 'customer', 'field_label': 'Customer',
        'field_type': 'lookup', 'lookup_module': 'alpha_customers'}).status_code == 404
    beta_user = db.query(User).filter_by(email='beta-custom@example.com').one()
    bad_owner = client.post('/api/v1/custom/alpha_customers', headers=alpha, json={'values': {'name': 'A'}, 'owner_user_id': beta_user.id})
    assert bad_owner.status_code == 422, bad_owner.text
    viewer = customization_headers(client, db, 'record-viewer@example.com', permissions=['customization_view'])
    assert client.get(f'/api/v1/custom/alpha_customers/{a}', headers=viewer).status_code == 200
    assert save(client, viewer, 'alpha_customers', {'name': 'forged'}, a).status_code == 403
    assert client.delete(f'/api/v1/custom/alpha_customers/{a}', headers=viewer).status_code == 403


def test_decimal_constants_rules_and_failed_edits_are_atomic(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'estimates')
    field(client, h, 'estimates', 'amount', 'decimal')
    field(client, h, 'estimates', 'tax', 'formula', formula_expression='round(amount * 0.18, 2)', editable=False)
    response = save(client, h, 'estimates', {'amount': '10.25'})
    assert response.status_code == 201, response.text
    identifier = response.json()['id']
    assert response.json()['values_json']['tax'] == '1.84'
    rule = client.post('/api/v1/customization/validation-rules', headers=h, json={
        'module_name': 'estimates', 'name': 'Tax limit', 'condition_json': {'field': 'tax', 'operator': 'greater_than', 'value': 2}, 'error_message': 'Tax too large'})
    assert rule.status_code == 201
    rejected = save(client, h, 'estimates', {'amount': '20'}, identifier)
    assert rejected.status_code == 400, rejected.text
    assert read(client, h, 'estimates', identifier)['amount'] == '10.25'


def test_connector_actions_use_governed_adapter_and_do_not_repeat_unknown_outcomes(client, db, superuser_headers, monkeypatch):
    h = superuser_headers
    create_module(client, h, 'exports')
    field(client, h, 'exports', 'name', 'text')
    identifier = save(client, h, 'exports', {'name': 'Approved export'}).json()['id']
    button = client.post('/api/v1/customization/buttons', headers=h, json={
        'module_name': 'exports', 'label': 'Export', 'action_type': 'webhook',
        'action_config_json': {'connection_id': 12, 'operation': 'send', 'payload': {'name': {'$record': 'values.name'}}}}).json()
    calls = []
    def adapter(db, actor, company, module, connection, operation, payload):
        calls.append((module, connection, operation, payload))
        return {'status': 'accepted'}
    monkeypatch.setattr('app.shared.integrations.invoke', adapter)
    monkeypatch.setattr('app.shared.integrations.prepare_operation', lambda *args: None)
    path = f'/api/v1/customization/buttons/{button["id"]}/execute'
    payload = {'record_id': identifier, 'request_key': 'governed-export-123'}
    first = client.post(path, headers=h, json=payload)
    assert first.status_code == 200, first.text
    assert client.post(path, headers=h, json=payload).json() == first.json()
    assert calls == [('customization', 12, 'send', {'name': 'Approved export'})]
    def uncertain(*args):
        calls.append('unknown')
        raise TimeoutError('Provider may have received the request')
    monkeypatch.setattr('app.shared.integrations.invoke', uncertain)
    pending = {**payload, 'request_key': 'uncertain-export-123'}
    assert client.post(path, headers=h, json=pending).status_code == 502
    assert client.post(path, headers=h, json=pending).status_code == 409
    assert client.post(path, headers=h, json={**pending, 'request_key': 'new-key-after-timeout'}).status_code == 409
    assert calls.count('unknown') == 1


@pytest.mark.parametrize('operation,expected', [('count', 2), ('sum', '30'), ('avg', '15'), ('min', '10'), ('max', '20')])
def test_all_rollup_operations_filter_unrelated_parents(client, db, operation, expected):
    h = customization_headers(client, db)
    create_module(client, h, 'parents')
    create_module(client, h, 'lines')
    field(client, h, 'parents', 'name', 'text')
    field(client, h, 'lines', 'parent', 'lookup', lookup_module='parents')
    field(client, h, 'lines', 'amount', 'decimal')
    parent = save(client, h, 'parents', {'name': 'A'}).json()['id']
    unrelated = save(client, h, 'parents', {'name': 'B'}).json()['id']
    for amount in ('10', '20'):
        assert save(client, h, 'lines', {'parent': parent, 'amount': amount}).status_code == 201
    assert save(client, h, 'lines', {'parent': unrelated, 'amount': '999'}).status_code == 201
    configured = client.post('/api/v1/customization/rollups', headers=h, json={
        'module_name': 'parents', 'field_api_name': 'aggregate', 'related_module_name': 'lines',
        'lookup_field': 'parent', 'aggregate_function': operation, 'aggregate_field': 'amount'})
    assert configured.status_code == 201, configured.text
    assert read(client, h, 'parents', parent)['aggregate'] == expected


def test_open_url_rejects_script_and_noop_is_not_reported_executed(client, db):
    h = customization_headers(client, db)
    create_module(client, h, 'links')
    identifier = save(client, h, 'links', {}).json()['id']
    for action, config, status in [('open_url', {'url': 'javascript:alert(1)'}, 422), ('open_url', {'url': 'https://example.com/help'}, 200), ('noop', {}, 200)]:
        button = client.post('/api/v1/customization/buttons', headers=h, json={
            'module_name': 'links', 'label': 'Link', 'action_type': action, 'action_config_json': config}).json()
        response = client.post(f'/api/v1/customization/buttons/{button["id"]}/execute', headers=h, json={'record_id': identifier, 'request_key': f'link-{button["id"]}-123'})
        assert response.status_code == status, response.text
        if status == 200:
            assert response.json()['status'] == ('skipped' if action == 'noop' else 'ready')


def test_ungoverned_connector_is_denied_before_external_io(client, db, superuser_headers, monkeypatch):
    h = superuser_headers
    create_module(client, h, 'connector_records')
    identifier = save(client, h, 'connector_records', {}).json()['id']
    button = client.post('/api/v1/customization/buttons', headers=h, json={
        'module_name': 'connector_records', 'label': 'Export', 'action_type': 'webhook',
        'action_config_json': {'connection_id': 99999, 'operation': 'send', 'payload': {}}}).json()
    calls = []
    monkeypatch.setattr('app.shared.integrations.send', lambda *args: calls.append(args))
    response = client.post(f'/api/v1/customization/buttons/{button["id"]}/execute', headers=h,
        json={'record_id': identifier, 'request_key': 'unapproved-connection'})
    assert response.status_code == 403, response.text
    assert calls == []
    assert db.query(CustomizationAuditLog).filter_by(entity_type='button', action='executed').count() == 0


def test_metadata_validation_and_stable_module_identifier(client, db):
    h = customization_headers(client, db)
    module = create_module(client, h, 'stable_records')
    bad = client.put(f'/api/v1/customization/modules/{module["id"]}', headers=h, json={**module, 'module_api_name': 'renamed_records'})
    assert bad.status_code == 409
    malformed = client.post('/api/v1/customization/buttons', headers=h, json={'module_name': 'stable_records'})
    assert malformed.status_code == 422, malformed.text
    create_module(client, h, 'rollup_children')
    field(client, h, 'rollup_children', 'parent', 'lookup', lookup_module='stable_records')
    field(client, h, 'rollup_children', 'amount')
    field(client, h, 'rollup_children', 'status', 'text')
    field(client, h, 'stable_records', 'paid', 'rollup', rollup_config_json={
        'related_module_name': 'rollup_children', 'lookup_field': 'parent', 'aggregate_function': 'sum', 'aggregate_field': 'amount',
        'condition': {'field': 'status', 'operator': 'equals', 'value': 'Paid'}})
    identifier = save(client, h, 'stable_records', {}).json()['id']
    assert save(client, h, 'rollup_children', {'parent': identifier, 'amount': 10, 'status': 'Paid'}).status_code == 201
    assert save(client, h, 'rollup_children', {'parent': identifier, 'amount': 90, 'status': 'Draft'}).status_code == 201
    assert read(client, h, 'stable_records', identifier)['paid'] == '10'
