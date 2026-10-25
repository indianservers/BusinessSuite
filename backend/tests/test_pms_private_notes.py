"""Exercise the real HTTP contract and private-note authorization boundary."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.base_class import Base
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.apps.project_management.models import PMSProject, PMSWorkspace, PMSWorkspaceMember, PMSTask
from app.apps.project_management.notes import router
from app.apps.project_management.note_actions import router as actions_router
from app.apps.project_management.recovery import workspace_export


@pytest.fixture
def db():
    # Real per-request commit/rollback behavior, independent of the suite's outer transaction.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def notes_client(db):
    owner = User(email="note-owner@audit.invalid", hashed_password="unused", is_active=True)
    admin = User(email="note-admin@audit.invalid", hashed_password="unused", is_active=True, is_superuser=True)
    db.add_all([owner, admin]); db.commit()
    app = FastAPI(); app.include_router(router); app.include_router(actions_router)
    app.dependency_overrides[get_db] = lambda: db
    actor = [owner]
    app.dependency_overrides[get_current_user] = lambda: actor[0]
    with TestClient(app) as client:
        yield client, owner, admin, actor


def test_owner_only_all_operations_including_admin(db, notes_client):
    c, owner, admin, actor = notes_client
    note = c.post("/notes", json={"title": "Secret", "content": "private marker", "tags": [" Ideas "]}).json()
    assert c.get(f'/notes/{note["id"]}').headers["cache-control"] == "private, no-store"
    assert note["tags"] == ["ideas"]
    assert c.get("/notes", params={"q": "private marker"}).json()[0]["id"] == note["id"]
    assert "content" not in c.get("/notes").json()[0]
    actor[0] = admin
    assert c.get("/notes").json() == []
    assert c.get("/notes", params={"q": "private marker", "view": "trash"}).json() == []
    for method, path, payload in [
        ("GET", f'/notes/{note["id"]}', None),
        ("PUT", f'/notes/{note["id"]}', {"title": "Steal", "version": 1}),
        ("DELETE", f'/notes/{note["id"]}', {"version": 1}),
        ("POST", f'/notes/{note["id"]}/restore', {"version": 1}),
        ("GET", f'/notes/{note["id"]}/revisions', None),
        ("GET", f'/notes/{note["id"]}/revisions/1', None),
    ]:
        assert c.request(method, path, **({"json": payload} if payload else {})).status_code == 404
    actor[0] = owner
    assert c.get(f'/notes/{note["id"]}').json()["content"] == "private marker"
    assert c.post("/notes", json={"title": "Injected", "owner_id": admin.id}).status_code == 422


def test_save_conflict_revisions_archive_and_trash(notes_client):
    c, *_ = notes_client
    note = c.post("/notes", json={"content": "First draft"}).json(); path = f'/notes/{note["id"]}'
    assert note["title"] == "Untitled note"
    update = {"title": "Second", "content": "Second draft", "version": 1, "pinned": True, "tags": ["work"]}
    assert c.put(path, json=update).status_code == 200
    assert c.put(path, json=update).status_code == 409
    assert c.get(path).json()["content"] == "Second draft"
    assert len(c.get(path + "/revisions").json()) == 2
    assert c.get(path + "/revisions/1").json()["content"] == "First draft"
    assert len(c.get("/notes", params={"view": "pinned", "tag": "work"}).json()) == 1
    assert c.put(path, json={**update, "version": 2, "archived": True}).status_code == 200
    assert c.get("/notes").json() == []
    assert len(c.get("/notes", params={"view": "archive"}).json()) == 1
    assert c.request("DELETE", path, json={"version": 2}).status_code == 409
    assert c.request("DELETE", path, json={"version": 3}).status_code == 200
    assert c.put(path, json={**update, "version": 4}).status_code == 409
    assert len(c.get("/notes", params={"view": "trash"}).json()) == 1
    assert c.post(path + "/restore", json={"version": 4}).status_code == 200
    assert c.get(path).json()["content"] == "Second draft"


def test_project_links_do_not_share_or_export_notes(db, notes_client):
    c, owner, admin, actor = notes_client
    workspace = PMSWorkspace(name="Notes privacy workspace"); db.add(workspace); db.flush()
    db.add_all([PMSWorkspaceMember(workspace_id=workspace.id, user_id=u.id, role="Owner") for u in [owner, admin]])
    project = PMSProject(name="Note project", project_key="NTP", workspace_id=workspace.id)
    other = PMSProject(name="Other project", project_key="NTO", workspace_id=workspace.id)
    db.add_all([project, other]); db.flush()
    task = PMSTask(title="Linked task", task_key="NTP-1", project_id=project.id)
    db.add(task); db.commit()
    assert c.post("/notes", json={"task_id": task.id}).status_code == 422
    assert c.post("/notes", json={"project_id": other.id, "task_id": task.id}).status_code == 422
    note = c.post("/notes", json={"title": "Private linked note", "project_id": project.id, "task_id": task.id}).json()
    assert note["project_name"] == project.name
    assert note["project_kind"] == "project" and note["visibility"] == "private"
    assert c.get("/notes", params={"personal": True}).json() == []
    assert c.get("/notes", params={"project_id": project.id}).json()[0]["id"] == note["id"]
    actor[0] = admin
    assert c.get("/notes", params={"project_id": project.id}).json() == []
    assert c.get(f'/notes/{note["id"]}').status_code == 404
    exported = workspace_export(db, workspace.id)
    assert "pms_private_notes" not in str(exported)
    assert "Private linked note" not in str(exported)
    actor[0] = owner
    db.query(PMSWorkspaceMember).filter_by(workspace_id=workspace.id, user_id=owner.id).delete(); db.commit()
    data = c.get(f'/notes/{note["id"]}').json()
    assert data["project_name"] == "Unavailable project" and data["task_title"] is None
    assert c.put(f'/notes/{note["id"]}', json={"title": "Still mine", "version": 1}).status_code == 200
    assert c.get(f'/notes/{note["id"]}').json()["project_name"] == "Personal"
    assert c.post("/notes", json={"project_id": project.id}).status_code in (403, 404)


def test_unauthenticated_notes_api():
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as c:
        assert c.get("/notes").status_code in (401, 403)


def test_default_personal_project_is_user_specific(notes_client):
    c, owner, admin, actor = notes_client
    personal = c.post("/notes", json={"title": "Default project"}).json()
    assert personal["project_name"] == "Personal"
    assert personal["project_kind"] == "personal"
    assert personal["project_key"] == f"personal:{owner.id}"
    assert personal["visibility"] == "private"
    assert c.get("/notes", params={"personal": True}).json()[0]["project_name"] == "Personal"
    actor[0] = admin
    own = c.post("/notes", json={"title": "Admin personal"}).json()
    assert own["project_key"] == f"personal:{admin.id}"
    assert own["project_key"] != personal["project_key"]
    assert [n["id"] for n in c.get("/notes", params={"personal": True}).json()] == [own["id"]]


def test_private_attachments_download_remove_restore_and_cross_note_isolation(db, notes_client):
    c, owner, admin, actor = notes_client
    note = c.post('/notes', json={'title': 'Private files'}).json()
    other = c.post('/notes', json={'title': 'Different note'}).json()
    path = f'/notes/{note["id"]}/attachments'
    upload = c.post(path, files={'file': ('../../meeting.txt', b'private-file-marker', 'text/html')})
    assert upload.status_code == 201, upload.text
    item = upload.json()
    assert item['filename'] == 'meeting.txt' and item['media_type'] == 'text/plain'
    assert 'body' not in item and 'url' not in item and 'path' not in item
    assert c.get(path).json()['items'][0]['id'] == item['id']
    download = f'{path}/{item["id"]}/download'
    response = c.get(download)
    assert response.content == b'private-file-marker'
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert c.get(f'/notes/{other["id"]}/attachments/{item["id"]}/download').status_code == 404
    actor[0] = admin
    for method, route in [('GET',path), ('GET',download), ('DELETE',f'{path}/{item["id"]}'), ('POST',f'{path}/{item["id"]}/restore')]:
        assert c.request(method, route).status_code == 404
    assert c.post(path, files={'file': ('attack.txt', b'no', 'text/plain')}).status_code == 404
    actor[0] = owner
    assert c.delete(f'{path}/{item["id"]}').status_code == 200
    assert c.get(path).json()['items'] == []
    assert c.get(path).json()['removed_items'][0]['id'] == item['id']
    assert c.get(download).status_code == 404
    assert c.post(f'{path}/{item["id"]}/restore').status_code == 200
    assert c.get(download).content == b'private-file-marker'
    assert c.request('DELETE', f'/notes/{note["id"]}', json={'version': 1}).status_code == 200
    assert c.post(path, files={'file': ('more.txt', b'no', 'text/plain')}).status_code == 409
    assert c.delete(f'{path}/{item["id"]}').status_code == 409
    assert c.get(download).status_code == 200  # owner can still recover their trashed note's files


def test_attachment_type_size_empty_and_quota_validation(db, notes_client, monkeypatch):
    from app.core.config import settings
    from app.apps.project_management.models import PMSNoteAttachment
    c, *_ = notes_client
    note = c.post('/notes', json={}).json(); path = f'/notes/{note["id"]}/attachments'
    for filename, body, status in [('attack.html', b'<script>1</script>', 415), ('vector.svg', b'<svg/>', 415),
                                    ('fake.png', b'<script>1</script>', 415), ('fake.pdf', b'not a pdf', 415),
                                    ('empty.txt', b'', 422), ('binary.txt', b'\xff\xfe', 415)]:
        assert c.post(path, files={'file': (filename, body, 'application/octet-stream')}).status_code == status
    monkeypatch.setattr(settings, 'MAX_UPLOAD_SIZE_MB', 1)
    assert c.post(path, files={'file': ('large.txt', b'x' * (1024 * 1024 + 1), 'text/plain')}).status_code == 413
    assert db.query(PMSNoteAttachment).count() == 0
    for index in range(20):
        db.add(PMSNoteAttachment(note_id=note['id'], filename=f'{index}.txt', media_type='text/plain', body=b'x', size=1))
    db.commit()
    assert c.post(path, files={'file': ('overflow.txt', b'x', 'text/plain')}).status_code == 413


def task_project(db, user):
    workspace = PMSWorkspace(name='Task publication test'); db.add(workspace); db.flush()
    db.add(PMSWorkspaceMember(workspace_id=workspace.id, user_id=user.id, role='Owner'))
    project = PMSProject(name='Reviewed destination', project_key='RVD', workspace_id=workspace.id)
    db.add(project); db.commit()
    return project


def test_note_to_task_only_publishes_reviewed_text_is_idempotent_and_private(db, notes_client):
    from uuid import uuid4
    from app.apps.project_management.models import PMSNoteTaskLink
    c, owner, admin, actor = notes_client
    project = task_project(db, owner)
    note = c.post('/notes', json={'title': 'Secret title never shared', 'content': 'UNAPPROVED PRIVATE BODY'}).json()
    path = f'/notes/{note["id"]}/tasks'
    files = f'/notes/{note["id"]}/attachments'
    c.post(files, files={'file': ('secret.txt', b'UNAPPROVED PRIVATE FILE', 'text/plain')})
    payload = {'project_id': project.id, 'title': 'Approved task title', 'description': 'Approved action only',
               'due_date': '2026-11-01', 'priority': 'High', 'request_key': str(uuid4())}
    assert c.post(path, json=payload).status_code == 422
    assert c.post(path, json={**payload, 'publish_to_project': False}).status_code == 422
    payload['publish_to_project'] = True
    response = c.post(path, json=payload)
    assert response.status_code == 201, response.text
    task = response.json()
    repeat = c.post(path, json=payload)
    assert repeat.status_code == 201 and repeat.json()['id'] == task['id']
    assert db.query(PMSNoteTaskLink).count() == 1 and db.query(PMSTask).count() == 1
    saved = db.get(PMSTask, task['id'])
    assert saved.title == 'Approved task title' and saved.description == 'Approved action only'
    assert saved.priority == 'High' and str(saved.due_date) == '2026-11-01'
    assert c.get(f'/notes/{note["id"]}').json()['project_name'] == 'Personal'
    assert c.get(f'/notes/{note["id"]}').json()['content'] == 'UNAPPROVED PRIVATE BODY'
    assert c.post(path, json={**payload, 'title': 'Different request'}).status_code == 409
    assert c.get(path).json()[0]['id'] == task['id']
    exported = str(workspace_export(db, project.workspace_id))
    for secret in ['UNAPPROVED PRIVATE BODY', 'UNAPPROVED PRIVATE FILE', 'Secret title never shared',
                   'pms_private_note_attachments', 'pms_private_note_task_links']:
        assert secret not in exported
    actor[0] = admin
    assert c.get(path).status_code == 404
    assert c.post(path, json={**payload, 'request_key': str(uuid4())}).status_code == 404
    actor[0] = owner
    db.query(PMSWorkspaceMember).filter_by(user_id=owner.id, workspace_id=project.workspace_id).delete(); db.commit()
    assert c.get(path).json() == []
    assert c.post(path, json=payload).status_code in (403,404)


def test_note_to_task_requires_destination_permissions_and_writable_note(db, notes_client):
    from uuid import uuid4
    c, owner, admin, actor = notes_client
    project = task_project(db, admin)
    note = c.post('/notes', json={}).json(); path = f'/notes/{note["id"]}/tasks'
    payload = {'project_id': project.id, 'title': 'Reviewed task', 'publish_to_project': True, 'request_key': str(uuid4())}
    assert c.post(path, json=payload).status_code in (403,404)
    db.add(PMSWorkspaceMember(workspace_id=project.workspace_id, user_id=owner.id, role='Guest')); db.commit()
    assert c.post(path, json=payload).status_code in (403,404)
    db.query(PMSWorkspaceMember).filter_by(workspace_id=project.workspace_id, user_id=owner.id).update({'role': 'Member'}); db.commit()
    assert c.request('DELETE', f'/notes/{note["id"]}', json={'version': 1}).status_code == 200
    assert c.post(path, json=payload).status_code == 409
    assert db.query(PMSTask).count() == 0


def test_rich_note_excerpt_is_readable_without_changing_stored_content(notes_client):
    c, *_ = notes_client
    content = '# ++==Launch plan==++\n\n**Decision:** keep <u>private</u> files. [Reference](https://example.com)'
    note = c.post('/notes', json={'content': content}).json()
    assert note['preview'] == 'Launch plan Decision: keep private files. Reference'
    assert note['content'] == content
