from datetime import date
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from pypdf import PdfReader

from app.models.company import Company, Branch
from app.models.employee import Employee
from app.models.document import StudioAsset, StudioDocument, StudioTemplate
from app.apps.interns_hub.models import InternApplication

BASE = "/api/v1/documents/studio"


@pytest.fixture
def studio(client, db, superuser_headers):
    company = db.query(Company).filter(Company.id == 1).first()
    if not company:
        company = Company(id=1, name="Example Company", address="12 Innovation Road", city="Hyderabad", email="hr@example.com")
        db.add(company)
    db.flush()
    branch = Branch(name="Main", company_id=1)
    db.add(branch); db.flush()
    employee = Employee(employee_id="DOC-001", first_name="Ananya", last_name="Rao", branch_id=branch.id, date_of_joining=date(2026, 6, 1))
    db.add(employee); db.commit()
    response = client.post(BASE+"/initialize", headers=superuser_headers)
    assert response.status_code == 200, response.text
    templates = client.get(BASE+"/templates", headers=superuser_headers).json()
    head = client.get(BASE+"/letterheads", headers=superuser_headers).json()[0]
    return superuser_headers, employee, templates, head


def payload(studio, name="Completion Letter"):
    _, employee, templates, head = studio
    template = next(t for t in templates if t["name"] == name)
    values = {"program": "Software Engineering Internship", "start_date": "2026-06-01", "end_date": "2026-09-30", "remarks": "Completed assigned projects with dedication and care."}
    return dict(template_id=template["id"], template_version=template["version"], letterhead_id=head["id"], letterhead_version=head["version"],
        recipient_type="employee", recipient_id=employee.id, issue_date="2026-10-27", variables=values, request_key=str(uuid4()))


def pdf_text(response):
    assert response.status_code == 200, response.text
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)


def test_starters_idempotent_preview_and_historical_reprint(client, db, studio):
    headers, employee, templates, _ = studio
    assert len(templates) == 12
    assert client.post(BASE+"/initialize", headers=headers).status_code == 200
    assert len(client.get(BASE+"/templates", headers=headers).json()) == 12
    data = payload(studio)
    preview = client.post(BASE+"/preview", json=data, headers=headers)
    assert "Ananya Rao" in pdf_text(preview) and "PREVIEW" in pdf_text(preview)
    assert db.query(StudioDocument).count() == 0
    issued = client.post(BASE+"/issue", json=data, headers=headers)
    assert issued.status_code == 201, issued.text
    identity = issued.json()["id"]
    assert client.post(BASE+"/issue", json=data, headers=headers).json()["id"] == identity
    assert db.query(StudioDocument).count() == 1
    employee.first_name = "Changed"
    template = db.query(StudioTemplate).filter(StudioTemplate.id == data["template_id"]).one()
    template.body = "Changed wording"
    template.version += 1
    db.commit()
    original = client.get(f"{BASE}/issued/{identity}/pdf", headers=headers)
    assert "Ananya Rao" in pdf_text(original) and "Changed" not in pdf_text(original)
    assert "no-store" in original.headers["cache-control"]
    assert client.post(BASE+"/preview", json=data, headers=headers).status_code == 409
    changed = {**data, "variables": {**data["variables"], "program": "Other"}}
    assert client.post(BASE+"/issue", json=changed, headers=headers).status_code == 409
    fresh = {**data, "template_version": template.version, "request_key": str(uuid4())}
    assert client.post(BASE+"/issue", json=fresh, headers=headers).json()["recipient_name"] == "Changed Rao"


def test_certificate_one_page_and_revocation(client, db, studio):
    headers, *_ = studio
    data = payload(studio, "Certificate of Completion")
    preview = client.post(BASE+"/preview", json=data, headers=headers)
    assert preview.status_code == 200, preview.text
    assert len(PdfReader(BytesIO(preview.content)).pages) == 1
    item = client.post(BASE+"/issue", json=data, headers=headers)
    assert item.status_code == 201, item.text
    identity = item.json()["id"]
    assert client.post(f"{BASE}/issued/{identity}/revoke", json={"reason": "Incorrect program details"}, headers=headers).status_code == 200
    assert "REVOKED" in pdf_text(client.get(f"{BASE}/issued/{identity}/pdf", headers=headers))


def test_template_safety_and_required_values(client, db, studio):
    headers, _, templates, _ = studio
    template = templates[0].copy()
    template.pop("id")
    for body in ("{{recipient.password}}", "{{custom.__class__}}", "{% for x in values %}", "{{recipient.name.__class__}}"):
        template["body"] = body
        assert client.post(BASE+"/templates", json=template, headers=headers).status_code == 422
    data = payload(studio)
    data["variables"]["recipient.name"] = "Forged name"
    assert client.post(BASE+"/preview", json=data, headers=headers).status_code == 422
    data = payload(studio)
    data["variables"]["program"] = ""
    assert client.post(BASE+"/issue", json=data, headers=headers).status_code == 422
    data = payload(studio, "Experience Letter")
    data["variables"] = {"remarks": "Excellent work"}
    assert "Missing database values" in client.post(BASE+"/issue", json=data, headers=headers).json()["detail"]
    assert db.query(StudioDocument).count() == 0


def test_tenant_isolation_assets_and_applicant_data(client, db, studio):
    headers, _, _, head = studio
    other = Company(id=2, name="Other organization")
    db.add(other); db.flush()
    branch = Branch(name="Other", company_id=2)
    db.add(branch); db.flush()
    employee = Employee(employee_id="DOC-002", first_name="Other", last_name="Tenant", branch_id=branch.id, date_of_joining=date(2026,1,1))
    db.add(employee)
    application = InternApplication(organization_id=1, reference="APP-DOC-1", full_name="Applicant Test", email="applicantdoc@example.com", password_hash="secret-password", identity_number_encrypted="secret-identity", identity_last4="1234", details={"college":"Example College", "degree":"BTech", "passout_year":2029})
    foreign = StudioAsset(organization_id=2, kind="logo", name="Other", content_type="image/png", content=b"private", sha256="0"*64)
    db.add_all([application, foreign]); db.commit()
    data = payload(studio); data["recipient_id"] = employee.id
    assert client.post(BASE+"/preview", json=data, headers=headers).status_code == 404
    assert "Other Tenant" not in str(client.get(BASE+"/recipients", headers=headers).json())
    assert client.get(f"{BASE}/assets/{foreign.id}", headers=headers).status_code == 404
    updated = {**head, "logo_asset_id":foreign.id}; updated.pop("id")
    assert client.put(f"{BASE}/letterheads/{head['id']}", json=updated, headers=headers).status_code == 404
    data = payload(studio); data.update(recipient_type="application", recipient_id=application.id)
    text = pdf_text(client.post(BASE+"/preview", json=data, headers=headers))
    assert "Applicant Test" in text and "secret" not in text


def test_image_validation_and_optimistic_edits(client, studio):
    headers, _, templates, head = studio
    invalid = client.post(BASE+"/assets?kind=logo", headers=headers, files={"file":("bad.png",b"not-image","image/png")})
    assert invalid.status_code == 422
    image = BytesIO(); Image.new("RGB",(100,50),"blue").save(image,format="PNG")
    asset = client.post(BASE+"/assets?kind=logo", headers=headers, files={"file":("logo.png",image.getvalue(),"image/png")})
    assert asset.status_code == 201, asset.text
    data = {**head, "logo_asset_id":asset.json()["id"]}; data.pop("id")
    result = client.put(f"{BASE}/letterheads/{head['id']}", json=data, headers=headers)
    assert result.status_code == 200 and result.json()["version"] == 2
    assert client.put(f"{BASE}/letterheads/{head['id']}", json=data, headers=headers).status_code == 409
    template = templates[0].copy(); identity = template.pop("id")
    assert client.put(f"{BASE}/templates/{identity}", json=template, headers=headers).json()["version"] == 2
    assert client.put(f"{BASE}/templates/{identity}", json=template, headers=headers).status_code == 409


def test_company_logo_import_uses_scoped_storage(client, db, studio, monkeypatch, tmp_path):
    from app.core.config import settings
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    folder = tmp_path / "company_logos"; folder.mkdir()
    Image.new("RGB", (100, 50), "blue").save(folder / "1_abcdef.png")
    company = db.get(Company, 1); company.logo_url = "/uploads/company_logos/1_abcdef.png"; db.commit()
    headers = studio[0]
    assert client.get(BASE+"/metadata", headers=headers).json()["has_company_logo"]
    result = client.post(BASE+"/company-logo", headers=headers)
    assert result.status_code == 201, result.text
    asset = db.get(StudioAsset, result.json()["id"])
    assert asset.organization_id == 1 and asset.content.startswith(b"\x89PNG")
    for url in ("https://example.com/logo.png", "/uploads/company_logos/2_abcdef.png", "/uploads/../private.png"):
        company.logo_url = url; db.commit()
        assert client.post(BASE+"/company-logo", headers=headers).status_code == 422


def test_full_name_and_academic_placeholders_are_database_backed(client, db, studio):
    from app.models.employee import EmployeeEducation
    headers, employee, templates, _ = studio
    employee.middle_name = "Kumar"
    db.add(EmployeeEducation(employee_id=employee.id, degree="BTech", institution="Example College", pass_year=2029))
    db.commit()
    template = {**templates[0], "name":"Academic Letter", "title":"Academic Letter", "recipient_scope":"both", "custom_fields":[],
        "body":"{{recipient.name}} studies {{recipient.degree}} at {{recipient.college}}. Graduation: {{recipient.graduation_year}}."}
    template.pop("id")
    saved = client.post(BASE+"/templates", json=template, headers=headers)
    assert saved.status_code == 201, saved.text
    data = payload(studio); data.update(template_id=saved.json()["id"], variables={})
    text = pdf_text(client.post(BASE+"/preview", json=data, headers=headers))
    assert "Ananya Kumar Rao studies BTech at Example College. Graduation: 2029." in text


def test_ordinary_user_cannot_issue(client, db, studio):
    from app.core.deps import get_current_user
    from app.main import app
    from app.models.user import User, Role
    role = Role(name="document_viewer")
    db.add(role); db.flush()
    user = User(email="viewer-doc@example.com", hashed_password="unused", is_active=True, is_superuser=False, role_id=role.id)
    db.add(user); db.flush()
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        assert client.post(BASE+"/issue", json=payload(studio), headers=studio[0]).status_code == 403
        assert client.get(BASE+"/templates", headers=studio[0]).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_pdf_letterhead_and_multpage_rendering(client, db, studio):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    headers, _, templates, head = studio
    background = BytesIO()
    page = canvas.Canvas(background, pagesize=A4)
    page.drawString(60, 800, "Official letterhead artwork")
    page.linkURL("https://example.com", (10, 10, 100, 30))
    page.showPage(); page.save()
    uploaded = client.post(BASE+"/assets?kind=background", headers=headers, files={"file":("official.pdf", background.getvalue(), "application/pdf")})
    assert uploaded.status_code == 201, uploaded.text
    asset = db.get(StudioAsset, uploaded.json()["id"])
    assert asset.content_type == "application/pdf"
    assert not PdfReader(BytesIO(asset.content)).pages[0].get("/Annots")
    updates = {**head, "background_asset_id":asset.id, "show_company_header":False}; updates.pop("id")
    saved = client.put(f"{BASE}/letterheads/{head['id']}", json=updates, headers=headers)
    assert saved.status_code == 200
    data = payload(studio); data["letterhead_version"] = saved.json()["version"]
    data["variables"]["remarks"] = "\n\n".join(["<Approved> & verified."] * 40)
    response = client.post(BASE+"/preview", json=data, headers=headers)
    text = pdf_text(response)
    assert "Official letterhead artwork" in text and "<Approved> & verified." in text
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) > 1
    assert all("Official letterhead artwork" in page.extract_text() for page in reader.pages)
    certificate = payload(studio, "Certificate of Completion"); certificate["letterhead_version"] = saved.json()["version"]
    invalid = client.post(BASE+"/preview", json=certificate, headers=headers)
    assert invalid.status_code == 422 and "orientation" in invalid.json()["detail"]


@pytest.mark.parametrize("folder,filename", [("alembic", "20261027_038_document_studio.py"), ("alembic_postgresql", "pg_20261027_038_document_studio.py")])
def test_frozen_migration_round_trip(folder, filename):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import create_engine, MetaData, Table, Column, Integer, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).resolve().parents[1] / folder / "versions" / filename
    spec = importlib.util.spec_from_file_location("studio_migration", path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    metadata = MetaData()
    for name in ("companies", "users"):
        Table(name, metadata, Column("id", Integer, primary_key=True))
    with engine.begin() as connection:
        metadata.create_all(connection)
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade(); migration.upgrade()
        tables = set(inspect(connection).get_table_names())
        assert {"document_studio_assets", "document_studio_letterheads", "document_studio_templates", "document_studio_documents"} <= tables
        migration.downgrade()
        assert set(inspect(connection).get_table_names()) == {"companies", "users"}
        migration.upgrade()
        assert "document_studio_documents" in inspect(connection).get_table_names()
    engine.dispose()
