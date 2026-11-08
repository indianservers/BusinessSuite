from datetime import date
from decimal import Decimal
import pytest
from app.apps.srm.services.recurrence import occurrence_dates


def test_month_end_does_not_drift():
    assert occurrence_dates(date(2028, 1, 31), 3, "monthly") == [date(2028, 1, 31), date(2028, 2, 29), date(2028, 3, 31)]


def test_invoice_reads_shared_billing_address(db):
    from app.apps.crm.models import CRMCompany
    from app.shared.master_data_models import CompanyMasterDetails
    from app.apps.srm.services.commercial import billing_customer_snapshot
    buyer = CRMCompany(organization_id=1, name="Shared buyer", address="Legacy address")
    db.add(buyer); db.flush()
    details = CompanyMasterDetails(account_id=buyer.id, organization_id=1,
        addresses=[{"type":"Shipping", "line1":"Warehouse"},
                   {"type":"Billing", "line1":"Billing office", "city":"Dubai", "country":"AE"}])
    db.add(details); db.flush()
    frozen = billing_customer_snapshot(db, buyer)
    assert frozen["address"] == "Billing office, Dubai, AE"
    details.addresses = [{"type":"Billing", "line1":"Changed later"}]
    assert frozen["address"] == "Billing office, Dubai, AE"
    assert billing_customer_snapshot(db, buyer)["address"] == "Changed later"


def test_leap_year_and_weekly():
    assert occurrence_dates(date(2028, 2, 29), 2, "yearly")[-1] == date(2029, 2, 28)
    assert occurrence_dates(date(2026, 12, 29), 2, "weekly")[-1] == date(2027, 1, 5)


@pytest.mark.parametrize("count,rule", [(0, "monthly"), (121, "daily"), (2, "invalid")])
def test_invalid_schedule(count, rule):
    with pytest.raises(ValueError):
        occurrence_dates(date(2026, 1, 1), count, rule)

def test_schedule_retries_do_not_duplicate_milestones(client, db, superuser_headers, directory_identity):
    from tests.srm_test_utils import create_engagement_via_confirm, seed_invoice_parties
    from app.apps.srm.models import SRMBillingPlan, SRMBillingMilestone
    seed_invoice_parties(db)
    engagement, _ = create_engagement_via_confirm(client, superuser_headers)
    plan = db.query(SRMBillingPlan).filter_by(engagement_id=engagement["id"]).first()
    plan.recurrence_rule = "monthly"
    db.commit()
    url = f"/api/v1/srm/billing-plans/{plan.id}/recurring-schedule"
    params = {"start_date": "2028-01-31", "amount": "100", "occurrences": 3}
    first = client.post(url, params=params, headers=superuser_headers)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 3
    retry = client.post(url, params=params, headers=superuser_headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["created"] == 0
    assert retry.json()["skipped"] == 3
    assert db.query(SRMBillingMilestone).filter_by(billing_plan_id=plan.id, due_date=date(2028, 2, 29)).count() == 1
from tests.test_contact_directory import directory_identity  # noqa: F401


@pytest.mark.parametrize("notify", [True, False])
def test_due_recurring_creates_draft_once(client, db, superuser_headers, directory_identity, notify):
    from tests.srm_test_utils import create_engagement_via_confirm, seed_invoice_parties
    from app.apps.srm.models import SRMBillingPlan, SRMBillingMilestone, SRMInvoice
    seed_invoice_parties(db)
    engagement, _ = create_engagement_via_confirm(client, superuser_headers)
    plan = db.query(SRMBillingPlan).filter_by(engagement_id=engagement["id"]).first()
    plan.recurrence_rule = "monthly"
    plan.status = "active"
    db.commit()
    result = client.post(f"/api/v1/srm/billing-plans/{plan.id}/recurring-schedule", params={"start_date": "2020-01-31", "amount": "125", "occurrences": 1, "payment_terms_days": 14, "automatic_drafts": True, "notify_on_creation": notify, "subject": "Monthly support", "customer_notes": "Thank you", "terms": "Net fourteen"}, headers=superuser_headers)
    assert result.status_code == 200, result.text
    milestone = db.get(SRMBillingMilestone, result.json()["milestones"][0]["id"])
    assert milestone.status == "ready"
    from app.apps.srm.services.recurring_jobs import dispatch_due
    outcome = dispatch_due(db)
    assert outcome["created"] == 1, outcome
    db.refresh(milestone)
    invoice = db.query(SRMInvoice).filter_by(invoice_draft_id=milestone.invoice_draft_id).one()
    assert invoice.status == "draft"
    assert invoice.issue_date == date(2020, 1, 31)
    assert invoice.due_date == date(2020, 2, 14)
    from app.shared.form_defaults import document_defaults
    snapshot = document_defaults(db, invoice.organization_id, "srm", "invoice", invoice.id)
    assert snapshot["customer_notes"] == "Thank you"
    assert snapshot["terms"] == "Net fourteen"
    visible = client.get("/api/v1/srm/invoices", headers=superuser_headers)
    assert visible.status_code == 200, visible.text
    assert invoice.id in {row["id"] for row in visible.json()}
    report = client.get("/api/v1/srm/reports", headers=superuser_headers)
    assert report.status_code == 200, report.text
    occurrences = report.json()["recurring_invoice_details"]
    detail = next(row for row in occurrences if row["id"] == milestone.id)
    assert detail["invoice_id"] == invoice.id
    assert detail["date"] == "2020-01-31"
    assert detail["currency"] == plan.currency
    assert Decimal(detail["total_amount"]) == 125
    assert client.post("/api/v1/srm/recurring-invoices/process-due", headers=superuser_headers).json()["created"] == 0
    from app.models.notification import Notification
    notifications = db.query(Notification).filter_by(title="Recurring invoice draft created", related_entity_id=invoice.id).all()
    assert len(notifications) == int(notify)
    if notify:
        assert notifications[0].company_id == invoice.organization_id
        assert notifications[0].action_url == f"/srm/invoices/{invoice.id}"

def test_scheduler_with_no_active_recurring_plans(db):
    from app.apps.srm.services.recurring_jobs import dispatch_due
    assert dispatch_due(db) == {"created": 0, "failed_owner_batches": 0}



def test_end_date_and_template_settings(client, db, superuser_headers, directory_identity):
    from tests.srm_test_utils import create_engagement_via_confirm, seed_invoice_parties
    from app.apps.srm.models import SRMBillingPlan
    seed_invoice_parties(db)
    engagement, _ = create_engagement_via_confirm(client, superuser_headers)
    plan = db.query(SRMBillingPlan).filter_by(engagement_id=engagement['id']).first()
    plan.recurrence_rule = 'monthly'
    db.commit()
    url = f'/api/v1/srm/billing-plans/{plan.id}/recurring-schedule'
    params = {'start_date':'2028-01-31','end_date':'2028-02-29','amount':'100','occurrences':12,'invoice_template':'compact'}
    result = client.post(url, params=params, headers=superuser_headers)
    assert result.status_code == 200, result.text
    assert result.json()['created'] == 2
    assert all(row['metadata_json']['invoice_template'] == 'compact' for row in result.json()['milestones'])
    params['end_date'] = '2027-01-01'
    assert client.post(url, params=params, headers=superuser_headers).status_code == 422

def test_ongoing_schedule_extends_without_date_drift_or_duplicates(client, db, superuser_headers, directory_identity):
    from tests.srm_test_utils import create_engagement_via_confirm, seed_invoice_parties
    from app.apps.srm.models import SRMBillingPlan, SRMBillingMilestone
    from app.apps.srm.services.recurring_jobs import dispatch_due
    from datetime import timedelta
    seed_invoice_parties(db)
    engagement, _ = create_engagement_via_confirm(client, superuser_headers)
    plan = db.query(SRMBillingPlan).filter_by(engagement_id=engagement['id']).first()
    plan.recurrence_rule = 'monthly'; plan.status = 'active'; db.commit()
    start = date.today() - timedelta(days=1)
    result = client.post(f'/api/v1/srm/billing-plans/{plan.id}/recurring-schedule', params={'start_date':start.isoformat(),'amount':'100','occurrences':1,'never_expires':True,'automatic_drafts':True}, headers=superuser_headers)
    assert result.status_code == 200, result.text
    outcome = dispatch_due(db)
    assert outcome['created'] == 1, outcome
    rows = db.query(SRMBillingMilestone).filter_by(billing_plan_id=plan.id).filter(SRMBillingMilestone.metadata_json['recurring'].as_boolean() == True).all()
    assert len(rows) == 13
    assert len({row.due_date for row in rows}) == 13
    assert sorted(row.due_date for row in rows) == occurrence_dates(start, 13, 'monthly')
    assert dispatch_due(db)['created'] == 0

def test_recurring_settings_validate_existing_company_records(client, db, superuser_headers, directory_identity):
    from tests.srm_test_utils import create_engagement_via_confirm, seed_invoice_parties
    from app.apps.srm.models import SRMBillingPlan
    seed_invoice_parties(db)
    engagement, _ = create_engagement_via_confirm(client, superuser_headers)
    plan = db.query(SRMBillingPlan).filter_by(engagement_id=engagement['id']).first()
    plan.recurrence_rule = 'monthly'; db.commit()
    options = client.get('/api/v1/srm/recurring-invoices/options', headers=superuser_headers)
    assert options.status_code == 200, options.text
    assert options.json()['users']
    params = {'start_date':'2026-01-01','amount':'100','occurrences':1,'salesperson_id':options.json()['users'][0]['value'],'order_number':'PO-42'}
    url = f'/api/v1/srm/billing-plans/{plan.id}/recurring-schedule'
    response = client.post(url, json=params, headers=superuser_headers)
    assert response.status_code == 200, response.text
    meta = response.json()['milestones'][0]['metadata_json']
    assert meta['order_number'] == 'PO-42'
    assert meta['salesperson_name'] == options.json()['users'][0]['label']
    params['salesperson_id'] = 999999999
    assert client.post(url, params=params, headers=superuser_headers).status_code == 422
    params.pop('salesperson_id'); params['payment_mode_id'] = 999999999
    assert client.post(url, params=params, headers=superuser_headers).status_code == 422

def test_billing_day_uses_company_timezone_at_midnight_boundary():
    from datetime import datetime, timezone
    from app.apps.srm.services.recurrence import business_date
    stamp=datetime(2026,11,6,22,0,tzinfo=timezone.utc)
    assert business_date('Asia/Dubai',stamp)==date(2026,11,7)
    assert business_date('Asia/Kolkata',stamp)==date(2026,11,7)
    assert business_date('UTC',stamp)==date(2026,11,6)

def test_custom_repeat_interval_keeps_original_month_end_anchor():
    assert occurrence_dates(date(2026,1,31),3,'monthly',interval=2)==[date(2026,1,31),date(2026,3,31),date(2026,5,31)]
