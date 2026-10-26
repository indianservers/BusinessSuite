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


def test_nested_folders_cycles_and_owner_isolation(db, notes_client):
    c, owner, admin, actor = notes_client
    root = c.post("/note-folders", json={"name": "Personal"}).json()
    child = c.post("/note-folders", json={"name": "Ideas", "parent_id": root["id"]}).json()
    moved = c.put(f'/note-folders/{root["id"]}', json={**{k:v for k,v in root.items() if k != "id"}, "parent_id": child["id"]})
    assert moved.status_code == 422
    note = c.post("/notes", json={"title": "Nested", "folder_id": child["id"], "favorite": True}).json()
    assert c.get("/notes", params={"folder_id": child["id"]}).json()[0]["id"] == note["id"]
    assert c.get("/notes", params={"view": "favorites"}).json()[0]["id"] == note["id"]
    assert c.request("DELETE",f'/note-folders/{root["id"]}',json={"version":1}).status_code == 409
    actor[0] = admin
    assert c.get("/note-folders").json() == []
    assert c.post("/notes",json={"folder_id":child["id"]}).status_code == 404
    assert c.get("/notes",params={"folder_id":child["id"]}).status_code == 404


def test_explicit_sharing_is_read_only_revocable_and_hides_trashed_notes(notes_client):
    c, owner, admin, actor = notes_client
    note = c.post("/notes",json={"title":"Explicit sharing", "content":"Only invited readers"}).json()
    assert c.post(f'/notes/{note["id"]}/shares',json={"email":admin.email,"version":1}).status_code == 200
    actor[0] = admin
    shared = c.get("/notes",params={"view":"shared"}).json()
    assert shared[0]["can_edit"] is False
    assert c.get(f'/notes/{note["id"]}').json()["content"] == "Only invited readers"
    assert c.put(f'/notes/{note["id"]}',json={"version":1,"title":"Edit"}).status_code == 404
    actor[0] = owner
    assert c.delete(f'/notes/{note["id"]}/shares/{admin.id}').status_code == 200
    actor[0] = admin
    assert c.get(f'/notes/{note["id"]}').status_code == 404


def test_bulk_conflict_is_atomic_and_trash_remains_recoverable(notes_client):
    c, *_ = notes_client
    notes=[c.post("/notes",json={"title":title}).json() for title in ["One","Two"]]
    payload={"action":"trash", "items":[{"id":notes[0]["id"],"version":1},{"id":notes[1]["id"],"version":99}]}
    assert c.post("/note-actions/bulk",json=payload).status_code == 409
    assert len(c.get("/notes").json()) == 2
    payload["items"][1]["version"]=1
    assert c.post("/note-actions/bulk",json=payload).json()["updated"] == 2
    assert len(c.get("/notes",params={"view":"trash"}).json()) == 2
    assert c.get("/notes").json() == []
    assert c.post(f'/notes/{notes[0]["id"]}/restore',json={"version":2}).status_code == 200


def test_pdf_export_and_duplicate_keep_private_notes(notes_client):
    c, owner, admin, actor = notes_client
    note=c.post("/notes",json={"title":"PDF","content":"A **legacy** note"}).json()
    assert c.get(f'/notes/{note["id"]}/export.pdf').content.startswith(b"%PDF")
    copy=c.post(f'/notes/{note["id"]}/duplicate').json()
    assert copy["content"] == note["content"] and copy["id"] != note["id"]
    assert copy["visibility"] == "private"
    actor[0]=admin
    assert c.get(f'/notes/{note["id"]}/export.pdf').status_code == 404


def test_inline_image_references_never_store_remote_sources(notes_client):
    c,*_=notes_client
    body='<!--suite-richtext:v1--><p data-note-image="12" onclick="bad()">Screenshot</p><img src="https://tracker.invalid/image"><script>alert(1)</script>'
    note=c.post("/notes",json={"content":body}).json()
    assert 'data-note-image="12"' in note["content"]
    assert 'onclick' not in note["content"] and '<img' not in note["content"] and '<script' not in note["content"]

def test_folder_drag_reorder_is_atomic_owned_and_cycle_safe(notes_client):
    c, owner, admin, actor = notes_client
    a=c.post('/note-folders',json={'name':'First'}).json()
    b=c.post('/note-folders',json={'name':'Second'}).json()
    child=c.post('/note-folders',json={'name':'Child','parent_id':a['id']}).json()
    path=f'/note-folders/{b["id"]}/move'
    assert c.post(path,json={'version':b['version'],'target_id':a['id'],'placement':'before'}).status_code==200
    roots=[row for row in c.get('/note-folders').json() if row['parent_id'] is None]
    assert [row['id'] for row in roots]==[b['id'],a['id']]
    current=next(row for row in roots if row['id']==a['id'])
    assert c.post(f'/note-folders/{a["id"]}/move',json={'version':current['version'],'target_id':child['id'],'placement':'inside'}).status_code==422
    assert c.post(path,json={'version':1,'target_id':a['id'],'placement':'inside'}).status_code==409
    actor[0]=admin
    assert c.post(path,json={'version':2,'target_id':a['id'],'placement':'inside'}).status_code==404

@pytest.mark.parametrize('action', ['move', 'archive', 'trash', 'unarchive', 'restore'])
def test_management_undo_restores_metadata_without_replacing_content(notes_client, action):
    c, owner, admin, actor = notes_client
    source=c.post('/note-folders',json={'name':'Source'}).json()
    target=c.post('/note-folders',json={'name':'Target'}).json()
    before=c.post('/notes',json={'title':'Keep title','content':'Keep my private content','folder_id':source['id'],'archived':action=='unarchive'}).json()
    if action=='restore':
        c.request('DELETE',f'/notes/{before["id"]}',json={'version':before['version']})
        before=c.get(f'/notes/{before["id"]}').json()
    payload={'action':action,'items':[{'id':before['id'],'version':before['version']}]}
    if action=='move':payload.update(folder_id=target['id'])
    changed=c.post('/note-actions/bulk',json=payload)
    assert changed.status_code==200
    expected_version=changed.json()['items'][0]['version']
    assert expected_version==before['version']+1
    undo={'id':before['id'],'version':expected_version,'project_id':before['project_id'],'task_id':before['task_id'],'folder_id':before['folder_id'],'archived':before['archived'],'trashed':bool(before['deleted_at'])}
    assert c.post('/note-actions/undo',json={'items':[undo]}).status_code==200
    after=c.get(f'/notes/{before["id"]}').json()
    for key in ['title','content','folder_id','project_id','task_id','archived']:assert after[key]==before[key]
    assert bool(after['deleted_at'])==bool(before['deleted_at'])
    assert after['version']==expected_version+1


def test_management_undo_conflicts_are_atomic_and_readers_cannot_undo(notes_client):
    c, owner, admin, actor = notes_client
    notes=[c.post('/notes',json={'title':title,'content':'Original'}).json() for title in ['One','Two']]
    assert c.post('/note-actions/bulk',json={'action':'archive','items':[{'id':n['id'],'version':1} for n in notes]}).status_code==200
    items=[{'id':n['id'],'version':2,'archived':False,'trashed':False} for n in notes]
    actor[0]=admin
    assert c.post('/note-actions/undo',json={'items':items}).status_code==404
    actor[0]=owner
    assert c.put(f'/notes/{notes[1]["id"]}',json={'version':2,'title':'New title','content':'Newer content','archived':True}).status_code==200
    assert c.post('/note-actions/undo',json={'items':items}).status_code==409
    assert all(c.get(f'/notes/{n["id"]}').json()['archived'] for n in notes)
    assert c.get(f'/notes/{notes[1]["id"]}').json()['content']=='Newer content'
    assert c.post('/note-actions/undo',json={'items':[items[0],items[0]]}).status_code==422


def test_management_undo_rejects_foreign_folder_and_arbitrary_fields(notes_client):
    c, owner, admin, actor = notes_client
    note=c.post('/notes',json={'title':'Private'}).json()
    actor[0]=admin
    folder=c.post('/note-folders',json={'name':'Foreign'}).json()
    actor[0]=owner
    item={'id':note['id'],'version':1,'archived':False,'trashed':False,'folder_id':folder['id']}
    assert c.post('/note-actions/undo',json={'items':[item]}).status_code==404
    item.pop('folder_id');item['content']='Overwrite attempt'
    assert c.post('/note-actions/undo',json={'items':[item]}).status_code==422
    assert c.get(f'/notes/{note["id"]}').json()['version']==1
