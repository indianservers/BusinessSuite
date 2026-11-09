from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.file_storage import StorageConnection
from app.models.user import User
from app.apps.project_management.models import PMSNote
from app.services import file_storage_providers as providers
from app.core.rich_text import PREFIX

ROOT = "/api/v1/files-storage/notes"


@pytest.fixture
def note_cloud(client, db, superuser_headers, monkeypatch):
    user = db.query(User).filter_by(email="testadmin@test.com").one()
    account = StorageConnection(organization_id=1, created_by=user.id, provider="google_drive",
                                label="My Drive", account="owner@example.test", connected=True)
    db.add(account)
    db.commit()
    result = client.post("/api/v1/project-management/notes", headers=superuser_headers,
                         json={"title":"Private meeting", "content":PREFIX+"<p><strong>Saved content</strong></p>"})
    assert result.status_code == 201, result.text
    note = db.get(PMSNote, result.json()["id"])
    uploads = []
    monkeypatch.setattr(providers, "folder_info", lambda db, conn, folder: {"id": folder, "name": "Chosen folder"})
    def upload(db, conn, folder, name, body, mime):
        uploads.append({"account": conn.id, "folder": folder, "name": name, "body": body, "mime": mime})
        return "cloud-file"
    monkeypatch.setattr(providers, "upload", upload)
    monkeypatch.setattr(providers, "download", lambda *args: uploads[-1]["body"])
    return user, account, note, uploads, superuser_headers


@pytest.mark.parametrize("provider", ["google_drive", "onedrive"])
@pytest.mark.parametrize("source", ["crm", "project_management"])
@pytest.mark.parametrize("format", ["html", "txt"])
def test_note_copy_preserves_original_and_uses_selected_account(client, db, note_cloud, provider, source, format):
    user, account, note, uploads, headers = note_cloud
    account.provider = provider; db.commit()
    payload = {"source": source, "connection_id": account.id, "folder_id": "selected-folder", "format": format,
               "title": "Browser note", "content": PREFIX+"<p>Browser content</p>"}
    if source == "project_management":
        payload.update(note_id=note.id, note_version=note.version, title="Tampered title", content="Tampered content")
    response = client.post(ROOT+"/save", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["saved"] and response.json()["provider"] == provider
    sent = uploads[0]
    assert sent["account"] == account.id and sent["folder"] == "selected-folder"
    assert (b"Saved content" if source == "project_management" else b"Browser content") in sent["body"]
    assert b"Tampered" not in sent["body"]
    db.refresh(note)
    assert note.title == "Private meeting" and note.version == 1
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize("change", ["other_user", "other_company", "disconnected", "unsupported"])
def test_note_accounts_and_folders_cannot_cross_ownership(client, db, note_cloud, change, monkeypatch):
    user, account, note, uploads, headers = note_cloud
    if change == "other_user": account.created_by = user.id+100
    if change == "other_company": account.organization_id = 2
    if change == "disconnected": account.connected = False
    if change == "unsupported": account.provider = "dropbox"
    db.commit()
    options = client.get(ROOT+"/options", headers=headers)
    assert options.status_code == 200 and options.json()["accounts"] == []
    called = []
    monkeypatch.setattr(providers, "folders", lambda *a: called.append(True))
    assert client.get(ROOT+f"/accounts/{account.id}/folders", headers=headers).status_code == 404
    response = client.post(ROOT+"/save", headers=headers, json={"source":"crm", "connection_id":account.id, "content":"Private"})
    assert response.status_code == 404 and uploads == [] and called == []


@pytest.mark.parametrize("change", ["stale", "trashed", "other_owner", "missing"])
def test_note_copy_rechecks_saved_note_access(client, db, note_cloud, change):
    user, account, note, uploads, headers = note_cloud
    note_id = note.id
    if change == "stale": note.version = 2
    if change == "trashed": note.deleted_at = datetime.now(timezone.utc)
    if change == "other_owner":
        other = User(email="other-owner@example.test", hashed_password=user.hashed_password, is_active=True); db.add(other); db.flush(); note.owner_id = other.id
    if change == "missing": note_id += 10000
    db.commit()
    response = client.post(ROOT+"/save", headers=headers, json={"source":"project_management", "connection_id":account.id, "note_id":note_id, "note_version":1})
    assert response.status_code == (409 if change in {"stale", "trashed"} else 404), response.text
    assert uploads == []


def test_html_export_does_not_execute_untrusted_content(client, note_cloud):
    _, account, _, uploads, headers = note_cloud
    response = client.post(ROOT+"/save", headers=headers, json={"source":"crm", "connection_id":account.id,
        "title":"<script>title</script>", "content":PREFIX+'<p onclick="evil()">Hello<script>alert(1)</script><a href="javascript:evil()">link</a></p>'})
    assert response.status_code == 200, response.text
    html = uploads[0]["body"].decode()
    assert '<script>' not in html and 'onclick=' not in html and 'javascript:' not in html
    assert "Content-Security-Policy" in html and "&lt;script&gt;title&lt;/script&gt;" in html


def test_cloud_verification_failure_never_changes_original(client, db, note_cloud, monkeypatch):
    _, account, note, _, headers = note_cloud
    monkeypatch.setattr(providers, "download", lambda *a: b"wrong bytes")
    response = client.post(ROOT+"/save", headers=headers, json={"source":"project_management", "connection_id":account.id, "note_id":note.id, "note_version":1})
    assert response.status_code == 502 and "original note is unchanged" in response.json()["detail"]
    db.refresh(note); assert note.version == 1


def test_note_cloud_requires_authentication_and_export_permission(client):
    assert client.get(ROOT+"/options").status_code in {401,403}
    from app.api.v1.note_cloud import note_company
    user = SimpleNamespace(is_superuser=False, _suite_grants={"crm":{"enabled":True,"actions":["view"]}})
    with pytest.raises(HTTPException) as failure: note_company(user, "crm")
    assert failure.value.status_code == 403


def test_folder_results_expose_no_tokens(client, note_cloud, monkeypatch):
    _, account, _, _, headers = note_cloud
    monkeypatch.setattr(providers, "folders", lambda *a: {"items":[{"id":"folder","name":"Notes"}],"cursor":None})
    response = client.get(ROOT+f"/accounts/{account.id}/folders", headers=headers)
    assert response.status_code == 200 and response.json()["items"][0]["name"] == "Notes"
    data = client.get(ROOT+"/options", headers=headers).json()["accounts"][0]
    assert set(data) == {"id","provider","account"}
