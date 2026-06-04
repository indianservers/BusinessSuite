from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.deps import RequirePermission, get_db
from app.models.audit import AuditLog
from app.models.audit import FieldAuditEvent
from app.models.user import User
from app.schemas.audit import AuditLogSchema, FieldAuditEventSchema

router = APIRouter(prefix="/logs", tags=["Admin Logs"])


@router.get("/audit", response_model=List[AuditLogSchema])
def list_audit_logs(
    endpoint: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    status_min: Optional[int] = Query(None),
    status_max: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    from_at: Optional[datetime] = Query(None),
    to_at: Optional[datetime] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    query = db.query(AuditLog)
    if endpoint:
        query = query.filter(AuditLog.endpoint.ilike(f"%{endpoint}%"))
    if method:
        query = query.filter(AuditLog.method == method.upper())
    if status_min is not None:
        query = query.filter(AuditLog.status_code >= status_min)
    if status_max is not None:
        query = query.filter(AuditLog.status_code <= status_max)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if from_at:
        query = query.filter(AuditLog.created_at >= from_at)
    if to_at:
        query = query.filter(AuditLog.created_at <= to_at)
    return query.order_by(AuditLog.id.desc()).limit(limit).all()


@router.get("/field-audit", response_model=List[FieldAuditEventSchema])
def list_field_audit_events(
    employee_id: Optional[int] = Query(None),
    field_name: Optional[str] = Query(None),
    actor_user_id: Optional[int] = Query(None),
    module: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    from_at: Optional[datetime] = Query(None),
    to_at: Optional[datetime] = Query(None),
    value_hash: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    query = db.query(FieldAuditEvent)
    if employee_id:
        query = query.filter(FieldAuditEvent.employee_id == employee_id)
    if field_name:
        query = query.filter(FieldAuditEvent.field_name == field_name)
    if actor_user_id:
        query = query.filter(FieldAuditEvent.actor_user_id == actor_user_id)
    if module:
        query = query.filter(FieldAuditEvent.module == module)
    if entity_type:
        query = query.filter(FieldAuditEvent.entity_type == entity_type)
    if from_at:
        query = query.filter(FieldAuditEvent.created_at >= from_at)
    if to_at:
        query = query.filter(FieldAuditEvent.created_at <= to_at)
    if value_hash:
        query = query.filter((FieldAuditEvent.old_value_hash == value_hash) | (FieldAuditEvent.new_value_hash == value_hash))
    return query.order_by(FieldAuditEvent.id.desc()).limit(limit).all()


@router.get("/errors", response_model=List[AuditLogSchema])
def list_error_logs(
    endpoint: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    query = db.query(AuditLog).filter(AuditLog.status_code >= 400)
    if endpoint:
        query = query.filter(AuditLog.endpoint.ilike(f"%{endpoint}%"))
    return query.order_by(AuditLog.id.desc()).limit(limit).all()


@router.get("/analysis")
def log_analysis(
    endpoint: Optional[str] = Query(None),
    from_at: Optional[datetime] = Query(None),
    to_at: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("company_manage")),
):
    query = db.query(AuditLog)
    if endpoint:
        query = query.filter(AuditLog.endpoint.ilike(f"%{endpoint}%"))
    if from_at:
        query = query.filter(AuditLog.created_at >= from_at)
    if to_at:
        query = query.filter(AuditLog.created_at <= to_at)

    total = query.count()
    errors = query.filter(AuditLog.status_code >= 400).count()
    server_errors = query.filter(AuditLog.status_code >= 500).count()
    avg_duration = query.with_entities(func.avg(AuditLog.duration_ms)).scalar() or 0

    by_status = (
        query.with_entities(AuditLog.status_code, func.count(AuditLog.id))
        .group_by(AuditLog.status_code)
        .order_by(AuditLog.status_code)
        .all()
    )
    by_method = (
        query.with_entities(AuditLog.method, func.count(AuditLog.id))
        .group_by(AuditLog.method)
        .order_by(func.count(AuditLog.id).desc())
        .all()
    )
    top_errors = (
        query.filter(AuditLog.status_code >= 400)
        .with_entities(AuditLog.endpoint, AuditLog.status_code, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.endpoint, AuditLog.status_code)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )
    slow = (
        query.with_entities(AuditLog.endpoint, func.avg(AuditLog.duration_ms).label("avg_ms"), func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.endpoint)
        .order_by(func.avg(AuditLog.duration_ms).desc())
        .limit(10)
        .all()
    )

    return {
        "total_requests": total,
        "error_count": errors,
        "server_error_count": server_errors,
        "error_rate_percent": round((errors / total * 100) if total else 0, 2),
        "avg_duration_ms": round(float(avg_duration), 2),
        "by_status": [{"status_code": row[0], "count": row[1]} for row in by_status],
        "by_method": [{"method": row[0], "count": row[1]} for row in by_method],
        "top_errors": [{"endpoint": row[0], "status_code": row[1], "count": row[2]} for row in top_errors],
        "slow_endpoints": [{"endpoint": row[0], "avg_ms": round(float(row[1] or 0), 2), "count": row[2]} for row in slow],
    }
