try:
    from celery import Celery
    from celery.schedules import crontab
except ModuleNotFoundError:
    Celery = None

    def crontab(*, hour: int, minute: int) -> dict:
        return {"hour": hour, "minute": minute}

from app.core.config import settings
from app.crud.crud_leave import run_scheduled_leave_accruals
from app.db.session import SessionLocal


class _CeleryFallback:
    def __init__(self) -> None:
        self.conf = type("CeleryFallbackConf", (), {})()

    def task(self, *, name: str):
        def decorator(func):
            func.name = name
            return func

        return decorator


celery_app = (
    Celery(
        "ai_hrms",
        broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
        backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    )
    if Celery
    else _CeleryFallback()
)

celery_app.conf.timezone = settings.CELERY_TIMEZONE
celery_app.conf.beat_schedule = {
    "process-pms-operator-queue": {
        "task": "app.worker.process_operator_queue",
        "schedule": 5.0,
    },
    "credit-scheduled-leave-accruals-daily": {
        "task": "app.worker.credit_scheduled_leave_accruals",
        "schedule": crontab(hour=1, minute=0),
    },
}


@celery_app.task(name="app.worker.credit_scheduled_leave_accruals")
def credit_scheduled_leave_accruals() -> dict:
    db = SessionLocal()
    try:
        return run_scheduled_leave_accruals(db)
    finally:
        db.close()


@celery_app.task(name="app.worker.process_operator_queue")
def process_operator_queue() -> dict:
    from app.module_registry import is_app_enabled
    if not is_app_enabled("project_management"):
        return {"disabled": True}
    from app.ai_operator.jobs import process_batch
    db = SessionLocal()
    try:
        return process_batch(db)
    finally:
        db.close()
