from datetime import datetime, timezone
import json
import pytest
from tests.rich_text_test_utils import organization_context
from tests.test_pms_workspaces import middleware_database, BASE
from tests.test_pms_automations import setup_workspace
from app.apps.project_management.models import PMSTask, PMSActivity, PMSWorkspaceEntry, PMSWorkspaceMember
from app.apps.project_management.automation_schedules import dispatch_due

NOW = datetime(2030, 1, 2, 4, 0, tzinfo=timezone.utc)  # 09:30 India


def fixture(client, db, trigger="schedule.daily", **extra):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    payload = {"name": "Clock rule", "project_id": pid, "trigger": trigger, "action": "set_priority",
        "priority": "Urgent", "schedule": {"at": "09:00", "timezone": "Asia/Kolkata"}, **extra}
    response = client.post(f"{BASE}/workspaces/{wid}/automations", headers=oh, json=payload)
    assert response.status_code == 201, response.text
    return wid, pid, owner, oh, member, mh, response.json()


def task(client, pid, mh, key="CLOCK", **extra):
    response = client.post(f"{BASE}/projects/{pid}/tasks", headers=mh,
        json={"task_key": key, "title": key, "priority": "Low", **extra})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_daily_timezone_periods_and_retries(client, db):
    wid, pid, owner, oh, member, mh, rule = fixture(client, db)
    tid = task(client, pid, mh)
    assert dispatch_due(db, now=NOW.replace(hour=3))["processed"] == 0
    result = dispatch_due(db, now=NOW)
    assert result["failed_rule_ids"] == [], result
    assert result["processed"] == 1
    assert db.get(PMSTask, tid).priority == "Urgent"
    db.get(PMSTask, tid).priority = "Low"; db.commit()
    assert dispatch_due(db, now=NOW)["processed"] == 0  # receipt prevents replay
    assert db.get(PMSTask, tid).priority == "Low"
    assert dispatch_due(db, now=NOW.replace(day=3))["processed"] == 1


def test_due_offsets_catchup_reschedule_and_no_repeat(client, db):
    wid, pid, owner, oh, member, mh, rule = fixture(client, db, "task.due_date",
        schedule={"at": "09:00", "timezone": "Asia/Kolkata", "due_offset_days": -1})
    past = task(client, pid, mh, "PAST", due_date="2029-12-31")
    due = task(client, pid, mh, "TOMORROW", due_date="2030-01-03")
    future = task(client, pid, mh, "FUTURE", due_date="2030-01-04")
    undated = task(client, pid, mh, "NO-DATE")
    result = dispatch_due(db, now=NOW)
    assert result["failed_rule_ids"] == [], result
    assert result["processed"] == 2
    assert db.get(PMSTask, future).priority == db.get(PMSTask, undated).priority == "Low"
    assert dispatch_due(db, now=NOW)["processed"] == 0
    # A reschedule is a different due-date occurrence, including an earlier date.
    response = client.patch(f"{BASE}/tasks/{due}", headers=mh, json={"due_date": "2030-01-02", "priority": "Low"})
    assert response.status_code == 200, response.text
    assert dispatch_due(db, now=NOW)["processed"] == 1


def test_clock_rechecks_conditions_pause_and_owner_access(client, db):
    wid, pid, owner, oh, member, mh, rule = fixture(client, db,
        conditions={"field": "status", "operator": "equals", "value": "In Progress"})
    tid = task(client, pid, mh)
    assert dispatch_due(db, now=NOW)["processed"] == 0
    client.patch(f"{BASE}/tasks/{tid}", headers=mh, json={"status": "In Progress"})
    path = f"{BASE}/workspaces/{wid}/automations/{rule['id']}"
    client.patch(path, headers=oh, json={"enabled": False})
    assert dispatch_due(db, now=NOW)["processed"] == 0
    client.patch(path, headers=oh, json={"enabled": True})
    owner.is_active = False; db.commit()
    result = dispatch_due(db, now=NOW)
    assert result["processed"] == 0 and result["failed_rule_ids"] == [rule["id"]]
    assert db.get(PMSTask, tid).priority == "Low"
    owner.is_active = True; db.commit()
    assert dispatch_due(db, now=NOW)["processed"] == 1


def test_bounded_scan_rolls_back_receipts_and_retries(client, db, monkeypatch):
    from app.apps.project_management import automation_schedules as service
    wid, pid, owner, oh, member, mh, rule = fixture(client, db)
    ids = [task(client, pid, mh, f"BOUNDED-{n}") for n in range(3)]
    original = service._apply_rule
    def broken(*args):
        original(*args)
        raise RuntimeError("Synthetic failure after mutation")
    monkeypatch.setattr(service, "_apply_rule", broken)
    failed = dispatch_due(db, now=NOW, task_limit=2)
    assert failed["failed_rule_ids"] == [rule["id"]]
    assert all(db.get(PMSTask, tid).priority == "Low" for tid in ids)
    assert db.query(PMSWorkspaceEntry).filter_by(kind=f"ar{rule['id']:x}").count() == 0
    monkeypatch.setattr(service, "_apply_rule", original)
    assert dispatch_due(db, now=NOW, task_limit=2)["processed"] == 2
    assert dispatch_due(db, now=NOW, task_limit=2)["processed"] == 1
    assert dispatch_due(db, now=NOW, task_limit=2)["processed"] == 0


@pytest.mark.parametrize("schedule", [None, {"at": "25:00"}, {"timezone": "No/SuchZone"}])
def test_invalid_schedule_rejected(client, db, schedule):
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    response = client.post(f"{BASE}/workspaces/{wid}/automations", headers=oh,
        json={"name": "Invalid", "project_id": pid, "trigger": "schedule.daily", "action": "set_priority", "schedule": schedule})
    assert response.status_code == 422, response.text


def test_scheduler_endpoint_requires_cron_credentials(client):
    assert client.get("/api/v1/internal/pms-automations").status_code == 401


def test_scheduled_author_with_pms_only_policy_and_revoked_membership(client, db):
    from app.access.models import AccessPolicy
    wid, pid, owner, oh, ah, member, mh, guest, gh = setup_workspace(client, db)
    reviewer = db.query(PMSWorkspaceMember).filter_by(workspace_id=wid, role="Admin").one()
    db.add(AccessPolicy(user_id=reviewer.user_id, company_id=1, status="active", version=1, grants={
        "project_management": {"enabled": True, "role": "PMS manager", "scope": "organization",
            "permissions": ["pms_view", "pms_manage_tasks"], "actions": ["view", "create", "edit"]}}))
    db.commit()
    response = client.post(f"{BASE}/workspaces/{wid}/automations", headers=ah,
        json={"name": "Managed author", "project_id": pid, "trigger": "schedule.daily", "action": "set_priority",
              "priority": "Urgent", "schedule": {"at": "09:00", "timezone": "Asia/Kolkata"}})
    assert response.status_code == 201, response.text
    tid = task(client, pid, mh)
    result = dispatch_due(db, now=NOW)
    assert result["failed_rule_ids"] == [] and result["processed"] == 1, result
    db.delete(db.get(PMSWorkspaceMember, reviewer.id)); db.commit()
    next_task = task(client, pid, mh, "REVOKED")
    result = dispatch_due(db, now=NOW)
    assert result["processed"] == 0 and result["failed_rule_ids"] == [response.json()["id"]]
    assert db.get(PMSTask, next_task).priority == "Low"
