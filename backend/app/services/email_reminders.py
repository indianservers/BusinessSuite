"""Bounded daily deadline reminders using the module event recipient rules."""
from datetime import datetime, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo
from sqlalchemy import String, cast, exists, func, literal, select
from app.core.config import settings
from app.db.base_class import Base
from app.models.email_outbox import EmailOutbox
from app.services.email_dispatch import queue_email
from app.services.email_events import EVENTS, recipients

DEADLINES = {
    "employee_onboarding_tasks": "due_date", "employee_onboardings": "target_completion_date",
    "learning_assignments": "due_date", "pms_tasks": "due_date", "pms_milestones": "due_date",
    "pms_task_assignees": "due_date",
    "crm_activities": "due_date", "crm_leads": "next_follow_up_at", "crm_meetings": "start_time",
    "srm_invoices": "due_date", "srm_contracts": "expiry_date", "srm_engagements": "planned_end_date",
    "srm_purchase_orders": "expected_date", "fam_purchase_bills": "due_date",
}
TERMINAL = {"draft", "completed", "complete", "done", "closed", "cancelled", "canceled", "rejected", "paid", "archived", "resolved"}


def enqueue_due_reminders(db, *, run_date=None, limit=25):
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return 0
    run_date = run_date or datetime.now(ZoneInfo(settings.CELERY_TIMEZONE)).date()
    models = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers}
    queued = 0
    for table, field in DEADLINES.items():
        if queued >= limit:
            break
        model = models.get(table)
        if model is None:
            continue
        deadline = getattr(model, field)
        identity = model.id if hasattr(model, "id") else model.task_id
        identity_text = cast(identity, String)
        if table == "pms_task_assignees":
            parent = models["pms_tasks"]
            deadline = func.coalesce(model.due_date, select(parent.due_date).where(parent.id == model.task_id).scalar_subquery())
            identity_text = cast(model.task_id, String) + literal(":") + cast(model.user_id, String)
        prefix = literal("reminder:" + table + ":") + identity_text + literal(":" + run_date.isoformat() + ":")
        query = db.query(model).filter(
            func.date(deadline) <= run_date + timedelta(days=1),
            func.date(deadline) >= run_date - timedelta(days=7),
            ~exists(select(EmailOutbox.id).where(EmailOutbox.event_key.like(prefix + "%"))),
        )
        if hasattr(model, "status"):
            query = query.filter(~func.lower(model.status).in_(TERMINAL))
        elif hasattr(model, "execution_status"):
            query = query.filter(~func.lower(model.execution_status).in_(TERMINAL), model.cancelled_at.is_(None))
        if table == "pms_tasks":
            assignment = models["pms_task_assignees"]
            query = query.filter(~exists(select(assignment.task_id).where(assignment.task_id == model.id, assignment.cancelled_at.is_(None))))
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))
        for obj in query.order_by(deadline, identity).with_for_update(skip_locked=True).limit(limit - queued):
            spec = EVENTS[table]
            source_id = str(obj.id) if hasattr(obj, "id") else f"{obj.task_id}:{obj.user_id}"
            for address, user_id, org in recipients(db, obj, spec):
                key = f"reminder:{table}:{source_id}:{run_date.isoformat()}:{sha256(address.casefold().encode()).hexdigest()}"
                row = queue_email(db, recipient=address, user_id=user_id, organization_id=org, module=spec[0],
                    event_key=key, subject=spec[1] + " deadline reminder",
                    body=f"{spec[1]} #{source_id} has an upcoming or overdue deadline.\n"
                         "Sign in to review its current status:\n" + settings.FRONTEND_PUBLIC_URL.rstrip("/") + spec[5])
                queued += bool(row)
                if queued >= limit:
                    break
        db.commit()
    return queued
