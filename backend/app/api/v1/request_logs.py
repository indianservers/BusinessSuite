"""Strict admin-only access to request audit evidence."""
from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.audit import AuditLog, AuditLogTask

router = APIRouter()


def global_audit_admin(user: User = Depends(get_current_user)):
    if not user.is_superuser and (not user.role or user.role.name not in {'admin', 'super_admin'}):
        raise HTTPException(403, 'Administrator access required')
    return user


def scoped_query(db, user):
    if user.is_superuser or (user.role and user.role.name in {'admin', 'super_admin'}):
        return db.query(AuditLog), 'suite'
    from app.apps.project_management.models import PMSWorkspaceMember, PMSProject
    from app.apps.project_management.access import accessible_project_query
    workspace_ids = [m.workspace_id for m in db.query(PMSWorkspaceMember).filter(PMSWorkspaceMember.user_id == user.id, PMSWorkspaceMember.role.in_(['Owner', 'Admin'])).all()]
    names = {p.name for p in user.role.permissions} if user.role else set()
    legacy_ids = [p.id for p in accessible_project_query(db, user).filter(PMSProject.workspace_id.is_(None)).all()] if 'pms_admin' in names or (user.role and user.role.name == 'pms_admin') else []
    if not workspace_ids and not legacy_ids:
        raise HTTPException(403, 'Workspace administrator access required')
    return db.query(AuditLog).filter(AuditLog.module == 'project-management', or_(AuditLog.workspace_id.in_(workspace_ids), AuditLog.project_id.in_(legacy_ids), AuditLog.user_id == user.id)), 'workspace'


def output(row, task_ids):
    try:
        metadata = json.loads(row.description or '{}')
        if not isinstance(metadata, dict):
            metadata = {}
    except (ValueError, TypeError):
        metadata = {}
    return {key: getattr(row, key) for key in ['id','user_id','actor_email','actor_role','actor_authenticated','request_id','module','method','endpoint','status_code','duration_ms','task_id','project_id','workspace_id','ip_address','ip_source','forwarded_ip','user_agent','error_type','created_at']} | {
        'created_at': row.created_at.replace(tzinfo=timezone.utc) if row.created_at and row.created_at.tzinfo is None else row.created_at,
        'task_ids': task_ids, 'changed_fields': metadata.get('changed_fields', []),
        'outcome': 'server_error' if (row.status_code or 0) >= 500 else 'rejected' if (row.status_code or 0) >= 400 else 'success',
        'safe_query': metadata.get('safe_query', {}), 'error_location': metadata.get('error_location', []),
    }


@router.get('/requests')
def requests(
    user_id: int | None = None, task_id: int | None = None, project_id: int | None = None,
    role: str | None = Query(None, max_length=80), request_id: str | None = Query(None, max_length=64),
    email: str | None = Query(None, max_length=100), ip: str | None = Query(None, max_length=50),
    module: str | None = Query(None, max_length=80), method: str | None = Query(None, max_length=10),
    outcome: str | None = Query(None, pattern='^(success|rejected|server_error)$'),
    from_at: datetime | None = None, to_at: datetime | None = None,
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    query, scope = scoped_query(db, user)
    from_at = from_at.replace(tzinfo=timezone.utc) if from_at and from_at.tzinfo is None else from_at
    to_at = to_at.replace(tzinfo=timezone.utc) if to_at and to_at.tzinfo is None else to_at
    if from_at and to_at and from_at > to_at:
        raise HTTPException(422, 'Start timestamp must not be after end timestamp')
    for field, value in [('user_id',user_id),('project_id',project_id),('actor_role',role),('request_id',request_id),('ip_address',ip),('module',module),('method',method.upper() if method else None)]:
        if value is not None:
            query = query.filter(getattr(AuditLog, field) == value)
    if task_id:
        linked = db.query(AuditLogTask.audit_log_id).filter_by(task_id=task_id)
        query = query.filter(or_(AuditLog.task_id == task_id, AuditLog.id.in_(linked)))
    if email:
        query = query.filter(AuditLog.actor_email.ilike('%' + email.replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%', escape='\\'))
    if from_at:
        query = query.filter(AuditLog.created_at >= from_at)
    if to_at:
        query = query.filter(AuditLog.created_at <= to_at)
    if outcome == 'server_error': query = query.filter(AuditLog.status_code >= 500)
    elif outcome == 'rejected': query = query.filter(AuditLog.status_code >= 400, AuditLog.status_code < 500)
    elif outcome == 'success': query = query.filter(AuditLog.status_code < 400)
    total = query.count()
    errors = query.filter(AuditLog.status_code >= 500).count()
    rows = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    links = {}
    for link in db.query(AuditLogTask).filter(AuditLogTask.audit_log_id.in_([row.id for row in rows])).all():
        links.setdefault(link.audit_log_id, []).append(link.task_id)
    return {'items':[output(row, sorted(links.get(row.id, [row.task_id] if row.task_id else []))) for row in rows],
            'total':total, 'server_errors':errors, 'offset':offset, 'limit':limit, 'scope':scope,
            'note':'Role and email are snapshots at request time. IP source distinguishes peer addresses from configured trusted proxies. Forwarded IP is reported separately and may be unverified.'}
