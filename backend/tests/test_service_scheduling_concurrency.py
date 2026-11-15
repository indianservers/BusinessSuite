"""Hospital/Salon races use independent committed PostgreSQL request sessions."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.apps.srm.industry_models import IndustryRecord
from app.apps.srm.models import SRMInvoice, SRMPOSSession, SRMReceipt, SRMReceiptAllocation, SRMSalesOrder
from app.apps.srm.service_checkout import save_eligibility, save_policy
from app.apps.srm.service_checkout_models import POSCheckoutPayment, POSServiceCheckout, POSServiceOccurrence
from app.apps.srm.service_checkout_schemas import EligibilityInput, PolicyInput
from app.business_packs.access import resolve_context
from app.business_packs.boundary import install
from app.business_packs.models import PackMasterAvailability
from app.business_packs.native_policy import native_srm_policy
from app.models.employee import Employee
from app.models.company import Branch
from tests.srm_test_utils import seed_invoice_parties
from tests.test_business_pack_http_integration import grant, native_actor
from tests.test_pms_workflow_postgresql import live, race
from tests.test_srm_native_transaction_operations import native_writer


BASE = '/api/v1/srm/service-checkout'
BUSY_DETAIL = {'detail': 'Database operation could not complete. Check its status before retrying.'}


def _race_with_exact_busy_retry(case, path, payloads, allowed_statuses):
    """A native bounded-busy response must recover to the original domain result.

    The existing race helper joins every future within its unchanged 20-second
    budget. Only then may a known winner's competing request retry its original
    idempotency key. The entire race plus the single advised retry must also fit
    within 20 seconds; this does not forgive a slow or unsuccessful winner.
    """
    started = monotonic()
    originals = tuple(deepcopy(payload) for payload in payloads)

    def post_exact(body):
        response = case.live.client.post(path, headers=case.headers, json=deepcopy(body))
        finished = monotonic()
        assert json.loads(response.request.content) == body, 'The original request/body/key must be retained'
        return response, finished

    completed = race(*(lambda body=body: post_exact(body) for body in originals))
    results = [response for response, _ in completed]
    assert monotonic() - started <= 20, 'The original race winner exceeded the existing workflow budget'
    assert all(response.status_code in {*allowed_statuses, 503} for response in results), [response.text for response in results]
    assert any(response.status_code == 201 for response in results), 'A committed 201 winner must complete before any retry'
    for index, (response, finished) in enumerate(completed):
        if response.status_code != 503:
            continue
        assert response.headers.get('Retry-After') == '5', response.headers
        assert response.json() == BUSY_DETAIL, response.text
        remaining = max(0, 5 - (monotonic() - finished))
        if remaining:
            sleep(remaining)
        assert monotonic() - started < 20, 'The advised retry must remain within the existing workflow budget'
        results[index], _ = post_exact(originals[index])
        assert results[index].status_code in allowed_statuses, results[index].text
    assert tuple(payloads) == originals, 'Retry must not mutate request IDs, payment keys or request details'
    assert monotonic() - started <= 20, 'The entire race and retry exceeded the existing 20-second workflow budget'
    return results


@pytest.fixture(params=['hospital', 'salon'])
def service_case(live, request):
    """Commit real canonical masters, then private operational pack resources."""
    pack = request.param
    with live.factory() as db:
        branch = db.query(Branch).filter_by(company_id=1, is_active=True).order_by(Branch.id).first().id
    response = live.client.post('/api/v1/srm/inventory/items', headers={**live.oh, 'X-Suite-Branch': str(branch)}, json={
        'sku': 'SERVICE-RACE-' + uuid4().hex, 'item_name': 'Synthetic scheduling service',
        'product_type': 'service', 'track_inventory': False, 'sales_rate': 100, 'gst_rate': 18,
    })
    assert response.status_code == 201, response.text
    product = response.json()['id']
    with live.factory() as db:
        seed_invoice_parties(db)
        headers, actor = native_actor(db, branch)
        with native_writer(db, actor, branch):
            employee = Employee(employee_id='RACE-' + uuid4().hex, first_name='Scheduling', last_name='Specialist',
                date_of_joining=datetime.now(timezone.utc).date(), status='Active', branch_id=branch)
            db.add(employee); db.commit()
            employee_id = employee.id
        context, _ = grant(db, actor, branch, pack, 'hospital_manager' if pack == 'hospital' else 'salon_manager')
        for table, ident in [('employees', employee_id), ('crm_companies', 101), ('srm_products', product)]:
            db.add(PackMasterAvailability(company_id=1, branch_id=branch, context_id=context.id,
                resource_table=table, resource_key=str(ident), active=True))
        db.commit()
        with native_writer(db, actor, branch):
            scope = resolve_context(db, actor, db.info['branch_context'], context.id)
            cleanup = install(db, scope, policy=native_srm_policy(pack).policy)
            try:
                register = SRMPOSSession(organization_id=1, session_number='SERVICE-RACE-' + uuid4().hex,
                    status='open', cashier_user_id=actor.id, created_by=actor.id)
                providers = [IndustryRecord(organization_id=1, branch_id=branch, kind='resource',
                    title='Synthetic provider alias ' + str(index), status='active', request_id=str(uuid4()), created_by=actor.id,
                    data={'resource_type': 'doctor' if pack == 'hospital' else 'stylist', 'employee_id': employee_id,
                        'user_id': None, 'timezone': 'UTC', 'weekdays': list(range(7)), 'opens': '00:00:00', 'closes': '23:59:00'})
                    for index in range(2)]
                db.add_all([register, *providers]); db.commit()
                register_id = register.id
                policy = save_policy(PolicyInput(service_product_id=product, default_duration_minutes=30,
                    min_duration_minutes=5, max_duration_minutes=120), db, actor)
                choices = []
                for provider in providers:
                    eligibility = save_eligibility(EligibilityInput(policy_id=policy['id'],
                        expected_policy_revision=policy['revision'], provider_resource_id=provider.id, employee_id=employee_id), db, actor)
                    choices.append({'policy_id': policy['id'], 'expected_policy_revision': policy['revision'],
                        'eligibility_id': eligibility['id'], 'expected_eligibility_revision': eligibility['revision'],
                        'provider_resource_id': provider.id, 'employee_id': employee_id})
            finally:
                cleanup()
        headers = {**headers, 'X-Suite-Pack-Context': str(context.id)}
    starts = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)

    def payload(alias=0, paid=False):
        return {'request_id': str(uuid4()), 'customer_id': 101, 'pos_session_id': register_id,
            'lines': [{'client_line_key': str(uuid4()), 'line_kind': 'booked_service', 'product_id': product,
                'booking': {**choices[alias], 'starts_at': starts.isoformat(), 'duration_minutes': 30}}],
            'payments': [{'payment_key': str(uuid4()), 'method': 'cash', 'amount': '50'}] if paid else []}

    return SimpleNamespace(live=live, headers=headers, payload=payload)


@pytest.mark.parametrize('second_alias', [0, 1], ids=['same-resource', 'same-employee-alias'])
def test_overlapping_service_checkouts_reserve_employee_only_once(service_case, second_alias):
    case = service_case
    first, second = case.payload(), case.payload(alias=second_alias)
    results = _race_with_exact_busy_retry(case, BASE, (first, second), {201, 409})
    assert sorted(response.status_code for response in results) == [201, 409], [response.text for response in results]
    with case.live.factory() as db:
        assert db.query(POSServiceCheckout).count() == db.query(POSServiceOccurrence).count() == 1
        assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == 1
        assert db.query(IndustryRecord).filter_by(kind='appointment').count() == 1
        assert db.query(SRMReceipt).count() == db.query(POSCheckoutPayment).count() == 0


def test_concurrent_exact_service_checkout_replay_creates_one_native_graph(service_case):
    case = service_case
    payload = case.payload(paid=True)
    results = _race_with_exact_busy_retry(case, BASE, (payload, payload), {201})
    assert [response.status_code for response in results] == [201, 201], [response.text for response in results]
    assert results[0].json() == results[1].json()
    with case.live.factory() as db:
        assert db.query(POSServiceCheckout).count() == db.query(POSServiceOccurrence).count() == 1
        assert db.query(SRMSalesOrder).count() == db.query(SRMInvoice).count() == 1
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == db.query(POSCheckoutPayment).count() == 1
        invoice = db.query(SRMInvoice).one()
        assert invoice.total_amount == Decimal('118') and invoice.paid_amount == Decimal('50') and invoice.balance_amount == Decimal('68')


def test_concurrent_duplicate_later_payment_allocates_native_receipt_once(service_case):
    case = service_case
    response = case.live.client.post(BASE, headers=case.headers, json=case.payload())
    assert response.status_code == 201, response.text
    checkout = response.json()
    payment = {'expected_revision': checkout['revision'],
        'payment': {'payment_key': str(uuid4()), 'method': 'cash', 'amount': '118'}}
    path = BASE + '/' + str(checkout['id']) + '/payments'
    results = _race_with_exact_busy_retry(case, path, (payment, payment), {201})
    assert [response.status_code for response in results] == [201, 201], [response.text for response in results]
    assert results[0].json() == results[1].json()
    with case.live.factory() as db:
        assert db.query(POSServiceCheckout).count() == db.query(POSServiceOccurrence).count() == 1
        assert db.query(SRMInvoice).count() == db.query(SRMSalesOrder).count() == 1
        assert db.query(SRMReceipt).count() == db.query(SRMReceiptAllocation).count() == db.query(POSCheckoutPayment).count() == 1
        invoice = db.query(SRMInvoice).one()
        assert invoice.total_amount == invoice.paid_amount == Decimal('118') and invoice.balance_amount == 0
