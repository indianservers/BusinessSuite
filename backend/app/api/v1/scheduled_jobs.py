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
    return run_cron_batch(db)


@router.get("/internal/jobs")
def job_status(db=Depends(get_db), user=Depends(RequirePermission("settings_manage"))):
    return [{"id": r.id, "job": r.job_name, "period": r.period, "status": r.status,
             "cursor": r.cursor, "attempts": r.attempts, "updated_at": r.updated_at,
             "error": r.error, "result": r.result}
            for r in db.query(ScheduledJobRun).order_by(ScheduledJobRun.id.desc()).limit(100)]
