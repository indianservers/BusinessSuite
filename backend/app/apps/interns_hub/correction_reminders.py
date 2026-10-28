"""Correction deadlines and daily, deduplicated SES reminders."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from app.core.config import settings
from .models import InternApplication
from .management_models import ApplicationEvent
from .application_receipts import FREE_PROGRAM_NOTICE


def correction_deadline(db, item):
    if item.status != "Correction Requested":
        return None
    row = db.query(ApplicationEvent).filter_by(application_id=item.id, state="Correction Deadline").order_by(ApplicationEvent.id.desc()).first()
    if not row:
        if not item.reviewed_at:
            return None
        reviewed = item.reviewed_at
        from datetime import timezone
        if reviewed.tzinfo is None:
            reviewed = reviewed.replace(tzinfo=timezone.utc)
        return reviewed.astimezone(ZoneInfo(settings.CELERY_TIMEZONE)).date() + timedelta(days=7)
    try:
        return date.fromisoformat(row.note)
    except (ValueError, TypeError):
        return None


def run_correction_reminders(db, *, run_date=None, limit=50):
    if not (settings.INTERN_HUB_SES_ENABLED or settings.EMAIL_PROVIDER == "ses"):
        return {"status": "disabled", "accepted": 0}
    run_date = run_date or datetime.now(ZoneInfo(settings.CELERY_TIMEZONE)).date()
    from .confirmation_email import deliver_ses
    ids = [row[0] for row in db.query(InternApplication.id).filter_by(
        organization_id=settings.INTERN_HUB_ORGANIZATION_ID, status="Correction Requested").order_by(InternApplication.id)]
    accepted = attempted = 0
    for application_id in ids:
        if attempted >= limit:
            break
        item = db.query(InternApplication).filter_by(id=application_id,
            organization_id=settings.INTERN_HUB_ORGANIZATION_ID).with_for_update().one()
        deadline = correction_deadline(db, item)
        if not deadline or not 0 <= (deadline - run_date).days <= 3:
            db.commit()
            continue
        cycle = db.query(ApplicationEvent).filter_by(application_id=item.id, state="Correction Deadline").order_by(ApplicationEvent.id.desc()).first()
        if not cycle:
            cycle = ApplicationEvent(application_id=item.id, state="Correction Deadline", note=str(deadline))
            db.add(cycle)
            db.flush()
        key = f"{cycle.id}:{run_date.isoformat()}"
        if db.query(ApplicationEvent.id).filter_by(application_id=item.id,
            state="Correction Reminder", note=key).first():
            db.commit()
            continue
        # Persist the claim before contacting SES, including uncertain failures.
        db.add(ApplicationEvent(application_id=item.id, state="Correction Reminder", note=key))
        db.commit()
        attempted += 1
        try:
            deliver_ses(Source=f"Interns Hub <{settings.INTERN_HUB_SES_FROM}>",
                Destination={"ToAddresses": [item.email]}, Message={
                    "Subject": {"Data": f"Correction deadline reminder - {item.reference}", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": f"Hello {item.full_name},\n\nPlease submit the requested corrections for application {item.reference} by {deadline:%d %b %Y} (India time).\n\n"
                        f"Requested corrections: {item.review_note}\n\nOpen Application Status in Interns Hub to submit your corrections.\n\n{FREE_PROGRAM_NOTICE}\n\n{settings.INTERN_HUB_SES_BRAND} - Interns Hub", "Charset": "UTF-8"}}})
            state = "Correction Reminder Accepted"
            accepted += 1
        except Exception:
            state = "Correction Reminder Uncertain"
        db.add(ApplicationEvent(application_id=item.id, state=state, note=key))
        db.commit()
    return {"status": "completed", "attempted": attempted, "accepted": accepted}
