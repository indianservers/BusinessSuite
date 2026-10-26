"""Observed operations derived from the existing sanitized HTTP audit stream."""

import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, text
from app.models.audit import AuditLog
from app.shared.models import ServicePolicy, ServiceDocument
from app.apps.automation.models import AutomationScheduledJob
from app.apps.communication.models import CommunicationEmailMessage


def audit_filter(actor, company):
    return AuditLog.organization_id == company


def health(db, actor, company):
    db.execute(text("SELECT 1"))
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    filters = [audit_filter(actor, company), AuditLog.created_at >= since]
    total = db.query(func.count(AuditLog.id)).filter(*filters).scalar()
    errors = (
        db.query(func.count(AuditLog.id))
        .filter(*filters, AuditLog.status_code >= 500)
        .scalar()
    )
    samples = [
        v
        for (v,) in db.query(AuditLog.duration_ms)
        .filter(*filters, AuditLog.duration_ms.isnot(None))
        .order_by(AuditLog.id.desc())
        .limit(5000)
    ]
    samples.sort()
    percentile = lambda p: (
        samples[min(len(samples) - 1, int((len(samples) - 1) * p))] if samples else None
    )
    queue = [
        {"status": status, "count": count}
        for status, count in db.query(
            AutomationScheduledJob.status, func.count(AutomationScheduledJob.id)
        )
        .filter(AutomationScheduledJob.organization_id == company)
        .group_by(AutomationScheduledJob.status)
    ]
    email = [
        {"status": status, "count": count}
        for status, count in db.query(
            CommunicationEmailMessage.status, func.count(CommunicationEmailMessage.id)
        )
        .filter(CommunicationEmailMessage.organization_id == company)
        .group_by(CommunicationEmailMessage.status)
    ]
    size = (
        db.query(func.coalesce(func.sum(ServiceDocument.size_bytes), 0))
        .filter(ServiceDocument.organization_id == company)
        .scalar()
    )
    binding = db.get_bind()
    pool = getattr(binding, "engine", binding).pool
    return {
        "observedAt": datetime.now(timezone.utc),
        "windowHours": 24,
        "database": {"status": "healthy", "evidence": "SELECT 1 completed"},
        "api": {
            "status": "degraded" if errors else "healthy" if total else "unknown",
            "requests": total,
            "errors": errors,
            "errorRate": errors / total if total else None,
            "latencyMs": {
                "p50": percentile(0.5),
                "p95": percentile(0.95),
                "p99": percentile(0.99),
            },
            "sampleCount": len(samples),
            "sampleLimit": 5000,
        },
        "pool": {
            "status": "observed",
            "size": pool.size() if callable(getattr(pool, "size", None)) else None,
            "checkedOut": (
                pool.checkedout()
                if callable(getattr(pool, "checkedout", None))
                else None
            ),
        },
        "workflowQueue": queue,
        "emailQueue": email,
        "documentBytes": int(size),
        "frontend": {
            "status": "unknown",
            "reason": "No synthetic availability probe configured",
        },
        "infrastructure": {
            "status": "unknown",
            "reason": "CPU/memory telemetry adapter not configured",
        },
        "worker": {
            "status": "unknown",
            "reason": "Queue state is not a worker heartbeat",
        },
    }


def errors(db, actor, company, page=1):
    base = (
        db.query(
            AuditLog.module,
            AuditLog.endpoint,
            AuditLog.error_type,
            func.count(AuditLog.id).label("frequency"),
            func.min(AuditLog.created_at),
            func.max(AuditLog.created_at),
        )
        .filter(audit_filter(actor, company), AuditLog.status_code >= 500)
        .group_by(AuditLog.module, AuditLog.endpoint, AuditLog.error_type)
    )
    rows = []
    for module, endpoint, kind, count, first, last in (
        base.order_by(func.max(AuditLog.created_at).desc())
        .offset((page - 1) * 50)
        .limit(50)
    ):
        key = hashlib.sha256(f"{module}:{endpoint}:{kind}".encode()).hexdigest()[:32]
        policy = (
            db.query(ServicePolicy)
            .filter_by(
                scope_key=f"company:{company}:error_resolution:{key}",
                kind="error_resolution",
            )
            .first()
        )
        status = (policy.values_json or {}).get("status", "open") if policy else "open"
        if (
            policy
            and status == "resolved"
            and policy.updated_at
            and last.replace(tzinfo=timezone.utc)
            > policy.updated_at.replace(tzinfo=timezone.utc)
        ):
            status = "open"
        rows.append(
            {
                "key": key,
                "module": module,
                "endpoint": endpoint,
                "type": kind,
                "frequency": count,
                "first": first,
                "latest": last,
                "severity": "high",
                "version": policy.version if policy else 0,
                "status": status,
            }
        )
    return {"items": rows, "page": page, "pageSize": 50, "total": base.count()}


def evaluate_alerts(db, company, actor_id):
    """Deduplicated operational inbox alerts, with no external provider claims."""
    from app.models.company import Company
    from app.models.user import User
    from app.access.models import AccessMembership
    from app.models.notification import Notification, NotificationDeliveryLog

    db.query(Company).filter_by(id=company).with_for_update().one()
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    failures = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.organization_id == company,
            AuditLog.status_code >= 500,
            AuditLog.created_at >= since,
        )
        .scalar()
    )
    failed_jobs = (
        db.query(func.count(AutomationScheduledJob.id))
        .filter(
            AutomationScheduledJob.organization_id == company,
            AutomationScheduledJob.status.in_(
                ["dead_letter", "reconciliation_required"]
            ),
        )
        .scalar()
    )
    rules = []
    if failures >= 5:
        rules.append(
            (
                "api_errors",
                f"{failures} server errors in 15 minutes",
                "/admin/control/enterprise/errors",
            )
        )
    if failed_jobs:
        rules.append(
            (
                "workflow_failures",
                f"{failed_jobs} workflow executions need attention",
                "/admin/control/services/executions",
            )
        )
    recipients = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.id.in_(
                db.query(AccessMembership.user_id).filter_by(
                    company_id=company, active=True, is_admin=True
                )
            ),
        )
        .all()
    )
    if not recipients:
        recipients = (
            db.query(User).filter(User.id == actor_id, User.is_active.is_(True)).all()
        )
    created = 0
    for key, message, path in rules:
        scope = f"company:{company}:operational_alert:{key}"
        prior = (
            db.query(ServicePolicy)
            .filter_by(scope_key=scope, kind="operational_alert")
            .first()
        )
        if (
            prior
            and prior.updated_at
            and prior.updated_at.replace(tzinfo=timezone.utc) > since
        ):
            continue
        if not prior:
            prior = ServicePolicy(
                scope_key=scope,
                kind="operational_alert",
                organization_id=company,
                updated_by=actor_id,
                values_json={},
                version=0,
            )
            db.add(prior)
        prior.values_json = {"message": message, "path": path}
        prior.updated_by = actor_id
        prior.version += 1
        prior.updated_at = datetime.now(timezone.utc)
        for recipient in recipients:
            notification = Notification(
                company_id=company,
                user_id=recipient.id,
                title="Master Suite operational alert",
                message=message,
                module="system",
                event_type=key,
                action_url=path,
                priority="high",
                channels=["in_app"],
            )
            db.add(notification)
            db.flush()
            db.add(
                NotificationDeliveryLog(
                    notification_id=notification.id,
                    channel="in_app",
                    recipient=str(recipient.id),
                    status="delivered",
                    delivered_at=datetime.now(timezone.utc),
                )
            )
            created += 1
    return {
        "created": created,
        "cooldownMinutes": 15,
        "externalDelivery": "not requested",
    }
