from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from app.shared.follow_ups import CreateFollowUp, Schedule, Change, FollowUp, FollowUpActivity, FollowUpReminder, create, change, dispatch, statistics, cancel_for_order
from app.models.user import User
from app.models.notification import Notification
from app.apps.crm.models import CRMCompany
from app.apps.srm.models import SRMProduct

@pytest.fixture
def setup(db):
    u = User(email='follow-up@example.com', hashed_password='unused', is_active=True, is_superuser=True)
    db.add(u)
    db.flush()
    from tests.tenant_test_utils import assign_company
    assign_company(db, u, 1)
    c = CRMCompany(organization_id=1, name='Service customer')
    p = SRMProduct(organization_id=1, sku='FOLLOW-SERVICE', item_name='Consultation', product_type='service', active=True, track_inventory=False)
    db.add_all([c, p])
    db.flush()
    return (u, c, p)

def data(c, p, **extra):
    return CreateFollowUp(customer_id=c.id, product_id=p.id, title='Service care', reference_at=datetime(2026, 11, 3, 9, tzinfo=timezone.utc), **extra)

def test_reference_45_days_and_source_idempotency(db, setup):
    u, c, p = setup
    first = create(db, u, data(c, p), source_key='order:1:line:1')
    again = create(db, u, data(c, p), source_key='order:1:line:1')
    assert first.id == again.id
    assert first.due_at.date().isoformat() == '2026-12-18'
    assert db.query(FollowUp).count() == 1
    assert db.query(FollowUpActivity).count() == 1

def test_delivery_reference_and_specific_date(db, setup):
    u, c, p = setup
    with pytest.raises(ValueError):
        Schedule(reference='delivery')
    with pytest.raises(ValueError):
        Schedule(type='date', due_at=datetime(2026, 12, 1))
    due = datetime(2026, 12, 25, 13, tzinfo=timezone.utc)
    row = create(db, u, data(c, p, type='date', due_at=due))
    assert row.due_at == due

def test_reschedule_audit_recurring_and_closed_guard(db, setup):
    u, c, p = setup
    row = create(db, u, data(c, p, type='recurring'))
    original = row.due_at.isoformat()
    change(row.id, Change(action='reschedule', due_at=datetime(2026, 12, 20, 9, tzinfo=timezone.utc), notes='Customer requested'), db, u)
    event = db.query(FollowUpActivity).filter_by(action='reschedule').one()
    assert event.details['original_due_at'] == original
    change(row.id, Change(action='complete', notes='Contacted customer'), db, u)
    assert db.query(FollowUp).count() == 2
    with pytest.raises(HTTPException):
        change(row.id, Change(action='complete', notes='Retry'), db, u)
    assert db.query(FollowUp).count() == 2

def test_reminders_are_persistent_and_duplicate_safe(db, setup):
    u, c, p = setup
    row = create(db, u, data(c, p, type='date', due_at=datetime.now(timezone.utc) + timedelta(days=1)))
    dispatch(db)
    dispatch(db)
    assert db.query(FollowUpReminder).count() == 1
    assert db.query(Notification).filter_by(related_entity_id=row.id, event_type='service_follow_up').count() == 1
    row.due_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.flush()
    dispatch(db)
    dispatch(db)
    assert db.query(FollowUpReminder).count() == 2
    assert statistics(db, u)['Overdue'] == 1


@pytest.mark.parametrize('status', ['Accepted', 'Rejected', 'Declined', 'Cancelled', 'Superseded', 'Expired'])
def test_terminal_quote_stops_follow_up_notifications(db, setup, status):
    from app.apps.crm.models import CRMQuotation
    u, c, p = setup
    quote = CRMQuotation(organization_id=1, quote_number='FOLLOW-QUOTE', company_id=c.id,
        issue_date=datetime.now().date(), expiry_date=datetime.now().date(), status=status)
    db.add(quote)
    db.flush()
    row = create(db, u, data(c, p, type='date', due_at=datetime.now(timezone.utc)-timedelta(hours=1)))
    row.quotation_id = quote.id
    db.flush()
    dispatch(db)
    assert db.query(FollowUpReminder).count() == 0
    assert row.status == 'Scheduled'  # Preserve the task and its history for review.

def test_cross_tenant_links_and_visibility(db, setup):
    u, c, p = setup
    c.organization_id = 2
    db.flush()
    with pytest.raises(HTTPException):
        create(db, u, data(c, p))

def test_cancellation_preserves_history(db, setup):
    u, c, p = setup
    row = create(db, u, data(c, p))
    cancel_for_order(db, None, u)
    db.flush()
    assert row.status == 'Cancelled'
    assert db.query(FollowUpActivity).filter_by(action='source_cancelled').count() == 1

def test_http_shared_directory_actions_and_branch_isolation(client, db, superuser_headers, monkeypatch, tmp_path):
    from app.models.company import Company, Branch
    from app.branches.models import BranchOwnership
    from app.apps.business_os.services.module_service import ensure_business_os_seed
    from tests.tenant_test_utils import assign_company
    u = db.query(User).filter_by(email='testadmin@test.com').one()
    assign_company(db, u, 1)
    a = Branch(company_id=1, name='Follow-up main', code='FUA')
    b = Branch(company_id=1, name='Follow-up private', code='FUB')
    db.add_all([a, b])
    db.flush()
    c = CRMCompany(organization_id=1, branch_id=a.id, name='HTTP service customer')
    db.add(c)
    db.flush()
    db.add(BranchOwnership(resource_table='crm_companies', resource_key=str(c.id), company_id=1, branch_id=a.id, source='test'))
    ensure_business_os_seed(db, company_id=1)
    db.commit()
    headers = {**superuser_headers, 'X-Suite-Branch': str(a.id)}
    payload = {'customer_id': c.id, 'title': 'HTTP follow-up', 'reference_at': '2026-11-03T09:00:00+00:00', 'interval_days': 45}
    response = client.post('/api/v1/follow-ups', headers=headers, json=payload)
    assert response.status_code == 201, response.text
    ident = response.json()['id']
    assert response.json()['due_at'].startswith('2026-12-18')
    listed = client.get('/api/v1/follow-ups', headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()['total'] == 1
    denied = client.get(f'/api/v1/follow-ups/{ident}', headers={**headers, 'X-Suite-Branch': str(b.id)})
    assert denied.status_code == 404, denied.text
    completed = client.post(f'/api/v1/follow-ups/{ident}/actions', headers=headers, json={'action': 'complete', 'notes': 'Customer contacted'})
    assert completed.status_code == 200, completed.text
    assert completed.json()['status'] == 'Completed'
    history = client.get(f'/api/v1/follow-ups/{ident}', headers=headers)
    assert len(history.json()['activities']) == 2, history.text
    from app.core.config import settings
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(tmp_path))
    uploaded = client.post(f'/api/v1/follow-ups/{ident}/attachments', headers=headers, files={'file': ('care.txt', b'Customer care instructions', 'text/plain')})
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()['id']
    downloaded = client.get(f'/api/v1/follow-ups/{ident}/attachments/{attachment}', headers=headers)
    assert downloaded.status_code == 200 and downloaded.content == b'Customer care instructions', downloaded.text
    private = client.get(f'/api/v1/follow-ups/{ident}/attachments/{attachment}', headers={**headers, 'X-Suite-Branch': str(b.id)})
    assert private.status_code == 404
    preference = client.put('/api/v1/follow-ups/preferences/me', headers=headers, json={'in_app': False, 'overdue': True})
    assert preference.status_code == 200, preference.text

def test_grid_filters_grouping_and_pagination(db, setup):
    import json
    from app.shared.follow_ups import grid_query
    u, c, p = setup
    create(db, u, data(c, p, priority='High'))
    create(db, u, data(c, p, priority='Normal'))
    state = {'pageSize': 1, 'sorting': [{'id': 'priority', 'desc': False}]}
    result = grid_query(json.dumps(state), db, u)
    assert result['total'] == 2 and len(result['rows']) == 1
    state = {'grouping': ['priority']}
    result = grid_query(json.dumps(state), db, u)
    assert {g['value'] for g in result['groups']} == {'High', 'Normal'}
    state = {'filters': {'logic': 'and', 'rules': [{'field': 'priority', 'operator': 'equals', 'value': 'High'}]}}
    result = grid_query(json.dumps(state), db, u)
    assert result['total'] == 1 and result['rows'][0]['priority'] == 'High'

def test_pos_order_creates_follow_up_once_on_retry(client, db, superuser_headers):
    from app.models.company import Branch
    from app.branches.models import BranchOwnership
    from app.apps.business_os.services.module_service import ensure_business_os_seed
    from tests.tenant_test_utils import assign_company
    from app.main import app
    u = db.query(User).filter_by(email='testadmin@test.com').one()
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, u)
    assign_company(db, u, 1)
    b = Branch(company_id=1, name='POS follow-up', code='POSFU')
    db.add(b)
    db.flush()
    c = CRMCompany(organization_id=1, branch_id=b.id, name='Checkout customer')
    db.add(c)
    db.flush()
    db.add(BranchOwnership(resource_table='crm_companies', resource_key=str(c.id), company_id=1, branch_id=b.id, source='test'))
    p = SRMProduct(organization_id=1, sku='POS-FU', item_name='Care service', product_type='service', track_inventory=False, active=True, sales_rate=200, metadata_json={'follow_up': {'required': True, 'interval_days': 45, 'reference_at': '2026-11-03T09:00:00Z'}})
    db.add(p)
    ensure_business_os_seed(db, company_id=1)
    db.commit()
    app.state.business_os_session_factory = lambda: db
    app.state.business_os_close_session = False
    try:
        headers = {**superuser_headers, 'X-Suite-Branch': str(b.id)}
        payload = {'order_number': 'POS-FOLLOW-RETRY', 'title': 'POS service', 'customer_id': c.id, 'metadata_json': {'source': 'pos', 'pos_sale_id': 'retry-1'}, 'lines': [{'product_id': p.id, 'description': 'Care service', 'service_type': 'service', 'quantity': 1, 'unit_price': 200}]}
        first = client.post('/api/v1/srm/sales-orders', headers=headers, json=payload)
        assert first.status_code == 201, first.text
        again = client.post('/api/v1/srm/sales-orders', headers=headers, json=payload)
        assert again.status_code == 201, again.text
        assert first.json()['id'] == again.json()['id']
        assert db.query(FollowUp).count() == 1
        assert db.query(FollowUp).one().due_at.date().isoformat() == '2026-12-18'
    finally:
        del app.state.business_os_session_factory
        del app.state.business_os_close_session

def test_disabled_employee_reminders(db, setup):
    from app.shared.follow_ups import FollowUpPreference
    u, c, p = setup
    create(db, u, data(c, p, type='date', due_at=datetime.now(timezone.utc) + timedelta(hours=1)))
    db.add(FollowUpPreference(organization_id=1, user_id=u.id, in_app=False, overdue=True))
    db.flush()
    dispatch(db)
    assert db.query(FollowUpReminder).count() == 0

def test_reminder_failure_history_and_retry(db, setup, monkeypatch):
    import app.models.notification as notification_module
    u, c, p = setup
    create(db, u, data(c, p, type='date', due_at=datetime.now(timezone.utc) + timedelta(hours=1)))
    original = notification_module.Notification

    def unavailable(**kwargs):
        raise RuntimeError('Simulated dispatch interruption')
    monkeypatch.setattr(notification_module, 'Notification', unavailable)
    dispatch(db)
    receipt = db.query(FollowUpReminder).one()
    assert receipt.delivery_status == 'retry' and len(receipt.attempt_history) == 1
    monkeypatch.setattr(notification_module, 'Notification', original)
    receipt.next_attempt_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()
    dispatch(db)
    assert receipt.delivery_status == 'delivered' and len(receipt.attempt_history) == 2
    dispatch(db)
    assert len(receipt.attempt_history) == 2

def test_contact_link_visibility_and_search(db, setup):
    from app.apps.crm.models import CRMContact
    from app.shared.follow_ups import link_options
    u, c, p = setup
    contact = CRMContact(organization_id=1, company_id=c.id, first_name='Service', full_name='Service Contact')
    db.add(contact)
    db.flush()
    choices = link_options('contacts', 'Service', db, u)
    assert choices[0]['id'] == contact.id
    row = create(db, u, data(c, p, contact_id=contact.id))
    assert row.contact_id == contact.id

def test_calendar_day_interval_preserves_local_time_across_dst(db, setup):
    from zoneinfo import ZoneInfo
    u, c, p = setup
    reference = datetime(2026, 10, 31, 13, tzinfo=timezone.utc)
    payload = CreateFollowUp(customer_id=c.id, product_id=p.id, title='DST follow-up', reference_at=reference, timezone='America/New_York', interval_days=7)
    row=create(db,u,payload)
    assert row.due_at.astimezone(ZoneInfo('America/New_York')).hour==9


def test_catalog_template_waits_for_customer_event(db, setup):
    from app.shared.catalog import ItemInput
    from app.shared.follow_ups import create_for_order, create_for_engagement
    from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine, SRMEngagement
    u, c, p = setup
    template = ItemInput(kind="service", name="Consultation", code="CONSULT", follow_up={
        "required": True, "reference": "completion", "interval_days": 7})
    assert template.follow_up.reference_at is None
    old_template = ItemInput(kind="service", name="Consultation", code="CONSULT", follow_up={
        "required": True, "reference_at": "2026-01-01T09:00:00Z"})
    assert old_template.follow_up.reference_at is None
    p.metadata_json = {"follow_up": template.follow_up.model_dump(mode="json")}
    order = SRMSalesOrder(organization_id=1, order_number="SERVICE-EVENT", title="Consultation", customer_id=c.id, status="draft")
    db.add(order)
    db.flush()
    line = SRMSalesOrderLine(sales_order_id=order.id, product_id=p.id, description="Consultation")
    db.add(line)
    db.flush()
    create_for_order(db, order, u)
    assert db.query(FollowUp).count() == 0
    order.status = "confirmed"
    create_for_order(db, order, u)
    assert db.query(FollowUp).count() == 0
    engagement = SRMEngagement(organization_id=1, engagement_number="ENG-EVENT", sales_order_id=order.id, customer_id=c.id, name="Consultation", status="completed")
    db.add(engagement)
    db.flush()
    before = datetime.now(timezone.utc)
    create_for_engagement(db, engagement, u)
    create_for_engagement(db, engagement, u)
    row = db.query(FollowUp).one()
    assert row.customer_id == c.id and row.order_line_id == line.id
    from app.shared.follow_ups import utc
    assert before + timedelta(days=7) <= utc(row.due_at) <= datetime.now(timezone.utc) + timedelta(days=7)


def test_confirmed_purchase_creates_follow_up_and_draft_cancelled_do_not(db, setup):
    from app.shared.follow_ups import create_for_order
    from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
    u, c, p = setup
    p.metadata_json = {"follow_up": {"required": True, "interval_days": 3}}
    order = SRMSalesOrder(organization_id=1, order_number="PURCHASE-EVENT", title="Purchase", customer_id=c.id, status="draft")
    db.add(order)
    db.flush()
    db.add(SRMSalesOrderLine(sales_order_id=order.id, product_id=p.id, description="Purchase"))
    db.flush()
    create_for_order(db, order, u)
    assert db.query(FollowUp).count() == 0
    order.status = "cancelled"
    create_for_order(db, order, u)
    assert db.query(FollowUp).count() == 0
    order.status = "confirmed"
    create_for_order(db, order, u)
    create_for_order(db, order, u)
    assert db.query(FollowUp).count() == 1


def test_line_can_disable_catalog_follow_up(db, setup):
    from app.shared.follow_ups import create_for_order
    from app.apps.srm.models import SRMSalesOrder, SRMSalesOrderLine
    u, c, p = setup
    p.metadata_json = {"follow_up": {"required": True}}
    order = SRMSalesOrder(organization_id=1, order_number="NO-FOLLOW", title="Opt out", customer_id=c.id, status="confirmed")
    db.add(order)
    db.flush()
    db.add(SRMSalesOrderLine(sales_order_id=order.id, product_id=p.id, metadata_json={"follow_up": {"required": False}}))
    db.flush()
    create_for_order(db, order, u)
    assert db.query(FollowUp).count() == 0
