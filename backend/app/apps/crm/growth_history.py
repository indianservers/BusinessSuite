"""Read-only follow-up history over scoped activities and retained action logs."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.user import User
from .models import CRMActivity

router = APIRouter()


def utc(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc) if value else None


def followup_snapshot(activity):
    if not activity:
        return None
    return {"id": activity.id, "title": activity.title or activity.subject,
            "status": activity.status, "owner_id": activity.owner_user_id,
            "due_at": utc(activity.due_date).isoformat() if activity.due_date else None,
            "reminder_at": (activity.metadata_json or {}).get("reminder_at"),
            "priority": activity.priority,
            "completed_at": utc(activity.completed_at).isoformat() if activity.completed_at else None}


@router.get('/history')
def history(entity: Literal['all', 'leads', 'contacts', 'companies', 'deals'] = 'all',
            record_id: int | None = Query(None, gt=0),
            view: Literal['pending', 'completed', 'history'] = 'pending',
            employee_id: int | None = Query(None, gt=0),
            search: str = Query('', max_length=150), page: int = Query(1, ge=1),
            per_page: int = Query(20, ge=1, le=100),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from . import growth as g
    if record_id and entity == 'all':
        raise HTTPException(422, 'Choose a relationship type for record history')
    clauses, resources = [], {}
    for kind in g.ENTITIES if entity == 'all' else [entity]:
        try:
            model = g.crm()._get_resource(kind).model
            records = g.sales.rows(db, user, kind)
        except HTTPException as error:
            if entity != 'all' or error.status_code != 403:
                raise
            continue
        if record_id:
            records = records.filter(model.id == record_id)
            if not records.first():
                raise HTTPException(404, 'Record not found in your permitted scope')
        if search.strip():
            name = getattr(model, 'full_name', None)
            if name is None:
                name = model.name
            term = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            records = records.filter(name.ilike(term, escape='\\'))
        resources[kind] = (model, records)
        clauses.append((CRMActivity.entity_type == ('account' if kind == 'companies' else g.sales.record_kind(kind))) & CRMActivity.entity_id.in_(records.with_entities(model.id)))
    if not clauses:
        return {'items': [], 'total': 0, 'page': page, 'pages': 0, 'employees': [], 'as_of': datetime.now(timezone.utc)}
    query = db.query(CRMActivity).filter(CRMActivity.organization_id == g.crm()._organization_id(db, user), or_(*clauses))
    if view == 'history':
        query = query.filter(CRMActivity.activity_type.in_(['follow_up_update', 'follow_up_assignment']))
    else:
        query = query.filter(CRMActivity.due_date.isnot(None))
        query = query.filter(CRMActivity.status.in_(g.sales.OPEN_ACTIVITY)) if view == 'pending' else query.filter(CRMActivity.status == 'Completed', CRMActivity.completed_at.isnot(None))
    employee_ids = {ident for pair in query.with_entities(CRMActivity.created_by_user_id, CRMActivity.owner_user_id).distinct() for ident in pair if ident}
    filter_column = CRMActivity.created_by_user_id if view == 'history' else CRMActivity.owner_user_id
    filter_employee_ids = {ident for (ident,) in query.with_entities(filter_column).distinct() if ident}
    if employee_id:
        query = query.filter((CRMActivity.created_by_user_id if view == 'history' else CRMActivity.owner_user_id) == employee_id)
    total = query.count()
    ordered = query.order_by(CRMActivity.created_at.desc(), CRMActivity.id.desc()) if view == 'history' else query.order_by(CRMActivity.due_date, CRMActivity.id)
    activities = ordered.offset((page-1)*per_page).limit(per_page).all()
    for activity in activities:
        metadata = activity.metadata_json or {}
        if metadata.get('owner_id'):
            employee_ids.add(metadata['owner_id'])
        if metadata.get('completed_by_user_id'):
            employee_ids.add(metadata['completed_by_user_id'])
        for state in [metadata.get('before'), metadata.get('after'), metadata.get('next_follow_up')]:
            if state and state.get('owner_id'):
                employee_ids.add(state['owner_id'])
        for change in metadata.get('changes', []):
            employee_ids.update(state['owner_id'] for state in [change.get('before'), change.get('after')] if state and state.get('owner_id'))
        employee_ids.update(x for x in [activity.created_by_user_id, activity.updated_by_user_id] if x)
    people = {}
    for person in db.query(User).filter(User.id.in_(employee_ids)):
        people[person.id] = {'id': person.id, 'name': getattr(person.person, 'display_name', None) or person.email, 'email': person.email}
    names = {}
    for kind, (model, records) in resources.items():
        record_kind = 'account' if kind == 'companies' else g.sales.record_kind(kind)
        ids = {row.entity_id for row in activities if row.entity_type == record_kind}
        for record in records.filter(model.id.in_(ids)):
            names[(record_kind, record.id)] = {'entity': kind, 'record_id': record.id, 'record_name': getattr(record, 'full_name', None) or getattr(record, 'name', None)}
    now = datetime.now(timezone.utc)
    items = []
    for row in activities:
        if (row.entity_type, row.entity_id) not in names:
            continue
        pending_since = utc(row.created_at) if row.status in g.sales.OPEN_ACTIVITY else None
        due = utc(row.due_date)
        items.append({**names[(row.entity_type, row.entity_id)], 'id': row.id,
                      'title': row.title or row.subject, 'action': row.activity_type,
                      'status': row.status, 'occurred_at': row.created_at, 'due_at': row.due_date,
                      'pending_since': pending_since, 'pending_seconds': max(0, int((now-pending_since).total_seconds())) if pending_since else None,
                      'overdue_since': due if pending_since and due and due < now else None,
                      'completed_at': row.completed_at, 'actor': people.get(row.created_by_user_id),
                      'completed_by': people.get((row.metadata_json or {}).get('completed_by_user_id')),
                      'assignee': people.get(row.owner_user_id), 'last_updated_by': people.get(row.updated_by_user_id),
                      'notes': row.outcome or row.body or row.description,
                      'metadata': row.metadata_json or {}})
    return {'items': items, 'total': total, 'page': page, 'pages': (total+per_page-1)//per_page,
            'employees': sorted([person for ident, person in people.items() if ident in filter_employee_ids], key=lambda person: person['name'].casefold()),
            'people': list(people.values()), 'as_of': now}
