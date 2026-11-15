"""Canonical native project authorization within an isolated Construction pack."""
from uuid import uuid4
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.apps.project_management.models import PMSProject, PMSProjectMember
from app.branches.models import BranchOwnership
from app.business_packs.models import PackActivation, PackContext, PackUserGrant, PackRecordOwnership
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.native_policy import native_srm_policy
from app.business_packs.construction import project_for_action
from tests.test_service_checkout import scenario, catalog, directory_identity
from tests.test_srm_native_transaction_operations import native_writer


@pytest.mark.parametrize('pack', ['hospital', 'salon', 'restaurant', 'pharma'])
def test_other_pack_cashiers_cannot_collect_construction_measurements(client, db, construction, catalog, pack):
    from tests.test_business_pack_http_integration import grant
    from app.apps.srm.models import SRMReceipt
    actor, branch, _, _ = construction
    selected, _ = grant(db, actor, branch, pack, 'cashier')
    response = client.post('/api/v1/srm/industry/records/1/payments',
        headers={**catalog[0], 'X-Suite-Pack-Context': str(selected.id)},
        json={'request_id': str(uuid4()), 'amount': '1.00', 'payment_method': 'bank_transfer'})
    assert response.status_code == 403, response.text
    assert response.json()['detail'] == 'An authorized Construction collection context is required'
    assert db.query(SRMReceipt).count() == 0


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_specialists_cannot_read_financial_document_controls(client, db, construction, catalog, pack, role):
    from tests.test_business_pack_http_integration import grant
    actor, branch, _, _ = construction
    selected, _ = grant(db, actor, branch, pack, role)
    response = client.get('/api/v1/srm/documents/invoices/1',
        headers={**catalog[0], 'X-Suite-Pack-Context': str(selected.id)})
    assert response.status_code == 403, response.text
    assert response.json()['detail']['code'] == 'business_pack_operation_denied'


@pytest.mark.parametrize('billing_role', ['project_manager', 'billing_officer'])
def test_native_construction_certified_invoice_retains_full_receivable(client, db, construction, catalog, billing_role, monkeypatch):
    from app.apps.srm.commercial_models import ProjectCommercial
    from app.business_packs.models import PackMasterAvailability
    from app.apps.srm.models import SRMInvoice
    actor, branch, context_id, project_id = construction
    db.add(ProjectCommercial(project_id=project_id, customer_id=101, seller_id=1, currency='INR', updated_by=actor.id))
    db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
        resource_table='crm_companies', resource_key='101', active=True))
    db.commit()
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    root = '/api/v1/srm/industry'
    def post(path, data, expected=201):
        response = client.post(root + path, headers=headers, json=data)
        assert response.status_code == expected, response.text
        return response.json()
    boq = post('/boq', {'request_id': str(uuid4()), 'title': 'Certified construction billing',
        'project_id': project_id, 'code': 'CERTIFIED', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1000', 'tax_rate': '18'})
    post(f'/records/{boq["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    measured = post('/measurements', {'request_id': str(uuid4()), 'title': 'Actual measured work',
        'boq_id': boq['id'], 'quantity': '6', 'measured_on': '2026-11-15'})
    approved = post(f'/records/{measured["id"]}/transition', {'expected_revision': 1, 'status': 'approved'}, 200)
    owner_headers = headers
    if billing_role == 'billing_officer':
        from app.access.models import AccessPolicy
        from tests.test_business_pack_http_integration import native_actor, grant
        financial_headers, financial_actor = native_actor(db, branch)
        grant(db, financial_actor, branch, 'construction', 'billing_officer', db.get(PackContext, context_id))
        policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=financial_actor.id).one()
        policy.grants = {**policy.grants, 'project_management': {'enabled': True,
            'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'organization'}}
        db.add(PMSProjectMember(project_id=project_id, user_id=financial_actor.id, role='Viewer'))
        db.commit()
        headers = {**financial_headers, 'X-Suite-Pack-Context': str(context_id)}
    payload = {'expected_revision': approved['revision'], 'retention_percent': '5'}
    invoice = post(f'/records/{measured["id"]}/invoice', payload)
    assert Decimal(str(invoice['total_amount'])) == Decimal('7080.00')
    assert Decimal(str(invoice['balance_amount'])) == Decimal('7080.00')
    assert post(f'/records/{measured["id"]}/invoice', payload)['id'] == invoice['id']
    issued = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=headers)
    assert issued.status_code == 200, issued.text
    detail = client.get(f'/api/v1/srm/invoices/{invoice["id"]}', headers=headers)
    assert detail.status_code == 200, detail.text
    assert Decimal(str(detail.json()['balance_amount'])) == Decimal('7080.00')
    workspace = client.get(f'/api/v1/srm/business/invoices/{invoice["id"]}', headers=headers)
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()['construction_measurement_id'] == measured['id']
    assert workspace.json()['can_record_payment'] is (billing_role == 'billing_officer')
    document = client.get(f'/api/v1/srm/documents/invoices/{invoice["id"]}', headers=headers)
    assert document.status_code == 200, document.text
    assert document.json()['record']['id'] == invoice['id']
    assert len(document.json()['version']) == 64
    assert document.json()['editable'] is False
    other_kind = client.get(f'/api/v1/srm/documents/contracts/{invoice["id"]}', headers=headers)
    assert other_kind.status_code == 503, other_kind.text
    choices = client.get('/api/v1/srm/business/collection-invoices', headers=headers)
    assert choices.status_code == 200, choices.text
    assert choices.json()['can_record'] is (billing_role == 'billing_officer')
    assert [item['construction_measurement_id'] for item in choices.json()['items']] == [measured['id']]
    assert db.query(SRMInvoice).count() == 1
    summary = client.get(root + f'/projects/{project_id}/summary', headers=owner_headers)
    assert summary.status_code == 200, summary.text
    assert Decimal(str(summary.json()['retention_tracked'])) == Decimal('300.00')
    assert Decimal(str(summary.json()['unbilled_certified_value'])) == 0
    # A later project currency change cannot reprice the issued source invoice.
    db.get(ProjectCommercial, project_id).currency = 'USD'
    db.commit()
    historical = client.get(f'/api/v1/srm/invoices/{invoice["id"]}', headers=headers)
    assert historical.status_code == 200, historical.text
    assert historical.json()['currency'] == 'INR'
    payment_path = f'/records/{measured["id"]}/payments'
    paid = {'request_id': str(uuid4()), 'amount': '2000.00', 'payment_method': 'bank_transfer', 'reference': 'Certified work installment'}
    from app.apps.srm.models import SRMReceipt, SRMReceiptAllocation
    if billing_role == 'project_manager':
        post(payment_path, paid, 403)
        assert db.query(SRMReceipt).count() == 0
    else:
        # A failure after native receipt/allocation creation must not leave money
        # behind or consume the request key before the outer transaction commits.
        from app.apps.srm import payments as native_payments
        from app.apps.srm.models import SRMInvoiceHistory, SRMRevenueEvent
        from app.apps.srm.commercial_models import ReceiptContext
        rollback_models = (SRMInvoiceHistory, SRMRevenueEvent, ReceiptContext)
        before_failure = {model: db.query(model).count() for model in rollback_models}
        original_payment = native_payments.record_payment_operation
        def fail_after_native_payment(*args, **kwargs):
            result = original_payment(*args, **kwargs)
            assert kwargs['commit'] is False
            assert result['receipt_id']
            raise RuntimeError('construction payment late failure')
        with monkeypatch.context() as fault:
            fault.setattr(native_payments, 'record_payment_operation', fail_after_native_payment)
            with pytest.raises(RuntimeError, match='construction payment late failure'):
                client.post(root + payment_path, headers=headers, json=paid)
        db.expire_all()
        assert db.query(SRMReceipt).count() == 0
        assert db.query(SRMReceiptAllocation).count() == 0
        assert {model: db.query(model).count() for model in rollback_models} == before_failure
        unchanged = client.get(f'/api/v1/srm/invoices/{invoice["id"]}', headers=headers)
        assert unchanged.status_code == 200, unchanged.text
        assert Decimal(str(unchanged.json()['balance_amount'])) == Decimal('7080.00')
        partial = post(payment_path, paid)
        assert Decimal(str(partial['invoice']['balance_amount'])) == Decimal('5080.00')
        assert post(payment_path, paid)['receipt_id'] == partial['receipt_id']
        post(payment_path, {**paid, 'amount': '2001.00'}, 409)
        post(payment_path, {**paid, 'request_id': str(uuid4()), 'amount': '5080.01'}, 422)
        settled = post(payment_path, {**paid, 'request_id': str(uuid4()), 'amount': '5080.00', 'reference': 'Final certified work payment'})
        assert Decimal(str(settled['invoice']['balance_amount'])) == 0
        assert Decimal(str(settled['invoice']['paid_amount'])) == Decimal('7080.00')
        assert db.query(SRMReceipt).count() == 2
        assert db.query(SRMReceiptAllocation).count() == 2
        refreshed = client.get(f'/api/v1/srm/business/invoices/{invoice["id"]}', headers=headers)
        assert refreshed.status_code == 200, refreshed.text
        assert len(refreshed.json()['payments']) == 2
    from app.apps.srm.industry_models import IndustryRecord
    from app.apps.srm.commercial_models import InvoiceContext
    from app.business_packs.construction_billing import source_reserved, project_reference
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            # An approved source ID alone cannot borrow the private creation command.
            with pytest.raises(HTTPException) as denied:
                source_reserved(db, measured['id'])
            assert denied.value.status_code == 403
            forged = InvoiceContext(invoice_id=invoice['id'], project_id=project_id,
                seller_id=1, request_id='industry:' + str(measured['id']), origin='srm')
            assert not project_reference(db, scope, forged, PMSProject.__table__, [('project_id', PMSProject.__table__.c.id)])
            with pytest.raises(HTTPException) as tampered:
                with db.begin_nested():
                    row = db.get(IndustryRecord, measured['id'])
                    stamp = {**row.data['_construction_invoice_source'], 'customer_id': 999999}
                    row.data = {**row.data, '_construction_invoice_source': stamp}
                    db.flush()
            assert tampered.value.status_code == 403
            for patch in ({'unit_rate': '1'}, {'currency': 'USD'}, {'retention_amount': '9999.00'}):
                with pytest.raises(HTTPException) as changed:
                    with db.begin_nested():
                        row = db.get(IndustryRecord, measured['id'])
                        row.data = {**row.data, **patch}
                        db.flush()
                assert changed.value.status_code == 403
            with pytest.raises(HTTPException) as changed_status:
                with db.begin_nested():
                    db.get(IndustryRecord, measured['id']).status = 'draft'
                    db.flush()
            assert changed_status.value.status_code == 403
        finally:
            cleanup()


@pytest.mark.parametrize('currency', ['INR', 'USD'])
def test_native_construction_measurements_variation_and_diary(client, db, construction, catalog, currency):
    actor, branch, context_id, project_id = construction
    if currency == 'USD':
        from app.apps.srm.commercial_models import ProjectCommercial
        db.add(ProjectCommercial(project_id=project_id, customer_id=101, seller_id=1, currency=currency, updated_by=actor.id))
        db.commit()
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    root = '/api/v1/srm/industry'
    def post(path, payload, expected=201):
        response = client.post(root + path, headers=headers, json=payload)
        assert response.status_code == expected, response.text
        return response.json()
    def create(path, **values):
        return post(path, {'request_id': str(uuid4()), 'title': 'Actual site delivery', **values})
    def approve(row, expected=200):
        return post(f'/records/{row["id"]}/transition', {'expected_revision': row['revision'], 'status': 'approved'}, expected)
    boq = create('/boq', project_id=project_id, code='FOUNDATION', unit='m3', quantity='10', unit_rate='1200', tax_rate='5')
    approve(boq)
    measured = create('/measurements', boq_id=boq['id'], quantity='8', measured_on='2026-11-15')
    approved = approve(measured)
    assert approved['approved_by'] == actor.id
    overrun = create('/measurements', boq_id=boq['id'], quantity='3', measured_on='2026-11-15')
    approve(overrun, 409)
    variation = create('/boq', project_id=project_id, code='EXTRA', unit='m3', quantity='3', unit_rate='1300', tax_rate='5', variation_of=boq['id'])
    approve(variation)
    extra = create('/measurements', boq_id=variation['id'], quantity='3', measured_on='2026-11-15')
    approve(extra)
    diary = create('/site-diaries', project_id=project_id, entry_date='2026-11-15', work_done='Foundation and approved extra work', workforce=4)
    assert diary['status'] == 'recorded'
    listed = client.get(root + '/records', headers=headers, params={'kind': 'measurement', 'project_id': project_id})
    assert listed.status_code == 200, listed.text
    assert {row['id']: row['status'] for row in listed.json()['items']} == {measured['id']: 'approved', overrun['id']: 'draft', extra['id']: 'approved'}
    summary = client.get(root + f'/projects/{project_id}/summary', headers=headers)
    assert summary.status_code == 200, summary.text
    assert Decimal(str(summary.json()['approved_scope_value'])) == Decimal('15900.00')
    assert Decimal(str(summary.json()['certified_value'])) == Decimal('13500.00')
    assert Decimal(str(summary.json()['unbilled_certified_value'])) == Decimal('13500.00')
    assert summary.json()['currency'] == currency


@pytest.fixture
def construction(db, scenario):
    actor, branch, _, _ = scenario
    activation = PackActivation(company_id=1, pack_key='construction', pack_version=1, state='active')
    db.add(activation); db.flush()
    context = PackContext(company_id=1, branch_id=branch, activation_id=activation.id,
        pack_key='construction', pack_version=1, state='active')
    db.add(context); db.flush()
    db.add(PackUserGrant(company_id=1, branch_id=branch, context_id=context.id,
        user_id=actor.id, role='project_manager'))
    project = PMSProject(organization_id=1, branch_id=branch, name='Private site',
        project_key=uuid4().hex[:16], manager_user_id=actor.id)
    db.add(project); db.flush()
    db.add(PackRecordOwnership(company_id=1, branch_id=branch, context_id=context.id,
        resource_table='pms_projects', resource_key=str(project.id), source='explicit-test-enrollment'))
    native = db.query(BranchOwnership).filter_by(resource_table='pms_projects', resource_key=str(project.id)).first()
    if native is None:
        db.add(BranchOwnership(company_id=1, branch_id=branch,
            resource_table='pms_projects', resource_key=str(project.id), source='explicit-test-enrollment'))
    db.commit()
    return actor, branch, context.id, project.id


def test_native_project_resource_returns_primitives_preserves_transaction_and_pack(db, construction):
    actor, branch, context_id, project_id = construction
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            connection = db.connection()
            transaction = connection.get_transaction()
            result = project_for_action(db, actor, project_id, 'manage_tasks')
            assert result.id == project_id and result.name == 'Private site' and result.currency == 'INR'
            assert db.info['business_pack_scope'] is scope
            assert transaction.is_active and connection.get_transaction() is transaction
            assert not any(type(row) is PMSProject for row in db.identity_map.values())
            # The resource grants no ordinary ORM access to the private graph.
            with pytest.raises(HTTPException):
                db.query(PMSProject).all()
        finally:
            cleanup()


def test_mutation_authorization_locks_project_in_request_transaction(db, construction):
    from sqlalchemy import event
    if db.bind.dialect.name != 'postgresql':
        pytest.skip('Project row locks require native PostgreSQL')
    actor, branch, context_id, project_id = construction
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        connection = db.connection()
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            if 'FROM pms_projects' in statement:
                statements.append(statement.upper())
        event.listen(connection, 'before_cursor_execute', capture)
        previous = db.info.get('security_write_request')
        try:
            db.info['security_write_request'] = False
            project_for_action(db, actor, project_id, 'browse')
            assert statements and not any('FOR UPDATE' in sql for sql in statements)
            statements.clear()
            db.info['security_write_request'] = True
            transaction = connection.get_transaction()
            project_for_action(db, actor, project_id, 'approve')
            assert any('FOR UPDATE OF PMS_PROJECTS' in sql for sql in statements)
            assert transaction.is_active and connection.get_transaction() is transaction
        finally:
            if previous is None:
                db.info.pop('security_write_request', None)
            else:
                db.info['security_write_request'] = previous
            event.remove(connection, 'before_cursor_execute', capture)
            cleanup()


def test_project_resource_requires_explicit_owner_not_matching_creator(db, construction):
    actor, branch, context_id, project_id = construction
    foreign = PMSProject(organization_id=1, branch_id=branch, name='Same creator is insufficient',
        project_key=uuid4().hex[:16], manager_user_id=actor.id)
    db.add(foreign); db.commit(); foreign_id = foreign.id
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            with pytest.raises(HTTPException) as exc:
                project_for_action(db, actor, foreign_id)
            assert exc.value.status_code == 404
        finally:
            cleanup()


def test_project_resource_unreviewed_action_fails_closed(db, construction):
    actor, branch, context_id, project_id = construction
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            with pytest.raises(HTTPException) as exc:
                project_for_action(db, actor, project_id, 'administer')
            assert exc.value.status_code == 403
        finally:
            cleanup()


def test_native_authorization_resource_rejects_other_sources_and_mutation(db, construction, monkeypatch):
    from app.apps.project_management import access
    from app.models.user import User
    original = access.get_project_for_action

    def inspect_resource(native, *args):
        operations = (
            lambda: native.query(User).first(),
            lambda: native.execute(select(PMSProject.__table__)),
            lambda: native.bulk_insert_mappings(PMSProject, []),
            lambda: native.flush(),
            lambda: native.commit(),
        )
        for operation in operations:
            with pytest.raises(HTTPException) as exc:
                operation()
            assert exc.value.status_code == 403
        return original(native, *args)

    monkeypatch.setattr(access, 'get_project_for_action', inspect_resource)
    actor, branch, context_id, project_id = construction
    with native_writer(db, actor, branch):
        scope = resolve_context(db, actor, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            assert project_for_action(db, actor, project_id).id == project_id
        finally:
            cleanup()


def test_actual_http_boq_create_replay_list_and_approve(client, db, construction, catalog):
    actor, branch, context_id, project_id = construction
    headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    body = {'request_id': str(uuid4()), 'title': 'Foundation concrete', 'project_id': project_id,
        'code': 'C-01', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1200', 'tax_rate': '18'}
    root = '/api/v1/srm/industry'
    created = client.post(root + '/boq', headers=headers, json=body)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row['status'] == 'draft' and row['data']['currency'] == 'INR'
    replay = client.post(root + '/boq', headers=headers, json=body)
    assert replay.status_code == 201 and replay.json()['id'] == row['id'], replay.text
    altered = client.post(root + '/boq', headers=headers, json={**body, 'quantity': '11'})
    assert altered.status_code == 409, altered.text
    listed = client.get(root + '/records', headers=headers, params={'kind': 'boq', 'project_id': project_id})
    assert listed.status_code == 200 and [item['id'] for item in listed.json()['items']] == [row['id']], listed.text
    picker = client.get(root + '/project-options', headers=headers)
    assert picker.status_code == 200 and picker.json()['items'] == [{'id': project_id, 'name': 'Private site'}], picker.text
    approved = client.post(root + f'/records/{row["id"]}/transition', headers=headers,
        json={'expected_revision': 1, 'status': 'approved'})
    assert approved.status_code == 200 and approved.json()['revision'] == 2, approved.text
    stale = client.post(root + f'/records/{row["id"]}/transition', headers=headers,
        json={'expected_revision': 1, 'status': 'rejected', 'reason': 'stale'})
    assert stale.status_code == 409, stale.text


@pytest.mark.parametrize('pack,role', [('hospital', 'doctor'), ('restaurant', 'chef')])
def test_specialists_cannot_create_construction_boq(client, db, construction, catalog, pack, role):
    actor, branch, _, project_id = construction
    from tests.test_business_pack_http_integration import grant
    context, _ = grant(db, actor, branch, pack, role)
    response = client.post('/api/v1/srm/industry/boq',
        headers={**catalog[0], 'X-Suite-Pack-Context': str(context.id)},
        json={'request_id': str(uuid4()), 'title': 'Not their workflow', 'project_id': project_id,
            'code': 'X', 'unit': 'm', 'quantity': '1', 'unit_rate': '10'})
    assert response.status_code == 403, response.text


def test_pack_manager_cannot_override_native_project_module_denial(client, db, construction):
    from tests.test_business_pack_http_integration import native_actor, grant
    actor, branch, context_id, project_id = construction
    headers, limited = native_actor(db, branch)
    context = db.get(PackContext, context_id)
    grant(db, limited, branch, 'construction', 'project_manager', context)
    response = client.post('/api/v1/srm/industry/boq',
        headers={**headers, 'X-Suite-Pack-Context': str(context_id)},
        json={'request_id': str(uuid4()), 'title': 'Native access denied', 'project_id': project_id,
            'code': 'DENIED', 'unit': 'm', 'quantity': '1', 'unit_rate': '10'})
    assert response.status_code == 403, response.text


def test_context_isolation_on_owned_project_with_same_native_actor(client, db, construction, catalog):
    from tests.test_business_pack_http_integration import grant
    actor, branch, context_id, project_id = construction
    context, _ = grant(db, actor, branch, 'retail', 'store_manager')
    response = client.get('/api/v1/srm/industry/records',
        headers={**catalog[0], 'X-Suite-Pack-Context': str(context.id)},
        params={'kind': 'boq', 'project_id': project_id})
    assert response.status_code == 403, response.text


def test_independent_native_project_member_approves_boq(client, db, construction, catalog):
    from app.access.models import AccessPolicy
    from tests.test_business_pack_http_integration import native_actor, grant
    actor, branch, context_id, project_id = construction
    owner_headers = {**catalog[0], 'X-Suite-Pack-Context': str(context_id)}
    root = '/api/v1/srm/industry'
    created = client.post(root + '/boq', headers=owner_headers,
        json={'request_id': str(uuid4()), 'title': 'Independent review', 'project_id': project_id,
            'code': 'REVIEW', 'unit': 'm3', 'quantity': '10', 'unit_rate': '1200'})
    assert created.status_code == 201, created.text
    headers, reviewer = native_actor(db, branch)
    grant(db, reviewer, branch, 'construction', 'project_manager', db.get(PackContext, context_id))
    policy = db.query(AccessPolicy).filter_by(company_id=1, user_id=reviewer.id).one()
    policy.grants = {**policy.grants, 'project_management': {'enabled': True,
        'permissions': ['pms_view'], 'actions': ['view'], 'scope': 'organization'}}
    db.add(PMSProjectMember(project_id=project_id, user_id=reviewer.id, role='Manager'))
    db.commit()
    with native_writer(db, reviewer, branch):
        assert db.query(PMSProject).filter_by(id=project_id).first() is not None, 'Native project hidden'
        from app.apps.srm.industry_models import IndustryRecord
        assert db.query(IndustryRecord).filter_by(id=created.json()['id']).first() is not None, 'Native BOQ hidden'
    response = client.post(root + f'/records/{created.json()["id"]}/transition',
        headers={**headers, 'X-Suite-Pack-Context': str(context_id)},
        json={'expected_revision': 1, 'status': 'approved'})
    assert response.status_code == 200, response.text
    assert response.json()['approved_by'] == reviewer.id
    assert response.json()['created_by'] == actor.id and reviewer.id != actor.id
    # Same native SRM scope cannot read the parent-backed record without a
    # genuine current project certificate. A later revoked membership cannot
    # reuse that certificate even within the same Session and pack scope.
    from app.apps.srm.industry_models import IndustryRecord
    from sqlalchemy.exc import StatementError
    with native_writer(db, reviewer, branch):
        scope = resolve_context(db, reviewer, db.info['branch_context'], context_id)
        cleanup = install(db, scope, policy=native_srm_policy('construction').policy)
        try:
            row_id = created.json()['id']
            assert db.query(IndustryRecord).filter_by(id=row_id).first() is None
            project_for_action(db, reviewer, project_id)
            assert db.query(IndustryRecord).filter_by(id=row_id).first() is not None
            membership = PMSProjectMember.__table__
            db.connection().execute(membership.delete().where(
                membership.c.project_id == project_id, membership.c.user_id == reviewer.id))
            with pytest.raises((HTTPException, StatementError)) as error:
                db.query(IndustryRecord).filter_by(id=row_id).first()
            underlying = getattr(error.value, 'orig', error.value)
            assert isinstance(underlying, HTTPException) and underlying.status_code == 403
        finally:
            cleanup()
