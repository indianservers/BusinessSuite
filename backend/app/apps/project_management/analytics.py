"""Access-scoped team and project analytics from persisted PMS data."""
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from .access import accessible_project_query
from .models import (PMSWorkspaceMember, PMSWorkspaceTeam, PMSProjectMember, PMSTask,
                     PMSTaskAssignee, PMSTimeLog, PMSActivity)

router = APIRouter()
from app.services.metrics.queries import COMPLETED,TERMINAL,business_day
DONE=set(COMPLETED)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


@router.get('/analytics/overview')
def analytics_overview(
    start_date: date | None = None, end_date: date | None = None,
    workspace_id: int | None = None, project_id: int | None = None,
    team_id: int | None = None, member_id: int | None = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    today = business_day(db,user)
    end_date = end_date or today
    start_date = start_date or end_date - timedelta(days=29)
    if start_date > end_date or (end_date - start_date).days > 365:
        raise HTTPException(422, 'Choose a date range of 1 to 366 days')
    memberships = db.query(PMSWorkspaceMember).filter_by(user_id=user.id).all()
    allowed_workspaces = {m.workspace_id for m in memberships if m.role != 'Guest'}
    if workspace_id and workspace_id not in allowed_workspaces:
        raise HTTPException(403, 'Collaborator membership is required for workspace analytics')
    projects = [p for p in accessible_project_query(db, user).all()
                if (not p.workspace_id or p.workspace_id in allowed_workspaces)]
    if workspace_id:
        projects = [p for p in projects if p.workspace_id == workspace_id]
    options = [{'id': p.id, 'name': p.name, 'workspace_id': p.workspace_id} for p in projects]
    if project_id:
        projects = [p for p in projects if p.id == project_id]
        if not projects:
            raise HTTPException(403, 'Project analytics access denied')
    project_ids = [p.id for p in projects]
    workspace_ids = ({workspace_id} if workspace_id else allowed_workspaces) if not project_id else {p.workspace_id for p in projects if p.workspace_id}
    teams = db.query(PMSWorkspaceTeam).filter(PMSWorkspaceTeam.workspace_id.in_(workspace_ids)).all()
    workspace_people = db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.workspace_id.in_(workspace_ids), PMSWorkspaceMember.role != 'Guest').all()
    eligible_by_workspace = defaultdict(set)
    for m in workspace_people:
        eligible_by_workspace[m.workspace_id].add(m.user_id)
    team_options = [{'id': t.id, 'name': t.name, 'workspace_id': t.workspace_id} for t in teams]
    selected_members = None
    if team_id:
        team = next((t for t in teams if t.id == team_id), None)
        if not team:
            raise HTTPException(403, 'Team analytics access denied')
        selected_members = set(json.loads(team.member_ids_json)) & eligible_by_workspace[team.workspace_id]
        projects = [p for p in projects if p.workspace_id == team.workspace_id]
        project_ids = [p.id for p in projects]
    if member_id:
        selected_members = ({member_id} if selected_members is None else selected_members & {member_id})
    tasks = db.query(PMSTask).filter(PMSTask.project_id.in_(project_ids), PMSTask.deleted_at.is_(None)).all()
    assignments = defaultdict(set)
    for assignment in db.query(PMSTaskAssignee).filter(PMSTaskAssignee.task_id.in_([t.id for t in tasks]),PMSTaskAssignee.cancelled_at.is_(None)).all():
        assignments[assignment.task_id].add(assignment.user_id)
    for task in tasks:
        if task.assignee_user_id:
            assignments[task.id].add(task.assignee_user_id)
    if selected_members is not None:
        tasks = [t for t in tasks if assignments[t.id] & selected_members]
    task_ids = {t.id for t in tasks}
    recorded_completion_dates = {t.id: utc(t.completed_at) for t in tasks if t.completed_at and t.status in DONE}
    completion_dates = {}
    history = db.query(PMSActivity).filter(PMSActivity.task_id.in_(task_ids), PMSActivity.action.in_(['status.changed', 'bulk_updated'])).order_by(PMSActivity.created_at).all()
    for event in history:
        try:
            metadata = json.loads(event.metadata_json or '{}')
        except (TypeError, ValueError):
            continue
        if metadata.get('new_value', metadata.get('status')) in DONE:
            completion_dates[event.task_id] = utc(event.created_at)
    completion_dates.update(recorded_completion_dates)
    start = datetime.combine(start_date, time.min, timezone.utc)
    until = datetime.combine(end_date + timedelta(days=1), time.min, timezone.utc)
    logs = db.query(PMSTimeLog).filter(PMSTimeLog.project_id.in_(project_ids), PMSTimeLog.log_date >= start_date, PMSTimeLog.log_date <= end_date).all()
    logs = [l for l in logs if (l.task_id is None or l.task_id in task_ids) and (selected_members is None or l.user_id in selected_members)]
    events = db.query(PMSActivity).filter(PMSActivity.project_id.in_(project_ids), PMSActivity.created_at >= start, PMSActivity.created_at < until).all()
    events = [e for e in events if (e.task_id is None or e.task_id in task_ids) and (selected_members is None or e.actor_user_id in selected_members)]
    people_ids = set().union(*(assignments[t.id] for t in tasks)) if tasks else set()
    people_ids |= {l.user_id for l in logs} | {e.actor_user_id for e in events if e.actor_user_id}
    for m in db.query(PMSProjectMember).filter(PMSProjectMember.project_id.in_(project_ids)).all():
        people_ids.add(m.user_id)
    if not project_id:
        people_ids |= set().union(*(eligible_by_workspace[w] for w in workspace_ids)) if workspace_ids else set()
    people_options = [{'id': u.id, 'name': u.email} for u in db.query(User).filter(User.id.in_(people_ids), User.is_active.is_(True)).order_by(User.email).all()]
    if selected_members is not None:
        people_ids &= selected_members
    users = db.query(User).filter(User.id.in_(people_ids), User.is_active.is_(True)).order_by(User.email).all()
    now = datetime.now(timezone.utc)
    def snapshot(items):
        done = sum(t.status in DONE for t in items)
        return {'total': len(items), 'completed': done, 'open': len(items) - done,
                'blocked': sum(t.status == 'Blocked' for t in items),
                'overdue': sum(bool(t.due_date and t.due_date < today and t.status not in TERMINAL) for t in items),
                'completion_percent': round(done / len(items) * 100, 1) if items else 0}
    people = []
    for person in users:
        assigned = [t for t in tasks if person.id in assignments[t.id]]
        person_logs = [l for l in logs if l.user_id == person.id]
        person_events = [e for e in events if e.actor_user_id == person.id]
        latest = max((utc(e.created_at) for e in person_events), default=None)
        focus = Counter()
        for log in person_logs:
            if log.task_id:
                focus[log.task_id] += log.duration_minutes or 0
        total_focus = sum(focus.values())
        people.append({'id': person.id, 'name': person.email, **snapshot(assigned),
                       'tracked_minutes': sum(l.duration_minutes or 0 for l in person_logs),
                       'activity_count': len(person_events), 'last_activity_at': latest.isoformat() if latest else None,
                       'recently_active': bool(latest and now - timedelta(minutes=15) <= latest <= now),
                       'focus': [{'task_id': tid, 'title': next(t.title for t in tasks if t.id == tid), 'minutes': minutes,
                                  'percent': round(minutes / total_focus * 100, 1) if total_focus else 0} for tid, minutes in focus.most_common(3)]})
    rows = []
    for project in projects:
        items = [t for t in tasks if t.project_id == project.id]
        rows.append({'id': project.id, 'name': project.name, 'status': project.status, **snapshot(items),
                     'tracked_minutes': sum(l.duration_minutes or 0 for l in logs if l.project_id == project.id),
                     'estimated_hours': round(sum(float(t.estimated_hours or 0) for t in items), 2),
                     'created_in_range': sum(bool(t.created_at and start <= utc(t.created_at) < until) for t in items),
                     'completed_in_range': sum(bool(t.status in DONE and completion_dates.get(t.id) and start <= completion_dates[t.id] < until) for t in items)})
    trend = []
    for index in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=index)
        trend.append({'date': day.isoformat(), 'minutes': sum(l.duration_minutes or 0 for l in logs if l.log_date == day),
                      'created': sum(bool(t.created_at and utc(t.created_at).date() == day) for t in tasks),
                      'completed': sum(bool(t.status in DONE and completion_dates.get(t.id) and completion_dates[t.id].date() == day) for t in tasks)})
    hourly = [set() for _ in range(24)]
    for event in events:
        timestamp = utc(event.created_at)
        if timestamp.date() == end_date and event.actor_user_id:
            hourly[timestamp.hour].add(event.actor_user_id)
    return {'start_date': start_date, 'end_date': end_date, 'timezone': 'UTC', 'generated_at': now,
            'summary': {**snapshot(tasks), 'people': len(people), 'projects': len(rows),
                        'tracked_minutes': sum(l.duration_minutes or 0 for l in logs),
                        'recently_active': sum(p['recently_active'] for p in people)},
            'people': people, 'projects': rows, 'trend': trend,
            'hourly_activity': [{'hour': hour, 'people': len(ids)} for hour, ids in enumerate(hourly)],
            'status_distribution': [{'status': status, 'count': count} for status, count in sorted(Counter(t.status for t in tasks).items())],
            'filters': {'projects': options, 'teams': team_options, 'people': people_options},
            'definitions': {'snapshot': 'Task counts reflect current state; tracked time and activity use the selected date range.',
                            'activity': 'Recorded PMS actions, not online presence. Recent means an action in the last 15 minutes within the selected range.',
                            'shared_tasks': 'A shared task counts once per project and once for each assigned person. Time is credited only to its author.'}}
