import json
from datetime import datetime, timedelta, timezone
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from pypdf import PdfReader
from app.apps.project_management.models import PMSActivity, PMSTask, PMSTaskDependency
from app.apps.project_management.report_files import xlsx_bytes, pdf_bytes
from tests.test_pms_automations import setup_workspace
from tests.test_pms_workspaces import middleware_database, BASE


def test_work_item_types_schedule_clear_and_guest_restriction(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    tasks = []
    for kind in ["Story", "Bug"]:
        response = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh, json={"title": kind, "task_key": kind.upper(), "work_type": kind})
        assert response.status_code == 200, response.text
        assert response.json()["work_type"] == kind
        tasks.append(response.json())
    tid = tasks[0]["id"]
    path = f"{BASE}/tasks/{tid}/schedule"
    assert client.patch(path, headers=gh, json={"start_date": "2026-10-23"}).status_code == 403
    result = client.patch(path, headers=mh, json={"start_date": "2026-10-23", "due_date": "2026-10-24"})
    assert result.status_code == 200, result.text
    assert client.patch(path, headers=mh, json={"due_date": "2026-10-22"}).status_code == 400
    result = client.patch(path, headers=mh, json={"start_date": None, "due_date": None})
    assert result.status_code == 200, result.text
    assert result.json()["task"]["start_date"] is None and result.json()["task"]["due_date"] is None
    assert client.get(BASE + "/gantt", params={"projectId": pid}, headers=gh).json()["tasks"] == []
    all_tasks = client.get(BASE + "/gantt", params={"projectId": pid, "includeUnscheduled": "true"}, headers=gh).json()["tasks"]
    assert {task["id"] for task in all_tasks} == {task["id"] for task in tasks}


def test_workflow_feed_cursor_replay_redaction_and_workspace_roles(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    task = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh, json={"title": "Feed", "task_key": "FEED"}).json()
    for status in ["In Progress", "Done"]:
        client.patch(f"{BASE}/tasks/{task['id']}", headers=mh, json={"status": status})
    db.add(PMSActivity(project_id=pid, task_id=task["id"], actor_user_id=owner.id, action="task.updated", entity_type="task", entity_id=task["id"], summary="Private metadata", metadata_json=json.dumps({"old_values": {"description": "DO-NOT-EXPORT", "status": "To Do", "token": "DO-NOT-EXPORT"}})))
    db.commit()
    path = f"{BASE}/workspaces/{wid}/workflow-events"
    for headers in [mh, gh]:
        assert client.get(path, headers=headers).status_code == 403
    first = client.get(path, headers=ah, params={"limit": 2, "replay": False}).json()
    assert first["schema_version"] == "1" and first["has_more"] is True
    second = client.get(path, headers=oh, params={"after_id": first["next_cursor"], "limit": 200, "replay": False}).json()
    assert second["next_cursor"] > first["next_cursor"]
    assert not ({row["event_id"] for row in first["items"]} & {row["event_id"] for row in second["items"]})
    assert "DO-NOT-EXPORT" not in json.dumps(second)
    assert all(row["project_id"] == pid and "description" not in (row["task"] or {}) for row in second["items"])
    replay = client.get(path, headers=oh, params={"after_id": second["next_cursor"], "limit": 4}).json()
    assert replay["replayed"] == 2 and replay["next_cursor"] == second["next_cursor"]
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Other"}).json()["id"]
    assert client.get(f"{BASE}/workspaces/{other}/workflow-events", headers=oh).json()["items"] == []
    assert client.get(f"{BASE}/workspaces/{other}/workflow-events", headers=ah).status_code == 404


def test_shared_assignees_reports_and_selected_time_window(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    result = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh, json={"title": "Shared", "task_key": "SHARED", "assignee_user_ids": [owner.id, member.id]})
    task = db.get(PMSTask, result.json()["id"])
    task.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.add(task)
    db.commit()
    report = client.get(BASE + "/reports/task-distribution", headers=gh, params={"projectId": pid}).json()
    assert report["total_tasks"] == 1
    assert {item["assignee_id"] for item in report["by_assignee"]} == {owner.id, member.id}
    team = client.get(BASE + "/reports/team-performance", headers=gh, params={"projectId": pid}).json()
    assert len(team["items"]) == 2 and all(item["assigned_tasks"] == 1 for item in team["items"])
    time = client.get(BASE + "/reports/time-in-status", headers=gh, params={"projectId": pid, "from": "2026-01-10", "to": "2026-01-11"})
    assert time.status_code == 200, time.text
    assert sum(item["hours"] for item in time.json()["statuses"]) == 48
    health = client.get(BASE + "/reports/project-health", headers=gh, params={"projectId": pid}).json()
    assert health["basis"] == "current_snapshot" and len(health["points"]) == 1


def test_report_export_mapping_xlsx_format_and_invalid_reports(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    endpoint = BASE + "/reports/export"
    sprint = client.post(f"{BASE}/projects/{pid}/sprints", headers=oh, json={"name": "Report sprint", "start_date": "2026-01-01", "end_date": "2026-01-07"})
    assert sprint.status_code == 200, sprint.text
    burn = client.get(endpoint, headers=gh, params={"report": "burndown", "sprintId": sprint.json()["id"]})
    assert burn.status_code == 200 and burn.text.startswith("Date,Ideal Remaining Points")
    for report, header in [("task-distribution", "Status,Tasks"), ("velocity", "Sprint,End Date"), ("cumulative-flow", "Date,"), ("time-in-status", "Status,Hours"), ("project-health", "Date,Good"), ("team-performance", "Assignee,Assigned Tasks"), ("cycle-time", "Task,Title")]:
        result = client.get(endpoint, headers=gh, params={"projectId": pid, "report": report, "format": "csv"})
        assert result.status_code == 200, result.text
        assert result.text.startswith(header), (report, result.text)
    assert client.get(endpoint, headers=oh, params={"report": "unknown"}).status_code == 422
    assert client.get(endpoint, headers=oh, params={"report": "burndown"}).status_code == 422
    assert client.get(endpoint, headers=oh, params={"format": "invalid"}).status_code == 422
    excel = client.get(endpoint, headers=gh, params={"projectId": pid, "report": "task-distribution", "format": "xlsx"})
    assert excel.status_code == 200 and excel.content[:2] == b"PK"
    assert "spreadsheetml" in excel.headers["content-type"]
    with ZipFile(BytesIO(excel.content)) as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()
        ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))


def test_gantt_dependencies_never_expose_unrelated_workspace(client, db):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    public = client.post(f"{BASE}/projects/{pid}/tasks", headers=oh, json={"title": "Visible", "task_key": "PUBLIC", "start_date": "2026-10-23", "due_date": "2026-10-24"}).json()
    other = client.post(BASE + "/workspaces", headers=oh, json={"name": "Private"}).json()["id"]
    project = client.post(BASE + "/projects", headers=oh, json={"name": "Private", "project_key": "PRIVATE", "workspace_id": other}).json()["id"]
    private = client.post(f"{BASE}/projects/{project}/tasks", headers=oh, json={"title": "SECRET-DEPENDENCY", "task_key": "SECRET", "start_date": "2026-12-01", "due_date": "2026-12-04"}).json()
    db.add(PMSTaskDependency(task_id=public["id"], depends_on_task_id=private["id"], dependency_type="Finish To Start"))
    db.commit()
    response = client.get(BASE + "/gantt", headers=gh, params={"projectId": pid})
    assert response.status_code == 200, response.text
    assert "SECRET" not in response.text
    assert response.json()["dependencies"] == [] and response.json()["warnings"] == []


def test_spreadsheet_cells_are_text_and_pdf_keeps_all_rows():
    data = xlsx_bytes(["Title", "Count"], [["=HYPERLINK(\"x\")", 7], ["Research & QA <ready>", 9]])
    with ZipFile(BytesIO(data)) as archive:
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        assert sheet.find('.//s:c[@r="A2"]', ns).get("t") == "inlineStr"
        assert sheet.findall(".//s:f", ns) == []
        assert sheet.find('.//s:c[@r="B2"]/s:v', ns).text == "7"
    pdf = pdf_bytes("Full report", ["Task", "Status"], [[f"Row {index}", "Done"] for index in range(150)])
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 1
    assert "Row 149" in "".join(page.extract_text() for page in reader.pages)
