from uuid import uuid4

import pytest

from app.shared.offline_operations import receipts
from tests.test_shared_catalog import ROOT, headers, item
from tests.test_catalog_offerings import config
from tests.test_pms_task_studio import BASE, studio, middleware_database, organization_context


@pytest.mark.parametrize("kind", ["product", "service", "membership"])
def test_catalog_create_and_edit_replay(client, db, headers, kind):
    receipts.create(db.get_bind(), checkfirst=True)
    body = item(kind, **({"plan": config()} if kind == "membership" else {}))
    create_headers = {**headers, "X-Offline-Operation": str(uuid4())}
    created = client.post(ROOT + "/items", json=body, headers=create_headers)
    assert created.status_code == 201, created.text
    assert client.post(ROOT + "/items", json=body, headers=create_headers).json() == created.json()
    saved = created.json()
    path = f"{ROOT}/items/{kind}/{saved['id']}"
    edit_headers = {**headers, "X-Offline-Operation": str(uuid4())}
    patch = {**body, "name": "Changed while offline", "version": saved["version"]}
    updated = client.put(path, json=patch, headers=edit_headers)
    assert updated.status_code == 200, updated.text
    assert client.put(path, json=patch, headers=edit_headers).json() == updated.json()
    assert client.put(path, json={**patch, "name": "Different operation"}, headers=edit_headers).status_code == 409
    current = client.get(path, headers=headers).json()
    assert current["version"] == saved["version"] + 1
    assert current["name"] == "Changed while offline"


def test_task_create_and_status_replay(client, db, studio):
    receipts.create(db.get_bind(), checkfirst=True)
    _, _, _, headers, _, _, project, _, _ = studio
    create_headers = {**headers, "X-Offline-Operation": str(uuid4())}
    path = f"{BASE}/projects/{project['id']}/tasks"
    body = {"title": "Review cycle counts", "task_key": "OFFLINE-01", "status": "To Do"}
    response = client.post(path, json=body, headers=create_headers)
    assert response.status_code == 200, response.text
    created = response.json()
    assert client.post(path, json=body, headers=create_headers).json() == created
    status_headers = {**headers, "X-Offline-Operation": str(uuid4())}
    path = f"{BASE}/tasks/{created['id']}"
    patch = {"status": "In Progress", "expected_updated_at": created["updated_at"]}
    response = client.patch(path, json=patch, headers=status_headers)
    assert response.status_code == 200, response.text
    assert client.patch(path, json=patch, headers=status_headers).json() == response.json()
    assert client.get(path, headers=headers).json()["status"] == "In Progress"


def test_private_note_create_replays_without_duplicate(client, db, studio):
    receipts.create(db.get_bind(), checkfirst=True)
    _, _, _, headers, _, _, _, _, _ = studio
    path = f"{BASE}/notes"
    offline_path = f"{path}/offline-create"
    request_headers = {**headers, "X-Offline-Operation": str(uuid4())}
    body = {"title": "Offline field notes", "content": "Private draft"}
    assert client.post(offline_path, headers=headers, json=body).status_code == 422
    first = client.post(offline_path, headers=request_headers, json=body)
    assert first.status_code == 201, first.text
    replay = client.post(path, headers=request_headers, json=body)
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert client.post(offline_path, headers=request_headers, json={**body, "title": "Another draft"}).status_code == 409
    assert [row["id"] for row in client.get(path, headers=headers, params={"q": body["title"]}).json()] == [first.json()["id"]]
