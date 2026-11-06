import pytest

from app.apps.crm.template_studio import RenderInput, TemplateInput, render


def template(module="lead", category="email"):
    return {
        "name": "Original gallery design", "category": category,
        "document_type": "email" if category == "email" else "letter", "module": module,
        "subject": "An update for {{company}}", "folder": "Gallery", "status": "draft",
        "design": {"blocks": [{"id": "heading", "type": "heading", "text": "Hello {{name}}"}]},
    }


@pytest.fixture
def gallery_headers(db, superuser_headers):
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    attach_test_identity(db, db.query(User).filter_by(email="testadmin@test.com").one())
    db.commit()
    return superuser_headers


@pytest.mark.parametrize("module", ["lead", "contact", "account", "deal", "quotation", "task", "meeting", "call", "campaign", "ticket"])
def test_gallery_modules_round_trip(client, gallery_headers, module):
    saved = client.post("/api/v1/crm/template-studio/templates", headers=gallery_headers, json=template(module))
    assert saved.status_code == 201, saved.text
    assert saved.json()["module"] == module
    listed = client.get("/api/v1/crm/template-studio/templates", headers=gallery_headers)
    assert any(row["id"] == saved.json()["id"] and row["module"] == module for row in listed.json()["items"])


def test_gallery_merge_new_module_keeps_visibility_guard(client, db, gallery_headers):
    created = client.post("/api/v1/crm/tasks", headers=gallery_headers, json={"title": "Review delivery evidence"})
    assert created.status_code == 201, created.text
    saved = client.post("/api/v1/crm/template-studio/templates", headers=gallery_headers, json=template("task", "mail_merge"))
    assert saved.status_code == 201, saved.text
    endpoint = f"/api/v1/crm/template-studio/templates/{saved.json()['id']}/merge"
    response = client.post(endpoint, headers=gallery_headers, json={"entity": "tasks", "record_ids": [created.json()["id"]]})
    assert response.status_code == 200, response.text
    assert "Review delivery evidence" in response.json()["items"][0]["body"]
    assert client.post(endpoint, headers=gallery_headers, json={"entity": "contacts", "record_ids": [created.json()["id"]]}).status_code == 422
    from app.apps.crm.models import CRMTask
    task = db.get(CRMTask, created.json()["id"])
    task.organization_id = 987654
    db.commit()
    assert client.post(endpoint, headers=gallery_headers, json={"entity": "tasks", "record_ids": [task.id]}).status_code == 404


def test_gallery_personalization_escapes_values_and_tracks_missing_fields():
    data = template()
    result = render(RenderInput(template=TemplateInput.model_validate(data), values={"name": '<img src=x onerror=alert(1)>'}))
    assert '<img src=x' not in result["body"]
    assert '&lt;img' in result["body"]
    assert result["unresolved"] == ["company"]
