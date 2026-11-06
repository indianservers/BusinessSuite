"""Committed PostgreSQL scheduler sessions reuse the workflow acceptance harness."""
from datetime import datetime, timezone
from tests.test_pms_workflow_postgresql import live, race, waiting_editor, wait_for_lock, BASE
from app.apps.project_management.automation_schedules import dispatch_due
from app.apps.project_management.models import PMSActivity, PMSTask
from app.models.user import User

NOW = datetime(2030, 1, 2, 4, 0, tzinfo=timezone.utc)


def create_rule(live):
    response = live.client.post(f"{BASE}/workspaces/{live.wid}/automations", headers=live.oh,
        json={"name": "Concurrent clock", "project_id": live.pid, "trigger": "schedule.daily",
              "action": "set_priority", "priority": "Urgent", "schedule": {"at": "09:00", "timezone": "Asia/Kolkata"}})
    assert response.status_code == 201, response.text
    # Commit the ledger's first initialization before competing calls.
    with live.factory() as db:
        assert dispatch_due(db, now=NOW.replace(hour=3))["processed"] == 0
    return response.json()["id"]


def test_pms_clock_overlapping_ticks_apply_once(live):
    rid = create_rule(live)
    def tick():
        with live.factory() as db:
            return dispatch_due(db, now=NOW)
    results = race(tick, tick)
    assert all(r["failed_rule_ids"] == [] for r in results), results
    assert sum(r["processed"] for r in results) == 1, results
    with live.factory() as db:
        assert db.get(PMSTask, live.tid).priority == "Urgent"
        assert db.query(PMSActivity).filter_by(entity_id=rid, action="automation.executed").count() == 1


def test_pms_clock_rechecks_author_after_lock_wait(live):
    rid = create_rule(live)
    def revoke(db):
        db.get(User, live.owner_id).is_active = False
    def tick():
        with live.factory() as db:
            return dispatch_due(db, now=NOW)
    with waiting_editor(live, revoke) as (pool, editor):
        future = pool.submit(tick)
        wait_for_lock(live); editor.commit()
        result = future.result(timeout=20)
    assert result["processed"] == 0 and result["failed_rule_ids"] == [rid], result
    with live.factory() as db:
        assert db.get(PMSTask, live.tid).priority != "Urgent"
