"""Polling must deliver committed changes only to accessible projects."""
from app.apps.project_management.event_feed import append_event, read_events


def test_feed_cursor_and_project_access(db):
    initial = read_events(db, {101})
    append_event(db, {"type": "task.updated", "projectId": 101, "taskId": 7})
    append_event(db, {"type": "task.updated", "projectId": 202, "taskId": 8})
    result = read_events(db, {101}, initial["cursor"])
    assert [event["taskId"] for event in result["events"]] == [7]
    assert read_events(db, set(), initial["cursor"])["events"] == []
    next_page = read_events(db, {101}, result["cursor"])
    assert next_page["events"] == []
    append_event(db, {"type": "comment.created", "projectId": 101, "taskId": 7})
    assert read_events(db, {101}, next_page["cursor"])["events"][0]["type"] == "comment.created"


def test_feed_pagination_does_not_skip_events(db):
    cursor = read_events(db, {101})["cursor"]
    for task_id in range(3):
        append_event(db, {"type": "task.created", "projectId": 101, "taskId": task_id})
    received = []
    for _ in range(3):
        page = read_events(db, {101}, cursor, limit=1)
        received.extend(event["taskId"] for event in page["events"])
        cursor = page["cursor"]
    assert received == [0, 1, 2]
