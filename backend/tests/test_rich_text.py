import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from app.core.rich_text import PREFIX, sanitize_rich_text, rich_text_plain, rich_text_type, sanitize_tree
from app.core.middleware.rich_text import RichTextMiddleware


@pytest.mark.parametrize("payload", [
    '<p onclick="alert(1)">Safe</p><script>alert(1)</script>',
    '<a href="javascript:alert(1)">Bad link</a>',
    '<a href="jav&#x61;script:alert(1)">Encoded</a>',
    '<svg onload="alert(1)"><a href="data:text/html,bad">SVG</a></svg>',
    '<iframe src="https://evil.invalid"></iframe><object data="https://evil.invalid"></object>',
    '<span style="color:red;background-image:url(javascript:alert(1));position:fixed">Text</span>',
    '<img src=x onerror="alert(1)"><input type="text" value="fake-password">',
])
def test_active_content_cannot_survive(payload):
    safe = sanitize_rich_text(PREFIX + payload)
    for forbidden in ("<script", "onclick", "onerror", "onload", "javascript:", "data:text", "<iframe", "<object", "<svg", "<img", "position:", "background-image", '<input type="text"'):
        assert forbidden not in safe.lower()
    assert sanitize_rich_text(safe) == safe


def test_supported_formatting_tables_and_controlled_styles_survive():
    value = PREFIX + '<h2>Heading</h2><p style="text-align:center"><span style="font-family:Georgia;font-size:24px;color:#123456">Text</span><strong>Bold</strong><u>Underlined</u></p><ol><li>Nested<ul><li>Child</li></ul></li></ol><table><tr><th>Header</th></tr><tr><td>Cell</td></tr></table>'
    safe = sanitize_rich_text(value)
    assert '<strong>Bold</strong>' in safe and '<table>' in safe
    assert 'font-family: Georgia' in safe and 'font-size: 24px' in safe
    assert 'text-align: center' in safe
    assert 'Heading' in rich_text_plain(safe) and 'Cell' in rich_text_plain(safe)


def test_legacy_content_and_credentials_are_not_reinterpreted():
    legacy = '**bold**\n\n`a ** b`\n\nhttps://example.com/a*b\n  literal *'
    assert sanitize_rich_text(legacy) == legacy
    assert rich_text_plain(legacy) == legacy
    assert sanitize_tree({"password": PREFIX + "<b>secret</b>"})["password"] == PREFIX + "<b>secret</b>"


@pytest.mark.parametrize("html", ["<p></p>", "<p><br></p>", "<p>&nbsp; </p>", "<div></div>"])
def test_visually_empty_is_empty(html):
    assert sanitize_rich_text(PREFIX + html) == ""


def test_bounds_measure_text_not_markup():
    class Input(BaseModel):
        body: rich_text_type(5, 1)
    assert Input(body=PREFIX + '<p><strong>Hello</strong></p>').body.startswith(PREFIX)
    with pytest.raises(ValidationError):
        Input(body=PREFIX + '<p>Hello!</p>')
    with pytest.raises(ValidationError):
        Input(body=PREFIX + '<p><br></p>')


def test_http_sanitization_occurs_before_endpoint_storage():
    app = FastAPI()
    app.add_middleware(RichTextMiddleware)
    stored = {}
    @app.post("/content")
    def save(data: dict):
        stored.update(data)
        return data
    with TestClient(app) as client:
        response = client.post('/content', json={"description": PREFIX + '<p><strong>Safe</strong><a href="javascript:evil()">link</a></p>'})
        assert response.status_code == 200
        assert '<strong>Safe</strong>' in stored['description']
        assert 'javascript:' not in stored['description']
        assert response.json() == stored


def test_pdf_supported_formatting_has_no_editor_source():
    from app.core.rich_text import rich_text_pdf_markup
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    html = rich_text_pdf_markup(PREFIX + '<h2>Title</h2><p><strong>Bold</strong> and <u>underline</u></p><ul><li>First</li></ul>')
    assert '<b>Bold</b>' in html and '<u>underline</u>' in html
    assert PREFIX not in html
    assert Paragraph(html, getSampleStyleSheet()['Normal']).getPlainText()


def test_email_parts_and_template_storage_are_safe():
    from app.core.rich_text import email_body_parts
    from app.apps.communication.schemas import EmailTemplatePayload
    value = '<p><strong>Hello</strong><a href="javascript:bad()">link</a></p>'
    template = EmailTemplatePayload(name="Safe template", subject="Hello", body_html=value)
    assert template.body_html.startswith(PREFIX)
    assert 'javascript:' not in template.body_html
    plain, formatted = email_body_parts(template.body_html)
    assert plain == 'Hellolink'
    assert '<strong>Hello</strong>' in formatted and PREFIX not in formatted
    assert email_body_parts('literal < & >')[1] == 'literal &lt; &amp; &gt;'


def test_code_and_literal_punctuation_survive_sanitization():
    value = PREFIX + '<pre><code>a ** b\n&lt;script&gt;literal&lt;/script&gt;</code></pre>'
    safe = sanitize_rich_text(value)
    assert 'a ** b' in safe and '&lt;script&gt;' in safe
    assert rich_text_plain(safe) == 'a ** b\n<script>literal</script>'


def test_document_save_reload_conflict_and_revisions(db, notes_client):
    from app.apps.project_management.documents import router
    from app.apps.project_management.models import PMSWorkspace, PMSWorkspaceMember, PMSProject
    from app.models.user import User
    client, owner, _, actor = notes_client
    client.app.include_router(router)
    workspace = PMSWorkspace(name='Formatted document workspace')
    db.add(workspace); db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role='Owner'))
    project = PMSProject(name='Rich documents', project_key='RTE', workspace_id=workspace.id)
    db.add(project); db.commit()
    first = PREFIX + '<h2>Document</h2><p><strong>First version</strong></p>'
    created = client.post(f'/projects/{project.id}/docs', json={'title':'Rich document','content':first})
    assert created.status_code == 201, created.text
    path = f'/docs/{created.json()["id"]}'
    update = {'title':'Rich document','content':PREFIX + '<p><em>Second version</em></p>','version':1}
    saved = client.put(path, json=update)
    assert saved.status_code == 200, saved.text
    assert client.put(path, json=update).status_code == 409
    assert '<em>Second version</em>' in client.get(path).json()['content']
    assert '<strong>First version</strong>' in client.get(path+'/revisions/1').json()['content']
    outsider = User(email='document-outsider@audit.invalid',hashed_password='unused',is_active=True)
    db.add(outsider); db.commit(); actor[0] = outsider
    assert client.get(path).status_code in (403,404)


def test_note_save_reload_and_revision_preserve_formatting(notes_client):
    client, owner, admin, actor = notes_client
    body = PREFIX + '<p><strong>Saved formatting</strong><u>Underline</u></p><table><tr><th>Header</th></tr></table>'
    response = client.post('/notes', json={"title":"Formatted note", "content":body})
    assert response.status_code in (200, 201), response.text
    row = response.json()
    assert '<strong>Saved formatting</strong>' in row['content']
    assert client.get(f'/notes/{row["id"]}').json()['content'] == row['content']
    actor[0] = admin
    assert client.get(f'/notes/{row["id"]}').status_code == 404


# Import only the existing isolated-note fixtures, never production connections.
from tests.test_pms_private_notes import db, notes_client
