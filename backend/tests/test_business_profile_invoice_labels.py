import io
import os
from pathlib import Path
from pypdf import PdfReader
from tests.test_industry_operations import business, stylist, booking, post, state
from tests.test_contact_directory import directory_identity


def test_invoice_terms_follow_branch_and_freeze_at_issue(client, db, business):
    from app.models.company import Branch
    from app.apps.srm.commercial_models import InvoiceContext
    h, buyer, _, service = business
    branch = db.query(Branch).filter_by(company_id=1).first()
    label = 'Patient receiving specialist consultation and follow-up care'
    assert len(label) == 60
    url = '/api/v1/access/settings/business-profile/configuration'
    params = {'branch_id': branch.id}
    saved = client.put(url, params=params, headers=h, json={'version': 0, 'values': {'business_type': 'hospital', 'terms': {'customer': [label, 'Patients']}}})
    assert saved.status_code == 200, saved.text
    buyer.name = 'Example patient with an extended registered billing name for visual layout verification'
    db.commit()
    row = post(client, h, '/appointments', booking(client, h, buyer, service, stylist(client, h)))
    for status in ['checked_in', 'in_service', 'completed']:
        row = state(client, h, row, status)
    invoice = post(client, h, f'/records/{row["id"]}/invoice', {'expected_revision': row['revision']})
    pdf_url = f'/api/v1/srm/invoices/{invoice["id"]}/pdf'
    draft = client.get(pdf_url, headers=h)
    assert draft.status_code == 200, draft.text
    def text(content):
        return ' '.join(' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(content)).pages).split())
    assert label in text(draft.content)
    issued = client.post(f'/api/v1/srm/invoices/{invoice["id"]}/approve', headers=h)
    assert issued.status_code == 200, issued.text
    ctx = db.get(InvoiceContext, invoice['id'])
    assert ctx.customer_snapshot['_business_terms']['customer'][0] == label
    changed = client.put(url, params=params, headers=h, json={'version': 1, 'values': {'business_type': 'salon'}})
    assert changed.status_code == 200, changed.text
    final = client.get(pdf_url, headers=h)
    assert final.status_code == 200, final.text
    assert label in text(final.content)
    assert 'Customer:' not in text(final.content)
    if os.environ.get('BUSINESS_PROFILE_PDF_QA_DIR'):
        target = Path(os.environ['BUSINESS_PROFILE_PDF_QA_DIR'])
        target.mkdir(parents=True, exist_ok=True)
        (target / 'business-profile-draft.pdf').write_bytes(draft.content)
        (target / 'business-profile-issued.pdf').write_bytes(final.content)
