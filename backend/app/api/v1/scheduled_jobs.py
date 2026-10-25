import secrets
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from app.core.config import settings
from app.core.deps import get_db, RequirePermission
from app.models.deployment import ScheduledJobRun
from app.services.scheduled_jobs import run_cron_batch

router = APIRouter(tags=["Scheduled jobs"])


@router.get("/internal/cron")
def cron(response: Response, authorization: str = Header(""), db=Depends(get_db)):
    if not settings.CRON_SECRET or not secrets.compare_digest(authorization, f"Bearer {settings.CRON_SECRET}"):
        raise HTTPException(401, "Invalid scheduler credentials")
    response.headers["Cache-Control"] = "no-store"
    result = run_cron_batch(db)
    from app.module_registry import is_app_enabled
    if is_app_enabled("crm"):
        from app.apps.crm.lead_management import scheduled_lead_alerts
        result["lead_management"] = scheduled_lead_alerts(db)
    if is_app_enabled("hrms") and is_app_enabled("project_management"):
        from app.apps.interns_hub.distribution import scheduled_tick
        from app.apps.interns_hub.router import today
        result["intern_management"] = scheduled_tick(db,today())
    return result


@router.get("/internal/jobs")
def job_status(db=Depends(get_db), user=Depends(RequirePermission("settings_manage"))):
    return [{"id": r.id, "job": r.job_name, "period": r.period, "status": r.status,
             "cursor": r.cursor, "attempts": r.attempts, "updated_at": r.updated_at,
             "error": r.error, "result": r.result}
            for r in db.query(ScheduledJobRun).order_by(ScheduledJobRun.id.desc()).limit(100)]
