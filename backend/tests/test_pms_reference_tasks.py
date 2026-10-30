from datetime import date
from tests.test_pms_workspaces import BASE, account, middleware_database
from app.apps.project_management.models import PMSTask, PMSActivity


def test_task_summary_filters_photos_and_activity_share_task_scope(client, db):
    owner, headers = account(db, "reference-owner@test.com", True)
    workspace = client.post(BASE + "/workspaces", headers=headers, json={"name": "Reference layout"}).json()
    project = client.post(BASE + "/projects", headers=headers, json={"name": "Visible work", "project_key": "REF", "workspace_id": workspace["id"]}).json()
    ids = []
    for title, status, due in [("Active", "In Progress", "2026-10-31"), ("Late", "To Do", "2026-10-30"), ("Finished", "Done", "2026-10-29"), ("Cancelled", "Cancelled", "2026-10-28")]:
        response = client.post(f"{BASE}/projects/{project['id']}/tasks", headers=headers, json={"title": title, "task_key": "REF-" + title, "status": status, "due_date": due, "assignee_user_id": owner.id})
        assert response.status_code == 200, response.text
        ids.append(response.json()["id"])
    owner.person.profile.profile_photo_url = "/uploads/reference-avatar.png"
    deleted = PMSTask(project_id=project["id"], title="Deleted overdue", task_key="REF-DEL", status="To Do", due_date=date(2026, 1, 1), deleted_at=__import__("datetime").datetime.now())
    db.add(deleted)
    db.commit()
    response = client.get(BASE + "/tasks", headers=headers, params={"referenceDate": "2026-10-31", "pageSize": 1})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["summary"]["total"] == 4
    assert result["summary"]["in_progress"] == 1
    assert result["summary"]["due_today"] == 1
    assert result["summary"]["completed"] == 1
    assert result["summary"]["overdue"] == 1
    assert len(result["items"]) == 1
    assert "/api/v1/files/blob?token=" in result["items"][0]["assignee_photo_url"]
    assert all(a["task_id"] in ids for a in result["activity"])
    overdue = client.get(BASE + "/tasks", headers=headers, params={"referenceDate": "2026-10-31", "overdue": True}).json()
    assert [t["title"] for t in overdue["items"]] == ["Late"]
    filtered = client.get(BASE + "/tasks", headers=headers, params={"search": "Active", "referenceDate": "2026-10-31"}).json()
    assert filtered["summary"]["total"] == 1
    assert filtered["summary"]["due_today"] == 1
    assert all(a["task_id"] == ids[0] for a in filtered["activity"])
    outsider, outsider_headers = account(db, "reference-outsider@test.com")
    hidden = client.get(BASE + "/tasks", headers=outsider_headers).json()
    assert hidden["items"] == []
    assert hidden["summary"]["total"] == 0
    assert hidden["activity"] == []
