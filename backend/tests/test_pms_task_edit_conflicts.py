from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workflow_schemes import task


def test_task_edit_precondition_rejects_stale_write_and_allows_reviewed_retry(client, db):
    wid, pid, _, _, _, _, member_headers, _, guest_headers = setup_workspace(client, db)
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
    overview=client.get(f"{BASE}/workspaces/{wid}/overview",headers=member_headers)
    assert overview.status_code==200,overview.text
    assert next(row for row in overview.json()["tasks"] if row["id"]==tid)["updated_at"]==fresh["updated_at"]
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


def test_dates_can_be_cleared_individually_without_bypassing_validation_or_access(client, db):
    _, pid, _, _, _, _, headers, _, guest_headers = setup_workspace(client, db)
    tid = task(client, pid, headers)
    url = f"{BASE}/tasks/{tid}"
    dated=client.patch(url,headers=headers,json={"start_date":"2026-11-13","due_date":"2026-11-16"})
    assert dated.status_code==200,dated.text
    cleared_start=client.patch(url,headers=headers,json={"start_date":None,"expected_updated_at":dated.json()["updated_at"]})
    assert cleared_start.status_code==200,cleared_start.text
    assert cleared_start.json()["start_date"] is None
    assert cleared_start.json()["due_date"]=="2026-11-16"
    cleared_due=client.patch(url,headers=headers,json={"due_date":None,"expected_updated_at":cleared_start.json()["updated_at"]})
    assert cleared_due.status_code==200,cleared_due.text
    assert cleared_due.json()["start_date"] is None and cleared_due.json()["due_date"] is None
    dated=client.patch(url,headers=headers,json={"start_date":"2026-11-13","due_date":"2026-11-16"})
    invalid=client.patch(url,headers=headers,json={"start_date":"2026-11-20","expected_updated_at":dated.json()["updated_at"]})
    assert invalid.status_code==422,invalid.text
    denied=client.patch(url,headers=guest_headers,json={"due_date":None,"expected_updated_at":dated.json()["updated_at"]})
    assert denied.status_code==403,denied.text
    stored=client.get(url,headers=headers).json()
    assert stored["start_date"]=="2026-11-13" and stored["due_date"]=="2026-11-16"
