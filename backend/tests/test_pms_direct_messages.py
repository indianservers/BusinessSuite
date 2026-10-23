from uuid import uuid4
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE
from app.apps.project_management.models import PMSWorkspaceMember


def test_private_messages_scope_retry_and_revoked_access(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    path = f"{BASE}/workspaces/{wid}/direct-conversations"
    created = client.post(path, headers=oh, json={"user_id": member.id})
    assert created.status_code == 200, created.text
    cid = created.json()["id"]
    assert client.post(path, headers=mh, json={"user_id": owner.id}).json()["id"] == cid
    assert client.get(path, headers=ah).json()["conversations"] == []
    messages = path + f"/{cid}/messages"
    assert client.get(messages, headers=ah).status_code == 404
    assert client.get(messages, headers=gh).status_code == 404
    assert client.post(path, headers=gh, json={"user_id": owner.id}).status_code == 403
    assert client.post(path, headers=oh, json={"user_id": guest.id}).status_code == 422
    payload = {"body": "Review the audit", "client_id": str(uuid4())}
    first = client.post(messages, headers=oh, json=payload)
    assert first.status_code == 200, first.text
    retry = client.post(messages, headers=oh, json=payload)
    assert retry.json()["id"] == first.json()["id"]
    assert client.post(messages, headers=oh, json={**payload, "body": "Changed"}).status_code == 409
    history = client.get(messages, headers=mh).json()
    assert len(history["messages"]) == 1 and history["messages"][0]["body"] == payload["body"]
    assert client.post(messages, headers=ah, json={**payload, "client_id": str(uuid4())}).status_code == 404
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other messages"}).json()["id"]
    assert client.get(f"{BASE}/workspaces/{other}/direct-conversations/{cid}/messages", headers=oh).status_code == 404
    membership = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, user_id=member.id).one()
    membership.role = "Guest"
    db.commit()
    assert client.post(messages, headers=mh, json={"body": "Cannot send", "client_id": str(uuid4())}).status_code == 403
    assert client.post(messages, headers=oh, json={"body": "Paused", "client_id": str(uuid4())}).status_code == 403
    db.delete(membership)
    db.commit()
    assert client.get(messages, headers=mh).status_code == 404
