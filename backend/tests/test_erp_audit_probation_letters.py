from datetime import date
from io import BytesIO
import pytest
from pypdf import PdfReader
from app.models.company import Branch
from app.models.employee import Employee, ProbationAction
from tests.rich_text_test_utils import organization_context


def employee(db):
    branch = db.query(Branch).filter_by(company_id=1, is_active=True).first()
    row = Employee(employee_id='LETTER-QA', first_name='Synthetic', last_name='Employee',
        date_of_joining=date(2026, 1, 1), branch_id=branch.id, probation_status='on_probation')
    db.add(row); db.commit()
    return row


@pytest.mark.parametrize('kind,title', [('confirm','Confirmation Letter'),
    ('extend','Probation Extension Letter'), ('terminate','Probation Termination Letter')])
def test_probation_letter_wraps_all_remarks(client, db, superuser_headers, tmp_path, monkeypatch, kind, title):
    from app.api.v1 import probation
    monkeypatch.setattr(probation.settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(probation, 'persist_file', lambda path: None)
    person = employee(db)
    paragraphs = [f'Review paragraph {i:03d}: ' + 'Detailed synthetic review evidence & <approved> ' * 5 for i in range(70)]
    response = client.post(f'/api/v1/hrms/probation/{person.id}/{kind}', headers=superuser_headers,
        json={'effectiveDate':'2026-06-30', 'extendedUntil':'2026-09-30' if kind == 'extend' else None,
              'remarks':'\n'.join(paragraphs)})
    assert response.status_code == 200, response.text
    letter = client.get(f'/api/v1/hrms/probation/{person.id}/letter', headers=superuser_headers)
    assert letter.status_code == 200, letter.text
    assert letter.content.startswith(b'%PDF-')
    reader = PdfReader(BytesIO(letter.content))
    assert len(reader.pages) > 1, 'Long letter must paginate instead of drawing past page edges'
    text = '\n'.join(p.extract_text() for p in reader.pages)
    assert title in text and 'Synthetic Employee' in text and 'LETTER-QA' in text
    assert '2026-06-30' in text
    if kind == 'extend': assert '2026-09-30' in text
    normalized = ''.join(text.split())
    for paragraph in paragraphs:
        assert ''.join(paragraph.split()) in normalized
    assert 'Authorized HR Signatory' in text
    assert db.query(ProbationAction).filter_by(employee_id=person.id).one().letter_generated
    from pathlib import Path
    output = Path(__file__).resolve().parents[2]/'.tmp'/f'erp-audit-probation-{kind}.pdf'
    output.write_bytes(letter.content)


def test_failed_pdf_generation_does_not_claim_letter_generated(client, db, superuser_headers, tmp_path, monkeypatch):
    from app.api.v1 import probation
    from reportlab.platypus import SimpleDocTemplate
    monkeypatch.setattr(probation.settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(probation, 'persist_file', lambda path: None)
    person = employee(db)
    response = client.post(f'/api/v1/hrms/probation/{person.id}/confirm', headers=superuser_headers,
        json={'effectiveDate':'2026-06-30', 'remarks':'Synthetic confirmation'})
    assert response.status_code == 200, response.text
    def fail(*args, **kwargs): raise RuntimeError('Synthetic renderer failure')
    monkeypatch.setattr(SimpleDocTemplate, 'build', fail)
    response = client.get(f'/api/v1/hrms/probation/{person.id}/letter', headers=superuser_headers)
    assert response.status_code == 503, response.text
    db.expire_all()
    assert not db.query(ProbationAction).filter_by(employee_id=person.id).one().letter_generated
    assert not list(tmp_path.rglob('*.pdf'))


@pytest.mark.parametrize('company,permissions,expected', [
    (1, ['employee_view'], 403), (2, ['employee_update'], 404)])
def test_probation_letter_denies_unrelated_reader(client, db, superuser_headers, tmp_path, monkeypatch, company, permissions, expected):
    from app.api.v1 import probation
    from ai_test_utils import auth_headers
    monkeypatch.setattr(probation.settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(probation, 'persist_file', lambda path: None)
    person = employee(db)
    response = client.post(f'/api/v1/hrms/probation/{person.id}/confirm', headers=superuser_headers,
        json={'effectiveDate':'2026-06-30', 'remarks':'Private review'})
    assert response.status_code == 200, response.text
    headers, _ = auth_headers(client, db, email=f'letter-reader-{company}@example.com',
        permissions=permissions, company_id=company)
    response = client.get(f'/api/v1/hrms/probation/{person.id}/letter', headers=headers)
    assert response.status_code == expected, response.text
    assert not db.query(ProbationAction).filter_by(employee_id=person.id).one().letter_generated
    assert not list(tmp_path.rglob('*.pdf'))
