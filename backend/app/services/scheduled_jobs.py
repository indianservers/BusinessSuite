"""Bounded, leased batches; cron retries resume from committed progress."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import or_, func, update
from sqlalchemy.dialects.postgresql import insert
from app.models.deployment import ScheduledJobRun, CollaborationEvent
from app.models.employee import Employee
from app.crud.crud_leave import run_scheduled_leave_accruals


def run_cron_batch(db, *, now=None, batch_size=25):
    now = now or datetime.now(timezone.utc)
    run_date = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    period = run_date.isoformat()
    # One overdue batch is resumed first, including missed monthly accrual days.
    overdue = db.query(ScheduledJobRun).filter(
        ScheduledJobRun.job_name == "leave_accrual", ScheduledJobRun.status != "completed",
        ScheduledJobRun.period < period,
    ).order_by(ScheduledJobRun.period).first()
    if not overdue:
        last = db.query(func.max(ScheduledJobRun.period)).filter(ScheduledJobRun.job_name == "leave_accrual").scalar()
        if last:
            from datetime import date
            next_date = date.fromisoformat(last) + timedelta(days=1)
            if next_date < run_date:
                run_date = next_date
                period = run_date.isoformat()
    if overdue:
        period = overdue.period
        from datetime import date
        run_date = date.fromisoformat(period)
    db.execute(insert(ScheduledJobRun).values(job_name="leave_accrual", period=period,
        status="pending", cursor=0, attempts=0, updated_at=now).on_conflict_do_nothing(
            constraint="uq_scheduled_job_period"))
    row = db.execute(update(ScheduledJobRun).where(
        ScheduledJobRun.job_name == "leave_accrual", ScheduledJobRun.period == period,
        ScheduledJobRun.status != "completed",
        or_(ScheduledJobRun.status != "running", ScheduledJobRun.lease_until < now),
    ).values(status="running", lease_until=now + timedelta(minutes=6), updated_at=now,
             attempts=ScheduledJobRun.attempts + 1, error=None).returning(ScheduledJobRun.id, ScheduledJobRun.cursor)).first()
    db.commit()
    if not row:
        return {"status": "already_running_or_completed", "period": period}
    job_id, cursor = row
    try:
        ids = [r[0] for r in db.query(Employee.id).filter(Employee.id > cursor,
            Employee.status.in_(["Active", "Probation"]), Employee.deleted_at.is_(None)
        ).order_by(Employee.id).limit(batch_size).all()]
        result = run_scheduled_leave_accruals(db, run_date=run_date, employee_ids=ids)
        status = "completed" if len(ids) < batch_size else "pending"
        db.execute(update(ScheduledJobRun).where(ScheduledJobRun.id == job_id).values(
            cursor=ids[-1] if ids else cursor, status=status, lease_until=None,
            updated_at=now, result=result))
        # Event retention is independent of active-user polling cursors.
        db.query(CollaborationEvent).filter(CollaborationEvent.created_at < now - timedelta(days=7)).delete()
        db.commit()
        return {"status": status, "period": period, "processed": len(ids), **result}
    except Exception as exc:
        db.rollback()
        db.execute(update(ScheduledJobRun).where(ScheduledJobRun.id == job_id).values(
            status="failed", lease_until=None, updated_at=now, error=type(exc).__name__))
        db.commit()
        raise
