from pathlib import Path
from tests.test_serverless_deployment import private_storage  # noqa: F401
from app.core.security import create_access_token
from app.models.user import User
from app.apps.project_management.models import PMSWorkspaceMember
from app.apps.project_management.event_feed import append_event

BASE = "/api/v1/project-management"


def test_private_task_attachment_survives_instance_loss_and_preserves_permissions(client, db, superuser_headers, private_storage, monkeypatch):
    import app.apps.project_management.api.router as routes
    monkeypatch.setattr(routes, "PMS_UPLOAD_ROOT", private_storage / "pms")
    project = client.post(BASE + "/projects", headers=superuser_headers, json={"name": "Cloud files", "project_key": "CFILE"})
    assert project.status_code == 200, project.text
    task = client.post(f"{BASE}/projects/{project.json()['id']}/tasks", headers=superuser_headers,
                       json={"title": "Cloud attachment", "task_key": "CFILE-1"})
    assert task.status_code == 200, task.text
    uploaded = client.post(f"{BASE}/tasks/{task.json()['id']}/attachments", headers=superuser_headers,
                           files={"file": ("scope.pdf", b"private scope", "application/pdf")})
    assert uploaded.status_code == 201, uploaded.text
    Path(uploaded.json()["storage_path"]).unlink()
    file_id = uploaded.json()["id"]
    download = client.get(f"{BASE}/attachments/{file_id}/download", headers=superuser_headers, follow_redirects=False)
    assert download.status_code == 307
    assert "/api/v1/files/blob?token=" in download.headers["location"]
    outsider = User(email="cloud-file-outsider@test.local", hashed_password="unused", is_active=True)
    db.add(outsider)
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(str(outsider.id))}
    denied = client.get(f"{BASE}/attachments/{file_id}/download", headers=headers, follow_redirects=False)
    assert denied.status_code == 403


def test_event_endpoint_rechecks_membership_after_removal(client, db, superuser_headers):
    workspace = client.post(BASE + "/workspaces", headers=superuser_headers, json={"name": "Feed scope"}).json()
    project = client.post(BASE + "/projects", headers=superuser_headers,
                         json={"name": "Scoped feed", "project_key": "FEEDS", "workspace_id": workspace["id"]}).json()
    teammate = User(email="feed-member@test.local", hashed_password="unused", is_active=True)
    db.add(teammate)
    db.flush()
    membership = PMSWorkspaceMember(workspace_id=workspace["id"], user_id=teammate.id, role="Member")
    db.add(membership)
    db.commit()
    headers = {"Authorization": "Bearer " + create_access_token(str(teammate.id))}
    append_event(db, {"type": "task.updated", "projectId": project["id"], "taskId": 123})
    events = client.get(BASE + "/realtime/events?cursor=0", headers=headers)
    assert events.status_code == 200, events.text
    assert any(event["taskId"] == 123 for event in events.json()["events"])
    db.delete(membership)
    db.commit()
    assert client.get(BASE + "/realtime/events?cursor=0", headers=headers).json()["events"] == []
