from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.apps.crm.models import CRMTask
from app.apps.crm.task_filters import apply_task_queue


def test_task_queues_use_local_day_and_exclude_finished_work(db):
    now = datetime(2026, 11, 7, 1, tzinfo=timezone.utc)
    rows = [
        CRMTask(title="Yesterday", status="To Do", due_date=datetime(2026, 11, 6, 18, 29, tzinfo=timezone.utc)),
        CRMTask(title="Today boundary", status="In Progress", due_date=datetime(2026, 11, 6, 18, 30, tzinfo=timezone.utc)),
        CRMTask(title="Tomorrow boundary", status="To Do", due_date=datetime(2026, 11, 7, 18, 30, tzinfo=timezone.utc)),
        CRMTask(title="Already done", status="Completed", due_date=datetime(2026, 11, 5, tzinfo=timezone.utc)),
        CRMTask(title="Cancelled", status="Cancelled"),
        CRMTask(title="No date", status="To Do"),
    ]
    db.add_all(rows)
    db.flush()
    base = db.query(CRMTask).filter(CRMTask.id.in_([row.id for row in rows]))

    def titles(queue):
        return {row.title for row in apply_task_queue(base, queue, "Asia/Kolkata", now=now).all()}

    assert titles("overdue") == {"Yesterday"}
    assert titles("today") == {"Today boundary"}
    assert titles("week") == {"Today boundary", "Tomorrow boundary"}
    assert titles("completed") == {"Already done"}
    assert titles("unscheduled") == {"No date"}
    assert titles("open") == {"Yesterday", "Today boundary", "Tomorrow boundary", "No date"}
    assert len(titles("all")) == 6
    for queue, zone in [("unknown", "UTC"), ("today", "Invalid/Zone")]:
        with pytest.raises(HTTPException) as error:
            apply_task_queue(base, queue, zone, now=now)
        assert error.value.status_code == 422


def test_task_queue_api_filters_before_count_and_pagination(client, db, superuser_headers):
    from app.models.user import User
    from test_identity_utils import attach_test_identity
    user = db.query(User).filter_by(email="testadmin@test.com").one()
    attach_test_identity(db, user)
    db.commit()
    for index in range(3):
        response = client.post("/api/v1/crm/tasks", headers=superuser_headers, json={
            "title": f"Queue regression {index}", "status": "To Do" if index < 2 else "Done", "priority": "High",
        })
        assert response.status_code == 201, response.text
    result = client.get("/api/v1/crm/tasks", headers=superuser_headers, params={
        "search": "Queue regression", "task_queue": "unscheduled", "priority": "High", "per_page": 1,
        "sort_by": "title", "sort_order": "asc", "timezone": "Asia/Kolkata",
    })
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 2
    assert result.json()["pages"] == 2
    assert result.json()["items"][0]["title"] == "Queue regression 0"
    assert client.get("/api/v1/crm/tasks", headers=superuser_headers, params={"task_queue": "bogus"}).status_code == 422
