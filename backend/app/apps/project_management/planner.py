"""Read model for the planner; scheduling writes use existing task permissions."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import accessible_project_query, can_access_project
from .models import PMSTask, PMSMilestone, PMSProjectMember

router = APIRouter()


@router.get('/planner')
def planner(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    projects = accessible_project_query(db, user).all()
    ids = [p.id for p in projects]
    editable = {p.id: can_access_project(db, p, user, 'manage_tasks') for p in projects}
    tasks = db.query(PMSTask).filter(PMSTask.project_id.in_(ids), PMSTask.deleted_at.is_(None)).order_by(PMSTask.due_date, PMSTask.id).all()
    milestones = db.query(PMSMilestone).filter(PMSMilestone.project_id.in_(ids)).all()
    people_ids = {user.id}
    for task in tasks:
        people_ids.update(task.assignee_user_ids)
    people_ids.update(m.user_id for m in db.query(PMSProjectMember).filter(PMSProjectMember.project_id.in_(ids)).all())
    people = db.query(User).filter(User.id.in_(people_ids), User.is_active.is_(True)).order_by(User.email).all()
    return {
        'projects': [{'id': p.id, 'name': p.name, 'workspace_id': p.workspace_id, 'due_date': p.due_date, 'status': p.status, 'can_schedule': editable[p.id]} for p in projects],
        'tasks': [{'id': t.id, 'project_id': t.project_id, 'title': t.title, 'description': t.description, 'task_key': t.task_key,
                   'start_date': t.start_date, 'due_date': t.due_date, 'status': t.status, 'priority': t.priority,
                   'assignee_user_ids': t.assignee_user_ids, 'can_schedule': editable[t.project_id], 'recurrence_rule': t.recurrence_rule, 'recurrence_interval': t.recurrence_interval, 'recurrence_until': t.recurrence_until} for t in tasks],
        'milestones': [{'id': m.id, 'project_id': m.project_id, 'title': m.name, 'due_date': m.due_date, 'status': m.status} for m in milestones],
        'people': [{'id': person.id, 'name': person.email} for person in people],
    }
