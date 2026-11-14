from io import BytesIO

from pypdf import PdfReader

from app.shared.business_profile import KIND, scope_key
from app.shared.models import ServicePolicy
from tests.test_payslip_workflow import slips
from tests.rich_text_test_utils import organization_context


def configure(db, company_id, label, branch_id=None):
    db.add(ServicePolicy(organization_id=company_id, kind=KIND,
                         scope_key=scope_key(company_id, branch_id), module_key='*',
                         values_json={'terms': {'employee': [label, label + 's']}}, version=1, updated_by=1))
    db.commit()


def pdf_text(content, password=None):
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        assert reader.decrypt(password)
    return ' '.join(' '.join(page.extract_text() or '' for page in reader.pages).split())


def test_published_payslip_uses_employee_branch_and_keeps_published_content(client, db, slips):
    run, record, admin, employee = slips
    branch = record.employee.branch
    configure(db, branch.company_id, 'Company colleague')
    label = 'Team member receiving consolidated salary and benefit detail'
    assert len(label) == 60
    configure(db, branch.company_id, label, branch.id)
    preview = client.get('/api/v1/payroll/delivery/template-preview', headers={**admin, 'X-Suite-Branch': str(branch.id)})
    assert preview.status_code == 200, preview.text
    assert label + ':' in pdf_text(preview.content)
    result = client.post(f'/api/v1/payroll/runs/{run.id}/payslip-publish',
                         json={'send_email': False}, headers=admin)
    assert result.status_code == 201, result.text
    url = f'/api/v1/payroll/payslip/{record.id}/pdf'
    result = client.get(url, headers=employee)
    assert result.status_code == 200, result.text
    original = result.content
    text = pdf_text(original, '02011990')
    assert label + ':' in text and record.employee.employee_id in text
    assert 'Company colleague:' not in text
    policy = db.query(ServicePolicy).filter_by(scope_key=scope_key(branch.company_id, branch.id), kind=KIND).one()
    policy.values_json = {'business_type': 'hospital'}
    db.commit()
    assert client.get(url, headers=employee).content == original


def test_custom_payslip_footer_is_not_rewritten(tmp_path):
    from app.services.payslip_pdf import render_payslip
    path = tmp_path / 'custom.pdf'
    render_payslip(str(path), {'month': 5, 'year': 2026, 'employee': {'first_name': 'Original Employee'}},
                   template={'footer': 'Employee support: contact Payroll', 'show_employee_code': False},
                   business_terms={'employee': ['Team member', 'Team members']})
    text = pdf_text(path.read_bytes())
    assert 'Team member: Original Employee' in text
    assert 'Employee support: contact Payroll' in text


def test_probation_letter_uses_employee_branch_terms(client, db, superuser_headers, tmp_path, monkeypatch):
    from app.api.v1 import probation
    from tests.test_erp_audit_probation_letters import employee
    monkeypatch.setattr(probation.settings, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(probation, 'persist_file', lambda path: None)
    person = employee(db)
    configure(db, person.branch.company_id, 'Team member', person.branch_id)
    result = client.post(f'/api/v1/hrms/probation/{person.id}/confirm', headers=superuser_headers,
                         json={'effectiveDate': '2026-06-30', 'remarks': 'Employee authored text remains.'})
    assert result.status_code == 200, result.text
    result = client.get(f'/api/v1/hrms/probation/{person.id}/letter', headers=superuser_headers)
    assert result.status_code == 200, result.text
    text = pdf_text(result.content)
    assert 'Team member: Synthetic Employee (LETTER-QA)' in text
    assert 'Employee authored text remains.' in text


def test_salary_certificate_wraps_custom_labels_and_preserves_purpose(client, db, slips):
    _, record, admin, _ = slips
    label = 'Team member receiving consolidated salary and benefit detail'
    configure(db, record.employee.branch.company_id, label, record.employee.branch_id)
    response = client.post('/api/v1/payroll/salary-certificates', headers=admin,
                           json={'employee_id': record.employee_id, 'purpose': 'Employee loan support'})
    assert response.status_code == 201, response.text
    document = client.get(response.json()['file_url'], headers=admin)
    assert document.status_code == 200, document.text
    text = pdf_text(document.content)
    assert label + ':' in text
    assert 'Purpose: Employee loan support' in text
    assert 'Annual CTC:' in text and 'Monthly Gross:' in text
