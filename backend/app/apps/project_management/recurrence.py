"""Generate the next recurrence when a task is completed, in its transaction."""
import calendar
from datetime import timedelta
from fastapi import HTTPException
from .models import PMSTask, PMSTaskAssignee, PMSTaskTag, PMSBoardColumn


def validate_recurrence(rule, due_date, until, interval):
    if not rule:
        return
    if rule not in {"daily", "weekly", "monthly"}:
        raise HTTPException(422, "Repeat frequency must be daily, weekly or monthly")
    if not due_date or not interval or interval < 1 or interval > 365:
        raise HTTPException(422, "Recurring tasks need a due date and interval from 1 to 365")
    if until and until < due_date:
        raise HTTPException(422, "Recurrence end cannot be before the due date")


def create_next_occurrence(db, task):
    if not task.recurrence_rule or not task.due_date:
        return None
    db.query(PMSTask).filter(PMSTask.id == task.id).with_for_update().first()
    key = f"REPEAT-{task.id}"
    existing = db.query(PMSTask).filter_by(project_id=task.project_id, task_key=key).first()
    if existing:
        return existing
    interval = task.recurrence_interval or 1
    if task.recurrence_rule == "monthly":
        month_index = task.due_date.year * 12 + task.due_date.month - 1 + interval
        year, month = divmod(month_index, 12)
        due = task.due_date.replace(year=year, month=month + 1, day=min(task.due_date.day, calendar.monthrange(year, month + 1)[1]))
    elif task.recurrence_rule in {"daily", "weekly"}:
        due = task.due_date + timedelta(days=interval * (7 if task.recurrence_rule == "weekly" else 1))
    else:
        return None
    if task.recurrence_until and due > task.recurrence_until:
        return None
    fields = ["project_id", "title", "description", "work_type", "priority", "assignee_user_id", "reporter_user_id", "estimated_hours", "story_points", "security_level", "is_client_visible", "recurrence_rule", "recurrence_interval", "recurrence_until", "board_id", "parent_task_id"]
    following = PMSTask(**{name: getattr(task, name) for name in fields}, task_key=key, status="To Do", due_date=due,
                        start_date=task.start_date + (due - task.due_date) if task.start_date else None)
    if task.board_id:
        column = db.query(PMSBoardColumn).filter_by(board_id=task.board_id, status_key="TODO").first()
        following.column_id = column.id if column else None
    db.add(following)
    db.flush()
    for assignment in db.query(PMSTaskAssignee).filter_by(task_id=task.id).all():
        db.add(PMSTaskAssignee(task_id=following.id, user_id=assignment.user_id))
    for tag in db.query(PMSTaskTag).filter_by(task_id=task.id).all():
        db.add(PMSTaskTag(task_id=following.id, tag_id=tag.tag_id))
    return following
