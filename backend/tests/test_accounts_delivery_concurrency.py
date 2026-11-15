"""Committed native Accounts races over independent PostgreSQL request sessions.

These tests deliberately use the existing live fixture and its bounded race
helper. SQLite execution skips rather than simulating company writer locks.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4
import json
from threading import Event, get_ident
from time import monotonic, sleep

from sqlalchemy import event

from app.models.employee import Employee
from app.models.user import User
from app.apps.srm.models import (
    SRMInvoice, SRMInvoiceDraft, SRMInvoiceLine, SRMReceipt, SRMReceiptAllocation,
)
from app.business_packs.models import PackContext, PackMasterAvailability
from app.business_packs.accounting_firm.models import AccountsPeriod, AccountsCommand
from tests.test_pms_workflow_postgresql import live, race
from tests.test_accounts_engagements_concurrency import configured as native_configured
from tests.test_business_pack_http_integration import native_actor, grant
from tests.test_srm_native_transaction_operations import native_writer


BASE = '/api/v1/srm/accounts/periods'


def configured(live):
    headers, manager_id = native_configured(live)
    branch = int(headers['X-Suite-Branch'])
    context_id = int(headers['X-Suite-Pack-Context'])
    people = {}
    with live.factory() as db:
        manager = db.get(User, manager_id)
        context = db.get(PackContext, context_id)
        for role in ('preparer', 'reviewer', 'billing_officer'):
            role_headers, user = native_actor(db, branch)
            grant(db, user, branch, 'accounting_firm', role, context)
            person = {'headers': role_headers | {'X-Suite-Pack-Context': str(context_id)}, 'user_id': user.id}
            if role in {'preparer', 'reviewer'}:
                with native_writer(db, manager, branch):
                    employee = Employee(employee_id='AC-RACE-' + uuid4().hex,
                        first_name=role, last_name='Native race', user_id=user.id,
                        branch_id=branch, status='Active', date_of_joining=date(2025, 1, 1))
                    db.add(employee)
                    db.commit()
                    employee_id = employee.id
                db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context_id,
                    resource_table='employees', resource_key=str(employee_id), active=True))
                db.commit()
                person['employee_id'] = employee_id
            people[role] = person
    response = live.client.post('/api/v1/srm/accounts/engagements', headers=headers, json={
        'request_key': str(uuid4()), 'client_id': 101, 'name': 'Native raced Accounts service'})
    assert response.status_code == 201, response.text
    return {'headers': headers, 'engagement_id': response.json()['id'], **people}


def body(case, *, occurrences=1):
    return {'request_key': str(uuid4()), 'engagement_id': case['engagement_id'], 'client_id': 101,
        'starts_on': '2026-01-01', 'ends_on': '2026-01-31', 'due_on': '2026-02-10',
        'title': 'Native client accounts period', 'preparer_employee_id': case['preparer']['employee_id'],
        'reviewer_employee_id': case['reviewer']['employee_id'], 'occurrences': occurrences}


def post(live, headers, path, data, *, method='post', status=200):
    response = getattr(live.client, method)(BASE + path, headers=headers, json=data)
    assert response.status_code == status, response.text
    return response.json()


def create(live, case):
    return post(live, case['headers'], '', body(case), status=201)


def revision(row):
    return {'request_key': str(uuid4()), 'expected_revision': row['revision']}


def prepared(live, case):
    row = create(live, case)
    return post(live, case['preparer']['headers'], f"/{row['id']}/work", revision(row) | {
        'summary': 'Actual native reconciled client work'}, method='put')


def approved(live, case):
    row = prepared(live, case)
    row = post(live, case['preparer']['headers'], f"/{row['id']}/submit", revision(row))
    return post(live, case['reviewer']['headers'], f"/{row['id']}/approve", revision(row) | {
        'expected_work_revision': row['work_revision'], 'reason': 'Independent native review'})


def issued(live, case):
    row = approved(live, case)
    invoice = post(live, case['headers'], f"/{row['id']}/invoice", revision(row) | {
        'expected_work_revision': row['work_revision'], 'amount': '1500.00'}, status=201)
    response = live.client.post(f"/api/v1/srm/invoices/{invoice['invoice_id']}/approve", headers=case['headers'])
    assert response.status_code == 200, response.text
    return row, invoice['invoice_id']


def test_exact_parallel_recurring_period_command_creates_one_series(live):
    case = configured(live)
    data = body(case, occurrences=3)
    call = lambda: live.client.post(BASE, headers=case['headers'], json=data)
    responses = race(call, call)
    assert [response.status_code for response in responses] == [201, 201], [response.text for response in responses]
    assert responses[0].json() == responses[1].json()
    assert len(responses[0].json()['periods']) == 3
    with live.factory() as db:
        assert db.query(AccountsPeriod).count() == 3
        assert db.query(AccountsCommand).filter_by(action='create').count() == 4


def test_parallel_same_uuid_different_series_payload_cannot_duplicate(live):
    case = configured(live)
    data = body(case, occurrences=3)
    responses = race(lambda: live.client.post(BASE, headers=case['headers'], json=data),
        lambda: live.client.post(BASE, headers=case['headers'], json=data | {'occurrences': 4}))
    assert sorted(response.status_code for response in responses) == [201, 409], [response.text for response in responses]
    accepted = next(response.json() for response in responses if response.status_code == 201)
    count = len(accepted['periods'])
    assert count in {3, 4}
    with live.factory() as db:
        assert db.query(AccountsPeriod).count() == count
        assert db.query(AccountsCommand).filter_by(action='create').count() == count + 1


def test_parallel_exact_preparer_submission_has_one_immutable_history(live):
    case = configured(live)
    row = prepared(live, case)
    data = revision(row)
    call = lambda: live.client.post(BASE + f"/{row['id']}/submit", headers=case['preparer']['headers'], json=data)
    responses = race(call, call)
    assert [response.status_code for response in responses] == [200, 200], [response.text for response in responses]
    assert responses[0].json() == responses[1].json()
    with live.factory() as db:
        current = db.get(AccountsPeriod, row['id'])
        assert current.state == 'submitted' and current.revision == row['revision'] + 1
        assert db.query(AccountsCommand).filter_by(action='submit', period_id=row['id']).count() == 1


def test_parallel_new_submission_keys_at_same_revision_reject_stale_writer(live):
    case = configured(live)
    row = prepared(live, case)
    data = revision(row)
    responses = race(lambda: live.client.post(BASE + f"/{row['id']}/submit", headers=case['preparer']['headers'], json=data),
        lambda: live.client.post(BASE + f"/{row['id']}/submit", headers=case['preparer']['headers'],
            json=data | {'request_key': str(uuid4())}))
    assert sorted(response.status_code for response in responses) == [200, 409], [response.text for response in responses]
    with live.factory() as db:
        assert db.query(AccountsCommand).filter_by(action='submit', period_id=row['id']).count() == 1


def test_parallel_exact_approved_period_invoice_mints_one_native_source(live):
    case = configured(live)
    row = approved(live, case)
    data = revision(row) | {'expected_work_revision': row['work_revision'], 'amount': '1500.00'}
    call = lambda: live.client.post(BASE + f"/{row['id']}/invoice", headers=case['headers'], json=data)
    responses = race(call, call)
    assert [response.status_code for response in responses] == [201, 201], [response.text for response in responses]
    assert responses[0].json() == responses[1].json()
    with live.factory() as db:
        assert db.query(SRMInvoice).count() == db.query(SRMInvoiceDraft).count() == db.query(SRMInvoiceLine).count() == 1
        assert db.query(AccountsCommand).filter_by(action='invoice', period_id=row['id']).count() == 1
        source = db.query(SRMInvoiceLine).one()
        assert source.source_type == 'accounts_period' and source.source_id == row['id']


def test_parallel_exact_collection_retry_has_one_canonical_receipt(live, monkeypatch):
    from app.core import company_writer
    from app.apps.srm.models import ReceiptContext, SRMRevenueEvent, SRMAuditLog

    case = configured(live)
    row, invoice_id = issued(live, case)
    data = {'request_id': str(uuid4()), 'amount': '500.00', 'payment_method': 'bank_transfer', 'reference': 'Native raced collection'}
    started = monotonic()
    diagnostic = {'writer_calls': [], 'database_errors': [], 'http_calls': []}
    original_lock = company_writer.lock_company_writer

    def database_error(context):
        original = context.original_exception
        diagnostic['database_errors'].append({
            'at_seconds': monotonic() - started, 'thread_id': get_ident(),
            'sqlstate': getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None),
            'exception_type': type(original).__name__,
            # Statement text only: never include bound parameters or exception text.
            'statement': context.statement,
        })

    def measured_lock(db, company_id):
        connection = db.connection()
        driver = connection.connection.driver_connection
        info = getattr(driver, 'info', None)
        backend_pid = getattr(info, 'backend_pid', None)
        if backend_pid is None and hasattr(driver, 'get_backend_pid'):
            backend_pid = driver.get_backend_pid()
        entry = {'session_id': id(db), 'backend_pid': backend_pid, 'thread_id': get_ident(),
            'before_seconds': monotonic() - started}
        diagnostic['writer_calls'].append(entry)
        try:
            result = original_lock(db, company_id)
            entry['outcome'] = 'acquired'
            return result
        except BaseException as failure:
            entry['outcome'] = type(failure).__name__
            raise
        finally:
            entry['after_seconds'] = monotonic() - started
            entry['wait_seconds'] = entry['after_seconds'] - entry['before_seconds']

    def call():
        before = monotonic()
        response = live.client.post(BASE + f"/{row['id']}/payments", headers=case['billing_officer']['headers'], json=data)
        diagnostic['http_calls'].append({'thread_id': get_ident(), 'before_seconds': before - started,
            'after_seconds': monotonic() - started, 'duration_seconds': monotonic() - before,
            'status': response.status_code, 'retry_after': response.headers.get('Retry-After')})
        return response

    event.listen(live.engine, 'handle_error', database_error)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(company_writer, 'lock_company_writer', measured_lock)
            responses = race(call, call)
    finally:
        event.remove(live.engine, 'handle_error', database_error)
    # Read committed canonical results before the original strict status check.
    with live.factory() as db:
        invoice = db.get(SRMInvoice, invoice_id)
        diagnostic['canonical'] = {
            'receipt_count': db.query(SRMReceipt).count(),
            'allocation_count': db.query(SRMReceiptAllocation).filter_by(invoice_id=invoice_id).count(),
            'receipt_context_count': db.query(ReceiptContext).filter_by(invoice_id=invoice_id).count(),
            'cash_revenue_count': db.query(SRMRevenueEvent).filter_by(invoice_id=invoice_id, event_type='cash_collected').count(),
            'payment_audit_count': db.query(SRMAuditLog).filter_by(entity_type='receipt', action='payment_applied').count(),
            'paid_amount': str(invoice.paid_amount), 'balance_amount': str(invoice.balance_amount),
        }
    diagnostic['initial_statuses'] = [response.status_code for response in responses]
    if diagnostic['initial_statuses'] != [201, 201]:
        try:
            assert sorted(diagnostic['initial_statuses']) == [201, 503], diagnostic
            winner = next(response for response in responses if response.status_code == 201)
            blocked = next(response for response in responses if response.status_code == 503)
            assert blocked.headers.get('Retry-After') == '5'
            errors = diagnostic['database_errors']
            assert len(errors) == 1 and errors[0]['sqlstate'] == '55P03', errors
            assert 'pg_advisory_xact_lock' in errors[0]['statement'], errors
            waits = [entry for entry in diagnostic['writer_calls'] if entry['outcome'] != 'acquired']
            assert len(waits) == 1 and waits[0]['wait_seconds'] >= 4.5, waits
            acquired = [entry for entry in diagnostic['writer_calls'] if entry['outcome'] == 'acquired']
            assert any(entry['session_id'] != waits[0]['session_id'] and
                entry['backend_pid'] != waits[0]['backend_pid'] for entry in acquired), diagnostic['writer_calls']
            canonical = diagnostic['canonical']
            assert all(canonical[key] == 1 for key in (
                'receipt_count', 'allocation_count', 'receipt_context_count', 'cash_revenue_count', 'payment_audit_count')), canonical
            assert Decimal(canonical['paid_amount']) == Decimal('500.00'), canonical
            assert Decimal(canonical['balance_amount']) == Decimal('1000.00'), canonical
            completion = next(entry['after_seconds'] for entry in diagnostic['http_calls'] if entry['status'] == 503)
            # Respect this actual response's native advice within the original
            # race budget; never turn unknown 503 failures into generic retries.
            retry_at = started + completion + int(blocked.headers['Retry-After'])
            assert retry_at < started + 20, diagnostic
            remaining_advice = retry_at - monotonic()
            if remaining_advice > 0:
                sleep(remaining_advice)
            assert monotonic() - started < 20, diagnostic
            retry = call()  # Exact same URI/body/UUID/authorized actor.
            assert retry.status_code == 201, retry.text
            assert retry.json() == winner.json()
            with live.factory() as db:
                invoice = db.get(SRMInvoice, invoice_id)
                diagnostic['after_same_key_retry'] = {
                    'receipt_count': db.query(SRMReceipt).count(),
                    'allocation_count': db.query(SRMReceiptAllocation).filter_by(invoice_id=invoice_id).count(),
                    'receipt_context_count': db.query(ReceiptContext).filter_by(invoice_id=invoice_id).count(),
                    'cash_revenue_count': db.query(SRMRevenueEvent).filter_by(invoice_id=invoice_id, event_type='cash_collected').count(),
                    'payment_audit_count': db.query(SRMAuditLog).filter_by(entity_type='receipt', action='payment_applied').count(),
                    'paid_amount': str(invoice.paid_amount), 'balance_amount': str(invoice.balance_amount),
                }
            assert diagnostic['after_same_key_retry'] == canonical
            diagnostic['elapsed_seconds'] = monotonic() - started
            assert diagnostic['elapsed_seconds'] <= 20, diagnostic
            responses = [retry if response.status_code == 503 else response for response in responses]
        finally:
            print('ACCOUNTS_COLLECTION_RACE_DIAGNOSTIC=' + json.dumps(diagnostic, sort_keys=True))
    else:
        print('ACCOUNTS_COLLECTION_RACE_DIAGNOSTIC=' + json.dumps(diagnostic, sort_keys=True))
    assert [response.status_code for response in responses] == [201, 201], [response.text for response in responses]
    assert responses[0].json() == responses[1].json()
    with live.factory() as db:
        invoice = db.get(SRMInvoice, invoice_id)
        assert invoice.paid_amount == Decimal('500.00') and invoice.balance_amount == Decimal('1000.00')
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 1


def test_native_busy_collection_rolls_back_and_same_key_retry_reuses_receipt(live, monkeypatch):
    from app.core import company_writer
    from app.apps.srm import payments
    from app.apps.srm.models import ReceiptContext, SRMRevenueEvent, SRMAuditLog

    case = configured(live)
    row, invoice_id = issued(live, case)
    path = BASE + f"/{row['id']}/payments"
    headers = case['billing_officer']['headers']
    data = {'request_id': str(uuid4()), 'amount': '500.00', 'payment_method': 'bank_transfer',
        'reference': 'Native busy same-key retry'}
    owner_ready, release_owner = Event(), Event()
    started = monotonic()
    diagnostic = {'writer_calls': [], 'database_errors': [], 'http_calls': []}
    original_lock = company_writer.lock_company_writer
    original_payment = payments.record_payment_operation

    def counts():
        with live.factory() as db:
            invoice = db.get(SRMInvoice, invoice_id)
            return {
                'receipt_count': db.query(SRMReceipt).count(),
                'allocation_count': db.query(SRMReceiptAllocation).filter_by(invoice_id=invoice_id).count(),
                'receipt_context_count': db.query(ReceiptContext).filter_by(invoice_id=invoice_id).count(),
                'cash_revenue_count': db.query(SRMRevenueEvent).filter_by(invoice_id=invoice_id, event_type='cash_collected').count(),
                'payment_audit_count': db.query(SRMAuditLog).filter_by(entity_type='receipt', action='payment_applied').count(),
                'paid_amount': str(invoice.paid_amount), 'balance_amount': str(invoice.balance_amount),
            }

    def database_error(context):
        original = context.original_exception
        diagnostic['database_errors'].append({
            'at_seconds': monotonic() - started, 'thread_id': get_ident(),
            'sqlstate': getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None),
            'exception_type': type(original).__name__, 'statement': context.statement,
        })
        if owner_ready.is_set() and not release_owner.is_set():
            # Snapshot before allowing the genuine owner to commit. Release at
            # the DB error, rather than waiting for HTTP error/audit completion,
            # which may itself need the same company's native writer lock.
            try:
                diagnostic['before_owner_commit'] = counts()
            finally:
                release_owner.set()

    def measured_lock(db, company_id):
        connection = db.connection()
        driver = connection.connection.driver_connection
        backend_pid = getattr(getattr(driver, 'info', None), 'backend_pid', None)
        if backend_pid is None and hasattr(driver, 'get_backend_pid'):
            backend_pid = driver.get_backend_pid()
        entry = {'session_id': id(db), 'backend_pid': backend_pid, 'thread_id': get_ident(),
            'before_seconds': monotonic() - started}
        diagnostic['writer_calls'].append(entry)
        try:
            result = original_lock(db, company_id)
            entry['outcome'] = 'acquired'
            return result
        except BaseException as failure:
            entry['outcome'] = type(failure).__name__
            raise
        finally:
            entry['after_seconds'] = monotonic() - started
            entry['wait_seconds'] = entry['after_seconds'] - entry['before_seconds']

    def hold_native_payment(*args, **kwargs):
        assert kwargs.get('commit') is False
        result = original_payment(*args, **kwargs)
        # Genuine native payment writes exist in the owner's transaction, whose
        # actual company writer lock is still held; do not commit or fake them.
        assert not owner_ready.is_set()
        diagnostic['owner_ready_seconds'] = monotonic() - started
        owner_ready.set()
        assert release_owner.wait(timeout=10), 'Contending request did not release the native owner'
        return result

    def request(label):
        before = monotonic()
        response = live.client.post(path, headers=headers, json=data)
        diagnostic['http_calls'].append({'label': label, 'thread_id': get_ident(),
            'before_seconds': before - started, 'after_seconds': monotonic() - started,
            'duration_seconds': monotonic() - before, 'status': response.status_code,
            'retry_after': response.headers.get('Retry-After')})
        return response

    def contender():
        try:
            assert owner_ready.wait(timeout=10), 'Native owner did not reach its uncommitted payment'
            response = request('contender')
            return response
        finally:
            release_owner.set()

    event.listen(live.engine, 'handle_error', database_error)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(company_writer, 'lock_company_writer', measured_lock)
            patch.setattr(payments, 'record_payment_operation', hold_native_payment)
            owner, blocked = race(lambda: request('owner'), contender)
        diagnostic['after_owner_commit'] = counts()
        assert owner.status_code == 201, owner.text
        assert blocked.status_code == 503, blocked.text
        assert blocked.headers.get('Retry-After') == '5'
        errors = diagnostic['database_errors']
        assert len(errors) == 1 and errors[0]['sqlstate'] == '55P03', errors
        assert 'pg_advisory_xact_lock' in errors[0]['statement'], errors
        waits = [entry for entry in diagnostic['writer_calls'] if entry['outcome'] != 'acquired']
        assert len(waits) == 1 and waits[0]['wait_seconds'] >= 4.5, waits
        acquired = [entry for entry in diagnostic['writer_calls'] if entry['outcome'] == 'acquired']
        assert any(entry['session_id'] != waits[0]['session_id'] and
            entry['backend_pid'] != waits[0]['backend_pid'] for entry in acquired), diagnostic['writer_calls']
        before = diagnostic['before_owner_commit']
        assert all(before[key] == 0 for key in (
            'receipt_count', 'allocation_count', 'receipt_context_count', 'cash_revenue_count', 'payment_audit_count')), before
        assert Decimal(before['paid_amount']) == 0 and Decimal(before['balance_amount']) == Decimal('1500.00'), before
        # Retry the identical native command only after the owner is known 201.
        retry = request('same_key_retry')
        assert retry.status_code == 201, retry.text
        assert retry.json() == owner.json()
        diagnostic['after_same_key_retry'] = counts()
        for stage in ('after_owner_commit', 'after_same_key_retry'):
            current = diagnostic[stage]
            assert all(current[key] == 1 for key in (
                'receipt_count', 'allocation_count', 'receipt_context_count', 'cash_revenue_count', 'payment_audit_count')), current
            assert Decimal(current['paid_amount']) == Decimal('500.00'), current
            assert Decimal(current['balance_amount']) == Decimal('1000.00'), current
    finally:
        release_owner.set()
        event.remove(live.engine, 'handle_error', database_error)
        print('ACCOUNTS_NATIVE_BUSY_COLLECTION_DIAGNOSTIC=' + json.dumps(diagnostic, sort_keys=True))


def test_parallel_competing_collections_never_overpay_remaining_balance(live):
    case = configured(live)
    row, invoice_id = issued(live, case)
    data = {'request_id': str(uuid4()), 'amount': '1000.00', 'payment_method': 'bank_transfer', 'reference': 'Native competing collection'}
    responses = race(lambda: live.client.post(BASE + f"/{row['id']}/payments", headers=case['billing_officer']['headers'], json=data),
        lambda: live.client.post(BASE + f"/{row['id']}/payments", headers=case['billing_officer']['headers'],
            json=data | {'request_id': str(uuid4())}))
    assert sorted(response.status_code for response in responses) == [201, 422], [response.text for response in responses]
    with live.factory() as db:
        invoice = db.get(SRMInvoice, invoice_id)
        assert invoice.paid_amount == Decimal('1000.00') and invoice.balance_amount == Decimal('500.00')
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 1
    final = {'request_id': str(uuid4()), 'amount': '500.00', 'payment_method': 'bank_transfer'}
    post(live, case['billing_officer']['headers'], f"/{row['id']}/payments", final, status=201)
    post(live, case['billing_officer']['headers'], f"/{row['id']}/payments", final | {
        'request_id': str(uuid4()), 'amount': '0.01'}, status=422)
    with live.factory() as db:
        invoice = db.get(SRMInvoice, invoice_id)
        assert invoice.paid_amount == invoice.total_amount == Decimal('1500.00') and invoice.balance_amount == 0
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == 2
