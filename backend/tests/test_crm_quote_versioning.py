from app.apps.crm.models import CRMQuoteVersion
from tests.test_contact_directory import directory_identity  # noqa: F401


def test_crm_quote_new_version_snapshots_existing_quote(client, db, superuser_headers):
    quote = client.post("/api/v1/crm/quotes", headers=superuser_headers, json={
        "quoteNumber": "QT-VER-001",
        "issueDate": "2026-06-01",
        "expiryDate": "2026-06-30",
    })
    quote_id = quote.json()["id"]
    response = client.post(f"/api/v1/crm/quotes/{quote_id}/new-version", headers=superuser_headers)
    assert response.status_code == 201, response.text
    assert response.json()["quote"]["versionNumber"] == 2
    assert db.query(CRMQuoteVersion).filter(CRMQuoteVersion.quote_id == quote_id).count() == 1


def test_revision_invalidates_prior_approval_and_keeps_flat_snapshots(client, db, superuser_headers):
    from datetime import datetime, timezone
    from app.apps.crm.models import CRMQuotation, CRMQuoteApproval
    response = client.post('/api/v1/crm/quotes', headers=superuser_headers, json={
        'quoteNumber': 'QT-REV-CONTROLS', 'issueDate': '2026-11-01', 'expiryDate': '2026-12-01'})
    assert response.status_code == 201, response.text
    ident = response.json()['id']
    quote = db.get(CRMQuotation, ident)
    quote.status = 'Sent'
    quote.approval_status = 'approved'
    quote.sent_at = quote.approved_at = datetime.now(timezone.utc)
    quote.approved_by = quote.created_by_user_id
    quote.pdf_url = '/historical-quotation.pdf'
    approval = CRMQuoteApproval(organization_id=1, quote_id=ident, status='pending')
    db.add(approval)
    from test_identity_utils import own_workflow_records
    own_workflow_records(db, approval)
    db.commit()
    response = client.post(f'/api/v1/crm/quotes/{ident}/new-version', headers=superuser_headers)
    assert response.status_code == 201, response.text
    snapshot = db.query(CRMQuoteVersion).filter_by(quote_id=ident, version_number=1).one().snapshot_json
    assert snapshot['status'] == 'Sent'
    assert snapshot['pdfUrl'] == '/historical-quotation.pdf'
    assert 'versions' not in snapshot
    db.expire_all()
    quote = db.get(CRMQuotation, ident)
    assert quote.status == 'Draft' and quote.approval_status == 'not_submitted'
    assert quote.sent_at is None and quote.approved_at is None and quote.pdf_url is None
    assert db.query(CRMQuoteApproval).filter_by(quote_id=ident).one().status == 'superseded'
    assert client.post(f'/api/v1/crm/quotes/{ident}/new-version', headers=superuser_headers).status_code == 201
    assert db.query(CRMQuoteVersion).filter_by(quote_id=ident).count() == 2
