from datetime import datetime, timedelta, timezone

from app.apps.crm.models import CRMActivity, CRMTimelineEvent
from app.models.notification import Notification
from tests.test_crm_lead_assignment import employee_account
from tests.test_crm_lead_management import ROOT, create


def future(days=1):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def test_due_reminders_are_scoped_deduplicated_and_reset_on_reschedule(
    client, db, superuser_headers
):
    from app.apps.crm.lead_management import scheduled_lead_alerts

    owner, _ = employee_account(db, "reminder")
    lead = create(client, superuser_headers, owner_user_id=owner.id)
    url = ROOT + f"/leads/{lead['id']}/follow-up"
    response = client.post(
        url,
        headers=superuser_headers,
        json={"title": "Call now", "dueAt": future(), "version": lead["version"]},
    )
    assert response.status_code == 200, response.text
    item = db.query(CRMActivity).filter_by(lead_id=lead["id"], status="Pending").one()
    item.due_date = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert scheduled_lead_alerts(db)["followUpReminders"] == 1
    assert scheduled_lead_alerts(db)["followUpReminders"] == 0
    assert (
        db.query(Notification)
        .filter_by(event_type="lead_follow_up_due", user_id=owner.id)
        .count()
        == 1
    )
    moved = client.post(
        url,
        headers=superuser_headers,
        json={
            "title": "Call tomorrow",
            "dueAt": future(),
            "activityId": item.id,
            "version": response.json()["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    db.refresh(item)
    assert "followUpReminderAt" not in item.metadata_json


def test_follow_up_is_pending_not_completed_and_notifies_owner(
    client, db, superuser_headers
):
    owner, _ = employee_account(db, "followup")
    lead = create(client, superuser_headers, owner_user_id=owner.id)
    response = client.post(
        ROOT + f"/leads/{lead['id']}/follow-up",
        headers=superuser_headers,
        json={
            "title": "Call about budget",
            "dueAt": future(),
            "type": "call",
            "ownerId": owner.id,
            "version": lead["version"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["next_follow_up_at"]
    task = db.query(CRMActivity).filter_by(lead_id=lead["id"], status="Pending").one()
    assert task.owner_user_id == owner.id and task.subject == "Call about budget"
    assert (
        db.query(Notification)
        .filter_by(user_id=owner.id, event_type="lead_follow_up")
        .count()
        == 1
    )
    assert (
        db.query(CRMTimelineEvent)
        .filter_by(record_id=lead["id"], event_type="follow_up_scheduled")
        .count()
        == 1
    )


def test_reschedule_updates_existing_task_and_earliest_next_step(
    client, db, superuser_headers
):
    lead = create(client, superuser_headers)
    url = ROOT + f"/leads/{lead['id']}/follow-up"
    first = client.post(
        url,
        headers=superuser_headers,
        json={"title": "First", "dueAt": future(), "version": lead["version"]},
    )
    assert first.status_code == 200, first.text
    task = db.query(CRMActivity).filter_by(lead_id=lead["id"], status="Pending").one()
    second = client.post(
        url,
        headers=superuser_headers,
        json={
            "title": "Second",
            "dueAt": future(2),
            "version": first.json()["version"],
        },
    )
    moved = client.post(
        url,
        headers=superuser_headers,
        json={
            "title": "First moved",
            "dueAt": future(3),
            "activityId": task.id,
            "version": second.json()["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    pending = (
        db.query(CRMActivity).filter_by(lead_id=lead["id"], status="Pending").all()
    )
    assert len(pending) == 2
    assert next(t for t in pending if t.id == task.id).subject == "First moved"
    assert (
        datetime.fromisoformat(
            moved.json()["next_follow_up_at"].replace("Z", "+00:00")
        ).date()
        == (datetime.now(timezone.utc) + timedelta(days=2)).date()
    )


def test_follow_up_conflicts_foreign_tasks_and_invalid_times_are_atomic(
    client, db, superuser_headers
):
    lead = create(client, superuser_headers)
    other = create(client, superuser_headers, full_name="Other lead")
    url = ROOT + f"/leads/{lead['id']}/follow-up"
    data = {"title": "Call", "dueAt": future(), "version": lead["version"]}
    assert (
        client.post(
            url, headers=superuser_headers, json={**data, "version": 999}
        ).status_code
        == 409
    )
    assert (
        client.post(
            url, headers=superuser_headers, json={**data, "dueAt": future(-1)}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, headers=superuser_headers, json={**data, "title": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, headers=superuser_headers, json={**data, "activityId": 99999}
        ).status_code
        == 409
    )
    assert (
        db.query(CRMActivity).filter_by(lead_id=lead["id"], status="Pending").count()
        == 0
    )
    assert (
        client.get(
            ROOT + f"/leads/{other['id']}", headers=superuser_headers
        ).status_code
        == 200
    )


def test_team_notes_keep_context_and_notify_only_visible_members(
    client, db, superuser_headers
):
    owner, _ = employee_account(db, "notified")
    outsider, _ = employee_account(db, "outsider")
    foreign, _ = employee_account(db, "foreign", organization=2)
    lead = create(client, superuser_headers, owner_user_id=owner.id)
    url = ROOT + f"/leads/{lead['id']}"
    team = client.get(url + "/team", headers=superuser_headers)
    ids = {m["id"] for m in team.json()["members"]}
    assert owner.id in ids and outsider.id not in ids and foreign.id not in ids
    for ident in (outsider.id, foreign.id):
        blocked = client.post(
            url + "/team-notes",
            headers=superuser_headers,
            json={
                "body": "Private handoff",
                "mentionIds": [ident],
                "version": lead["version"],
            },
        )
        assert blocked.status_code == 422, blocked.text
    saved = client.post(
        url + "/team-notes",
        headers=superuser_headers,
        json={
            "body": "Budget confirmed; call tomorrow",
            "mentionIds": [owner.id, owner.id],
            "version": lead["version"],
        },
    )
    assert saved.status_code == 200, saved.text
    assert (
        db.query(Notification)
        .filter_by(event_type="lead_team_mention", user_id=owner.id)
        .count()
        == 1
    )
    detail = client.get(url, headers=superuser_headers).json()
    note = next(e for e in detail["timeline"] if e["event_type"] == "team_note")
    assert note["description"] == "Budget confirmed; call tomorrow"
    assert note["metadata_json"]["mentionIds"] == [owner.id]
    assert (
        client.post(
            url + "/team-notes",
            headers=superuser_headers,
            json={"body": "Stale update", "version": lead["version"]},
        ).status_code
        == 409
    )


def test_lost_and_archived_leads_cannot_schedule(client, db, superuser_headers):
    lead = create(client, superuser_headers)
    url = ROOT + f"/leads/{lead['id']}"
    lost = client.patch(
        url,
        headers=superuser_headers,
        json={
            "values": {"status": "Lost"},
            "details": {"lossReason": "No budget"},
            "version": lead["version"],
        },
    )
    assert lost.status_code == 200, lost.text
    assert (
        client.post(
            url + "/follow-up",
            headers=superuser_headers,
            json={
                "title": "Call",
                "dueAt": future(),
                "version": lost.json()["version"],
            },
        ).status_code
        == 409
    )


def test_workflow_endpoints_enforce_record_visibility(client, db, superuser_headers):
    outsider, _ = employee_account(db, "restricted")
    lead = create(client, superuser_headers)
    login = client.post(
        "/api/v1/auth/login", json={"email": outsider.email, "password": "Sales@123456"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    url = ROOT + f"/leads/{lead['id']}"
    assert client.get(url + "/team", headers=headers).status_code == 404
    assert (
        client.post(
            url + "/team-notes",
            headers=headers,
            json={"body": "Cannot see this lead", "version": lead["version"]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            url + "/follow-up",
            headers=headers,
            json={"title": "Call", "dueAt": future(), "version": lead["version"]},
        ).status_code
        == 404
    )
