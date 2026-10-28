import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from app.core.config import settings
from app.core.deps import get_db, RequirePermission
from app.models.deployment import ScheduledJobRun
from app.services.scheduled_jobs import run_cron_batch


def scoped_email_query(db, user):
    from app.models.email_outbox import EmailOutbox
    from app.core.tenant_boundary import company_ids
    query = db.query(EmailOutbox)
    return query if user.is_superuser else query.filter(EmailOutbox.organization_id.in_(company_ids(db, user)))

router = APIRouter(tags=["Scheduled jobs"])


@router.get("/internal/email-status")
def email_status(db=Depends(get_db), user=Depends(RequirePermission("settings_manage"))):
    from sqlalchemy import func
    from app.models.email_outbox import EmailOutbox
    query = scoped_email_query(db, user)
    return {"counts": [{"module": module, "status": status, "count": count}
        for module, status, count in query.with_entities(EmailOutbox.module, EmailOutbox.status, func.count(EmailOutbox.id))
            .group_by(EmailOutbox.module, EmailOutbox.status)],
        "failures": [{"id": row.id, "module": row.module, "status": row.status, "error": row.error, "created_at": row.created_at}
            for row in query.filter(EmailOutbox.status.in_(["failed", "reconciliation_required"])).order_by(EmailOutbox.id.desc()).limit(50)]}


@router.get("/internal/email-dispatch")
def email_dispatch(response: Response, authorization: str = Header(""), db=Depends(get_db)):
    if not settings.CRON_SECRET or not secrets.compare_digest(authorization, f"Bearer {settings.CRON_SECRET}"):
        raise HTTPException(401, "Invalid scheduler credentials")
    response.headers["Cache-Control"] = "no-store"
    from app.services.email_dispatch import process_email
    return process_email(db, limit=25)


@router.get("/internal/intern-correction-reminders")
def intern_correction_reminders(response: Response, authorization: str = Header(""), db=Depends(get_db)):
    if not settings.CRON_SECRET or not secrets.compare_digest(authorization, f"Bearer {settings.CRON_SECRET}"):
        raise HTTPException(401, "Invalid scheduler credentials")
    response.headers["Cache-Control"] = "no-store"
    from app.apps.interns_hub.correction_reminders import run_correction_reminders
    return run_correction_reminders(db, limit=50)


@router.get("/internal/cron")
def cron(response: Response, authorization: str = Header(""), db=Depends(get_db)):
    if not settings.CRON_SECRET or not secrets.compare_digest(authorization, f"Bearer {settings.CRON_SECRET}"):
        raise HTTPException(401, "Invalid scheduler credentials")
    response.headers["Cache-Control"] = "no-store"
    result = run_cron_batch(db)
    from app.services.email_dispatch import process_email
    result["email"] = process_email(db, limit=25)
    from app.module_registry import is_app_enabled
    if is_app_enabled("crm"):
        from app.apps.crm.lead_management import scheduled_lead_alerts
        result["lead_management"] = scheduled_lead_alerts(db)
    if is_app_enabled("hrms") and is_app_enabled("project_management"):
        from app.apps.interns_hub.distribution import scheduled_tick
        from app.apps.interns_hub.router import today
        result["intern_management"] = scheduled_tick(db,today())
        from app.apps.interns_hub.operations import scheduled_tick as workforce_tick
        result["workforce_operations"] = workforce_tick(db)
    from app.shared.runtime import process_batch
    result["shared_services"] = process_batch(db, limit=10)
    if is_app_enabled("project_management"):
        from app.shared.communication.reminders import run_reminders
        result["communication_reminders"] = run_reminders(db)
    return result


@router.get("/internal/jobs")
def job_status(db=Depends(get_db), user=Depends(RequirePermission("settings_manage"))):
    return [{"id": r.id, "job": r.job_name, "period": r.period, "status": r.status,
             "cursor": r.cursor, "attempts": r.attempts, "updated_at": r.updated_at,
             "error": r.error, "result": r.result}
            for r in db.query(ScheduledJobRun).order_by(ScheduledJobRun.id.desc()).limit(100)]
