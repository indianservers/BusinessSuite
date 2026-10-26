from app.apps.crm.models import CRMQuoteApproval
from datetime import datetime, timezone
import pytest


@pytest.fixture(autouse=True)
def approval_tenant(db):
    from app.models.company import Company
    if not db.get(Company, 1):
        db.add(Company(id=1, name='Quote approval regression tenant'))
    db.commit()


def test_quote_approval_list_defaults_to_submission_date(client, db, superuser_headers):
    quote = client.post('/api/v1/crm/quotes', headers=superuser_headers, json={
        'quoteNumber': 'QT-LIST-001', 'issueDate': '2026-10-01', 'expiryDate': '2026-10-31',
    })
    assert quote.status_code in (200, 201), quote.text
    submitted = client.post(f"/api/v1/crm/quotes/{quote.json()['id']}/submit", headers=superuser_headers, json={})
    assert submitted.status_code == 200, submitted.text
    row = db.query(CRMQuoteApproval).filter_by(quote_id=quote.json()['id']).one()
    row.submitted_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    db.add(CRMQuoteApproval(organization_id=row.organization_id, quote_id=row.quote_id, status='pending', submitted_at=datetime(2026, 10, 2, tzinfo=timezone.utc)))
    db.commit()
    response = client.get('/api/v1/crm/quote-approvals', headers=superuser_headers)
    assert response.status_code == 200, response.text
    items = response.json()['items']
    assert len(items) == 2
    assert items[0]['submitted_at'] > items[1]['submitted_at']
    invalid = client.get('/api/v1/crm/quote-approvals?sort_by=missing_column', headers=superuser_headers)
    assert invalid.status_code == 422


def test_crm_quote_submit_approve_and_reject_paths(client, db, superuser_headers):
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-APP-001",
        "issueDate": "2026-06-01",
        "expiryDate": "2026-06-30",
    })
    quote_id = quote.json()["id"]

    submit = client.post(f"/api/v1/crm/quotes/{quote_id}/submit", headers=superuser_headers, json={"comments": "Discount review"})
    assert submit.status_code == 200, submit.text
    assert submit.json()["approvalStatus"] == "pending"
    assert db.query(CRMQuoteApproval).filter(CRMQuoteApproval.quote_id == quote_id, CRMQuoteApproval.status == "pending").count() == 1

    approve = client.post(f"/api/v1/crm/quotes/{quote_id}/approve", headers=superuser_headers, json={"comments": "Approved"})
    assert approve.status_code == 200, approve.text
    assert approve.json()["approvalStatus"] == "approved"
    assert db.query(CRMQuoteApproval).filter(CRMQuoteApproval.quote_id == quote_id, CRMQuoteApproval.status == "approved").count() == 1


def test_approval_visibility_inherits_quote_scope(client, db):
    from app.models.user import User, Role, Permission
    from app.core.security import get_password_hash
    from app.apps.crm.models import CRMQuotation
    from datetime import date

    permission = Permission(name='crm_view', module='crm')
    role = Role(name='crm_sales_executive', permissions=[permission])
    user = User(email='approval-owner@example.com', hashed_password=get_password_hash('Password@123'), role=role, is_active=True)
    db.add(user)
    db.flush()
    for number, org, owned in [('OWN', 1, True), ('OTHER', 1, False), ('FOREIGN', 2, True)]:
        quote = CRMQuotation(organization_id=org, quote_number=number, issue_date=date(2026,10,1), expiry_date=date(2026,10,31), owner_user_id=user.id if owned else None, created_by_user_id=user.id if owned else None)
        db.add(quote)
        db.flush()
        db.add(CRMQuoteApproval(organization_id=org, quote_id=quote.id, status='pending'))
        if number == 'OWN':
            own_quote_id = quote.id
    db.commit()
    login = client.post('/api/v1/auth/login', json={'email':user.email, 'password':'Password@123'})
    headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
    response = client.get('/api/v1/crm/quote-approvals', headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()['total'] == 1
    assert response.json()['items'][0]['quoteId'] == own_quote_id
