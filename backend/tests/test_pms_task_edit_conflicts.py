from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workflow_schemes import task


def test_task_edit_precondition_rejects_stale_write_and_allows_reviewed_retry(client, db):
    _, pid, _, _, _, _, member_headers, _, guest_headers = setup_workspace(client, db)
    tid = task(client, pid, member_headers)
    url = f"{BASE}/tasks/{tid}"
    initial = client.get(url, headers=member_headers).json()
    token = initial["updated_at"]
    first = client.patch(url, headers=member_headers, json={
        "title": "Other editor's title", "expected_updated_at": token,
    })
    assert first.status_code == 200, first.text
    fresh = first.json()
    assert fresh["updated_at"] != token
    stale = client.patch(url, headers=member_headers, json={
        "title": "Unsaved local draft", "status": "Done", "expected_updated_at": token,
    })
    assert stale.status_code == 409, stale.text
    unchanged = client.get(url, headers=member_headers).json()
    assert unchanged["title"] == "Other editor's title"
    assert unchanged["status"] == initial["status"]
    assert unchanged["updated_at"] == fresh["updated_at"]
    # The token does not grant permission to a read-only member.
    assert client.patch(url, headers=guest_headers, json={
        "title": "Forbidden", "expected_updated_at": fresh["updated_at"],
    }).status_code == 403
    retry = client.patch(url, headers=member_headers, json={
        "title": "Reviewed local draft", "expected_updated_at": fresh["updated_at"],
    })
    assert retry.status_code == 200, retry.text
    assert retry.json()["title"] == "Reviewed local draft"
    assert retry.json()["updated_at"] != fresh["updated_at"]
    # Old API clients remain valid while entry points adopt preconditions.
    assert client.patch(url, headers=member_headers, json={"priority": "Low"}).status_code == 200


def test_explicit_null_precondition_is_not_an_unconditional_update(client, db):
    _, pid, _, _, _, _, headers, _, _ = setup_workspace(client, db)
    tid = task(client, pid, headers)
    url = f"{BASE}/tasks/{tid}"
    assert client.patch(url, headers=headers, json={"title": "Versioned task"}).status_code == 200
    result = client.patch(url, headers=headers, json={"title": "Stale null", "expected_updated_at": None})
    assert result.status_code == 409, result.text
    assert client.get(url, headers=headers).json()["title"] == "Versioned task"
