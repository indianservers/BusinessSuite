"""Native SQL filters for task/commitment feeds, before keyset paging."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func, or_, and_


def filtered(query, source, due, user, *, view='all', search='', assigned=None):
    model = query.column_descriptions[0]['entity']
    if source == 'pms_followup':
        closed = model.resolved.is_(True)
        assignee = func.coalesce(model.responsible_user_id, model.author_id)
        creator = model.author_id
        title = model.body
    else:
        closed = func.lower(func.coalesce(model.status, '')).in_(['done', 'completed', 'closed', 'cancelled', 'missed'])
        assignee = model.assigned_user_id if source == 'service_followup' else model.assignee_user_id if source == 'pms_task' else model.owner_user_id
        creator = model.created_by if source == 'service_followup' else model.reporter_user_id if source == 'pms_task' else model.created_by_user_id
        title = func.coalesce(model.title, model.subject) if source == 'crm_activity' else model.title
    if view == 'completed':
        query = query.filter(closed)
    elif view != 'all':
        query = query.filter(~closed)
    identity = user.id if view == 'mine' else assigned
    if identity:
        assigned_to = assignee == identity
        if source == 'pms_task':
            from app.apps.project_management.models import PMSTaskAssignee
            assigned_to = or_(assigned_to, query.session.query(PMSTaskAssignee.task_id).filter(PMSTaskAssignee.task_id == model.id, PMSTaskAssignee.user_id == identity).exists())
        query = query.filter(assigned_to)
    if view == 'assigned':
        query = query.filter(creator == user.id)
    if search:
        escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.filter(title.ilike('%' + escaped + '%', escape='\\'))
    now = datetime.now(timezone.utc)
    if view in ('today', 'upcoming', 'overdue'):
        if source in ('pms_task', 'pms_followup'):
            today = now.astimezone(ZoneInfo('Asia/Kolkata')).date()
            query = query.filter(due == today if view == 'today' else due > today if view == 'upcoming' else due < today)
        elif view == 'overdue':
            query = query.filter(due < now)
        else:
            # Reuse the service engine's stored timezone contract. This query
            # loads distinct zone names, never every follow-up row.
            zones = [zone for zone, in query.order_by(None).with_entities(model.timezone).distinct()] if source == 'service_followup' else ['Asia/Kolkata']
            conditions = []
            for zone in zones:
                local = now.astimezone(ZoneInfo(zone))
                start = datetime.combine(local.date(), time.min, ZoneInfo(zone)).astimezone(timezone.utc)
                end = datetime.combine(local.date() + timedelta(days=1), time.min, ZoneInfo(zone)).astimezone(timezone.utc)
                condition = and_(due >= start, due < end) if view == 'today' else due >= end
                conditions.append(and_(model.timezone == zone, condition) if source == 'service_followup' else condition)
            query = query.filter(or_(*conditions) if conditions else False)
    return query
